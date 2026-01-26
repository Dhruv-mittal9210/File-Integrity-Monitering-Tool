"""
Real-time watch mode built on top of watchdog.
Watch mode is an interrupt-driven version of check: incremental, event-based comparison.

Design principles:
1. Stateless: Baseline is source of truth, never rebuilt
2. One event = one decision: "Does this event violate the baseline?"
3. Idempotent: Same event twice → same outcome (handle duplicate/noisy events)
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from .comparator import compare_baseline
from .hasher import hash_file
from .logger import append_log
from .scanner import _matches_exclude_patterns


def classify_change(rel_path: str, baseline_files: Dict[str, dict], new_meta: Optional[dict]) -> Optional[str]:
    """
    Decide what changed for a single path by reusing comparator logic.
    Returns one of: "created", "modified", "deleted", or None if no change.
    
    This is the single decision point: "Does this event violate the baseline?"
    - Created → not in baseline
    - Modified → hash mismatch with baseline
    - Deleted → existed in baseline, now gone
    """
    old_subset = {rel_path: baseline_files[rel_path]} if rel_path in baseline_files else {}
    new_subset = {rel_path: new_meta} if new_meta else {}

    diff = compare_baseline(old_subset, new_subset)
    if diff["created"]:
        return "created"
    if diff["modified"]:
        return "modified"
    if diff["deleted"]:
        return "deleted"
    return None


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
    ) -> None:
        self.target = target.resolve()
        self.baseline_files = baseline_files  # Read-only source of truth
        self.exclude = exclude or []
        self.log_path = log_path

    # ---- helpers ---------------------------------------------------------
    def _rel_path(self, absolute: str) -> Optional[str]:
        """Convert absolute path to relative path from target root."""
        try:
            rel = Path(absolute).resolve().relative_to(self.target)
            return str(rel)
        except Exception:
            return None

    def _should_ignore(self, rel_path: str) -> bool:
        """Check if path matches exclude patterns."""
        return _matches_exclude_patterns(rel_path, self.exclude)

    def _build_meta(self, path: Path) -> Optional[dict]:
        """
        Build file metadata (hash, size, mtime).
        Returns None if file is unreadable, locked, or half-written.
        This handles the "never trust filesystem events" principle:
        file may exist but be half-written, so hash might fail.
        """
        try:
            stat = path.stat()
        except (FileNotFoundError, PermissionError, OSError):
            # File disappeared, locked, or inaccessible - ignore this event
            return None

        file_hash = hash_file(path)
        if file_hash is None:
            # Hash failed (file might be half-written, locked, etc.) - ignore
            return None

        return {
            "hash": file_hash,
            "size": stat.st_size,
            "mtime": int(stat.st_mtime),
        }

    def _emit(self, kind: str, rel_path: str, meta: Optional[dict] = None) -> None:
        """
        Emit change event to console and log.
        Uses same event types as check command: "created", "modified", "deleted"
        Log format compatible with check: same event types, same structure.
        """
        print(f"[{kind.upper()}] {rel_path}")
        if self.log_path:
            # Log individual watch events using same event types as check
            # Structure: single path per event (event-driven) vs check's batch format
            append_log(
                self.log_path,
                {
                    "event": "watch",
                    "target": str(self.target),
                    "path": rel_path,
                    "change_type": kind,  # "created", "modified", or "deleted"
                    "hash": meta.get("hash") if meta else None,
                },
            )

    def _evaluate_event(self, rel_path: str, abs_path: Optional[Path] = None, is_delete: bool = False) -> None:
        """
        Core decision function: "Does this event violate the baseline?"
        
        One event = one decision. Stateless comparison against baseline.
        Idempotent: same file state → same result (handles duplicate events).
        """
        # Filter: ignore paths outside target or matching exclude patterns
        if rel_path is None or self._should_ignore(rel_path):
            return

        # Decision point: compare current state against baseline
        if is_delete:
            # File deleted: violates baseline if it existed in baseline
            change = classify_change(rel_path, self.baseline_files, None)
            if change:  # Only "deleted" is possible here
                self._emit(change, rel_path)
            return

        # File created or modified: need to hash it
        if abs_path is None:
            return

        meta = self._build_meta(abs_path)
        if meta is None:
            # File unreadable/half-written - ignore this event (idempotent: will retry on next event)
            return

        # Decision: does current hash match baseline?
        change = classify_change(rel_path, self.baseline_files, meta)
        if change:
            # Violation detected: created (not in baseline) or modified (hash mismatch)
            self._emit(change, rel_path, meta)
        # If change is None, file matches baseline - no violation, no output (idempotent)

    # ---- event processors ------------------------------------------------
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation event."""
        if event.is_directory:
            return
        rel_path = self._rel_path(event.src_path)
        self._evaluate_event(rel_path, Path(event.src_path), is_delete=False)

    def on_modified(self, event: FileModifiedEvent) -> None:
        """
        Handle file modification event.
        Windows may fire this twice for the same change - idempotent handling
        ensures same file state → same result.
        """
        if event.is_directory:
            return
        rel_path = self._rel_path(event.src_path)
        self._evaluate_event(rel_path, Path(event.src_path), is_delete=False)

    def on_deleted(self, event: FileDeletedEvent) -> None:
        """Handle file deletion event."""
        if event.is_directory:
            return
        rel_path = self._rel_path(event.src_path)
        self._evaluate_event(rel_path, is_delete=True)

    def on_moved(self, event: FileMovedEvent) -> None:
        """
        Handle file move/rename event.
        Treated as delete (src) + create (dest) for baseline comparison.
        """
        if event.is_directory:
            return
        # Source: deleted
        rel_src = self._rel_path(event.src_path)
        self._evaluate_event(rel_src, is_delete=True)
        # Destination: created
        rel_dest = self._rel_path(event.dest_path)
        self._evaluate_event(rel_dest, Path(event.dest_path), is_delete=False)


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