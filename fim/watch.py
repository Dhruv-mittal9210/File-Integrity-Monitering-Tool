"""
Real-time watch mode built on top of watchdog.
Watch mode is an interrupt-driven version of check: incremental, event-based comparison.

Design principles:
1. Stateless: Baseline is source of truth, never rebuilt
2. One event = one decision: "Does this event violate the baseline?"
3. Idempotent: Same event twice → same outcome (handle duplicate/noisy events)
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from .hasher import hash_file
from .logger import append_log
from .scanner import _matches_exclude_patterns
from .utils import normalize_rel_path


ChangeType = str  # "created" | "modified" | "deleted"


@dataclass(frozen=True)
class CompareResult:
    """
    Output of single-file comparator.

    - change_type: created/modified/deleted or None for no change
    - meta: computed metadata (hash/size/mtime) when available
    - unreadable: True when file couldn't be read/hashed; caller may retry once
    """

    change_type: Optional[ChangeType]
    meta: Optional[dict] = None
    unreadable: bool = False


@dataclass(frozen=True)
class NormalizedEvent:
    """
    Normalized event that watch mode processes.
    MOVED is normalized to DELETE + CREATE elsewhere.
    """

    kind: str  # "created" | "modified" | "deleted"
    abs_path: Path


def normalize_event(kind: str, src_path: str, dest_path: Optional[str] = None) -> List[NormalizedEvent]:
    """
    Normalize noisy watchdog events into explicit security-relevant events.

    Raw event -> normalized:
    - moved -> deleted(src) + created(dest)
    - created -> created
    - modified -> modified
    - deleted -> deleted
    """
    k = kind.lower().strip()
    if k == "moved":
        if dest_path is None:
            return [NormalizedEvent(kind="deleted", abs_path=Path(src_path))]
        return [
            NormalizedEvent(kind="deleted", abs_path=Path(src_path)),
            NormalizedEvent(kind="created", abs_path=Path(dest_path)),
        ]
    if k in ("created", "modified", "deleted"):
        return [NormalizedEvent(kind=k, abs_path=Path(src_path))]
    # unknown event -> ignore
    return []


def _build_file_meta(path: Path) -> Tuple[Optional[dict], bool]:
    """
    Build file metadata (hash, size, mtime).

    Returns (meta, unreadable):
    - meta is None when file missing or unreadable
    - unreadable True means "exists but we couldn't read/hash it"
    """
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None, False
    except (PermissionError, OSError):
        return None, True

    file_hash = hash_file(path)
    if file_hash is None:
        return None, True

    return {
        "hash": file_hash,
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
    }, False


def compare_file(abs_path: Path, rel_path: str, baseline_entry: Optional[dict]) -> CompareResult:
    """
    Single-file comparator (MANDATORY core brain):

    One path in -> one decision out.
    - No scanning
    - No logging
    - Pure decision logic around baseline truth + current file state

    Rules:
    - Created  -> not in baseline, but exists now (readable)
    - Modified -> in baseline, exists now, hash mismatch
    - Deleted  -> in baseline, missing now
    - None     -> matches baseline OR unreadable (caller may retry once)
    """
    meta, unreadable = _build_file_meta(abs_path)

    # Missing file
    if meta is None and not unreadable:
        if baseline_entry is not None:
            return CompareResult(change_type="deleted", meta=None, unreadable=False)
        return CompareResult(change_type=None, meta=None, unreadable=False)

    # Unreadable/half-written: do not claim modified; allow one retry
    if meta is None and unreadable:
        return CompareResult(change_type=None, meta=None, unreadable=True)

    # Exists & readable at this point
    if baseline_entry is None:
        return CompareResult(change_type="created", meta=meta, unreadable=False)

    baseline_hash = baseline_entry.get("hash")
    if baseline_hash != meta.get("hash"):
        return CompareResult(change_type="modified", meta=meta, unreadable=False)

    return CompareResult(change_type=None, meta=meta, unreadable=False)


class WatchHandler(FileSystemEventHandler):
    """
    Stateless watchdog handler that compares each event against baseline.
    Baseline is source of truth - never modified or rebuilt.
    """

    def __init__(
        self,
        target: Path,
        baseline_files: Dict[str, dict],
        exclude: Optional[List[str]],
        log_path: Optional[Path] = None,
        debounce_ms: int = 600,
    ) -> None:
        self.target = target.resolve()
        self.baseline_files = baseline_files  # Read-only source of truth
        self.exclude = exclude or []
        self.log_path = log_path

        # per-path debounce state (Windows is noisy)
        self.debounce_seconds = max(0.0, debounce_ms / 1000.0)
        self._lock = threading.Lock()
        self._timers: Dict[str, threading.Timer] = {}
        self._pending: Dict[str, Path] = {}  # rel_path -> last abs_path to evaluate
        self._retry_once: Dict[str, bool] = {}  # rel_path -> whether we've retried already

    # ---- helpers ---------------------------------------------------------
    def _rel_path(self, absolute: str) -> Optional[str]:
        """Convert absolute path to relative path from target root."""
        try:
            rel = Path(absolute).resolve().relative_to(self.target)
            return normalize_rel_path(rel)
        except Exception:
            return None

    def _should_ignore(self, rel_path: str) -> bool:
        """Check if path matches exclude patterns."""
        return _matches_exclude_patterns(rel_path, self.exclude)

    def _emit(self, kind: str, rel_path: str, meta: Optional[dict] = None) -> None:
        """
        Emit change event to console and log.
        Uses same event types as check command: "created", "modified", "deleted"
        Log format compatible with check: same event types, same structure.
        """
        print(f"[{kind.upper()}] {rel_path}")
        if self.log_path:
            # Same log "shape" as check (created/modified/deleted lists),
            # but watch emits one decision at a time.
            append_log(
                self.log_path,
                {
                    "event": "watch",
                    "target": str(self.target),
                    "created": [rel_path] if kind == "created" else [],
                    "modified": [rel_path] if kind == "modified" else [],
                    "deleted": [rel_path] if kind == "deleted" else [],
                    # optional extra for watch consumers/services
                    "path": rel_path,
                    "hash": meta.get("hash") if meta else None,
                },
            )

    # ---- debounce + evaluation ------------------------------------------
    def _schedule_evaluation(self, rel_path: str, abs_path: Path) -> None:
        """
        Per-path debounce: always process the latest filesystem state.
        If events arrive too quickly, delay processing until Windows finishes touching the file.
        """
        with self._lock:
            self._pending[rel_path] = abs_path
            # cancel existing timer for this path
            t = self._timers.get(rel_path)
            if t is not None:
                t.cancel()
            timer = threading.Timer(self.debounce_seconds, self._flush_one, args=(rel_path,))
            timer.daemon = True
            self._timers[rel_path] = timer
            timer.start()

    def _flush_one(self, rel_path: str) -> None:
        # Grab latest pending state
        with self._lock:
            abs_path = self._pending.get(rel_path)
            # timer has fired; remove it
            self._timers.pop(rel_path, None)

        if abs_path is None:
            return

        # Evaluate latest filesystem state vs baseline
        baseline_entry = self.baseline_files.get(rel_path)
        result = compare_file(abs_path, rel_path, baseline_entry)

        if result.unreadable:
            # Retry once after debounce window (Day 10 rule)
            do_retry = False
            with self._lock:
                already = self._retry_once.get(rel_path, False)
                if not already:
                    self._retry_once[rel_path] = True
                    do_retry = True
            if do_retry:
                self._schedule_evaluation(rel_path, abs_path)
            return

        # On successful read, clear retry flag for future noise
        with self._lock:
            self._retry_once.pop(rel_path, None)

        if result.change_type:
            self._emit(result.change_type, rel_path, result.meta)

    # ---- event processors ------------------------------------------------
    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        for ne in normalize_event("created", event.src_path):
            rel_path = self._rel_path(str(ne.abs_path))
            if rel_path is None or self._should_ignore(rel_path):
                continue
            self._schedule_evaluation(rel_path, ne.abs_path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        if event.is_directory:
            return
        for ne in normalize_event("modified", event.src_path):
            rel_path = self._rel_path(str(ne.abs_path))
            if rel_path is None or self._should_ignore(rel_path):
                continue
            self._schedule_evaluation(rel_path, ne.abs_path)

    def on_deleted(self, event: FileDeletedEvent) -> None:
        if event.is_directory:
            return
        for ne in normalize_event("deleted", event.src_path):
            rel_path = self._rel_path(str(ne.abs_path))
            if rel_path is None or self._should_ignore(rel_path):
                continue
            self._schedule_evaluation(rel_path, ne.abs_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        if event.is_directory:
            return
        for ne in normalize_event("moved", event.src_path, event.dest_path):
            rel_path = self._rel_path(str(ne.abs_path))
            if rel_path is None or self._should_ignore(rel_path):
                continue
            self._schedule_evaluation(rel_path, ne.abs_path)


def _build_observer(use_polling: bool = False) -> Observer:
    """
    Create a watchdog observer. PollingObserver is slower but more compatible
    across filesystems; used as a fallback when requested.
    """
    if use_polling:
        return PollingObserver()
    return Observer()


def watch(target: Path, baseline_files: Dict[str, dict], exclude: Optional[List[str]], log_path: Optional[Path]) -> None:
    """
    Start a foreground watch loop. Blocks until KeyboardInterrupt.
    """
    handler = WatchHandler(target, baseline_files, exclude, log_path)
    observer = _build_observer()
    observer.schedule(handler, str(target), recursive=True)
    observer.start()

    print(f"Watching {target.resolve()} for changes... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping watcher...")
    finally:
        observer.stop()
        observer.join()