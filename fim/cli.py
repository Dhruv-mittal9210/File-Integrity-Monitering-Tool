#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Any, List
import shutil
from datetime import datetime

from .scanner import scan_directory
from .storage.json_store import save_json, load_json
from .schema import build_baseline_structure
from .comparator import compare_baseline
from .logger import append_log
from .settings import build_settings
from .watch import watch
from .utils import default_watch_log_path, is_path_within, normalize_rel_path


def _flatten_exclude(exclude_arg: Any) -> List[str]:
    """
    Normalize argparse output for --exclude to a flat list of strings.
    Accepts None, list, or list-of-lists (from previous argparse patterns).
    """
    if exclude_arg is None:
        return []
    if isinstance(exclude_arg, str):
        return [exclude_arg]
    flat: List[str] = []
    for item in exclude_arg:
        if item is None:
            continue
        if isinstance(item, (list, tuple)):
            for sub in item:
                if sub is not None:
                    flat.append(str(sub))
        else:
            flat.append(str(item))
    return flat


# ===========================
# INIT COMMAND
# ===========================

def init_command(args: Any) -> None:
    # normalize exclude arg shape before passing to settings
    args.exclude = _flatten_exclude(args.exclude)

    settings = build_settings(args, args.config)

    target = settings["target"]
    baseline_path = Path(settings["baseline"])
    exclude = settings.get("exclude", [])
    follow_symlinks = settings.get("follow_symlinks", False)

    print(f"Scanning directory: {target}")
    files = scan_directory(Path(target), exclude=exclude, follow_symlinks=follow_symlinks)

    print(f"Found {len(files)} files. Building baseline...")
    baseline = build_baseline_structure(str(Path(target).resolve()), files)

    save_json(baseline_path, baseline)
    print(f"Baseline saved to {baseline_path}")

    # log init event
    append_log(Path(settings["log"]), {
        "event": "init",
        "target": str(Path(target).resolve()),
        "baseline": str(baseline_path),
        "files_count": len(files)
    })


# ===========================
# CHECK COMMAND
# ===========================

def check_command(args: Any) -> None:
    args.exclude = _flatten_exclude(args.exclude)
    settings = build_settings(args, args.config)

    target = settings["target"]
    baseline_path = Path(settings["baseline"])
    log_path = Path(settings["log"])
    exclude = settings.get("exclude", [])
    follow_symlinks = settings.get("follow_symlinks", False)

    baseline = load_json(baseline_path)
    if baseline is None:
        print(f"ERROR: Baseline not found at: {baseline_path}")
        return
    baseline_files_raw = baseline.get("files", {})
    baseline_files = {normalize_rel_path(k): v for k, v in baseline_files_raw.items()}

    print(f"Scanning current directory state: {target}")
    new_files = scan_directory(Path(target), exclude=exclude, follow_symlinks=follow_symlinks)

    print("Comparing with baseline...")
    changes = compare_baseline(baseline_files, new_files)

    created = changes.get("created", [])
    deleted = changes.get("deleted", [])
    modified = changes.get("modified", [])

    if not (created or deleted or modified):
        print("No changes detected. Everything is clean.")
    else:
        print("\n=== Changes Detected ===")

        if created:
            print("\n[CREATED]")
            for p in created:
                print(" +", p)

        if modified:
            print("\n[MODIFIED]")
            for p in modified:
                print(" *", p)

        if deleted:
            print("\n[DELETED]")
            for p in deleted:
                print(" -", p)

    append_log(log_path, {
        "event": "check",
        "target": str(Path(target).resolve()),
        "created": created,
        "modified": modified,
        "deleted": deleted
    })

    print(f"\nLogged to {log_path}")


# ===========================
# UPDATE COMMAND
# ===========================

def update_command(args: Any) -> None:
    args.exclude = _flatten_exclude(args.exclude)
    settings = build_settings(args, args.config)

    target = settings["target"]
    baseline_path = Path(settings["baseline"])
    log_path = Path(settings["log"])
    exclude = settings.get("exclude", [])
    follow_symlinks = settings.get("follow_symlinks", False)

    old_baseline = load_json(baseline_path)
    if old_baseline is None:
        print(f"ERROR: Baseline not found at {baseline_path}. Run `fim init` first.")
        return
    old_files_raw = old_baseline.get("files", {})
    old_files = {normalize_rel_path(k): v for k, v in old_files_raw.items()}

    print(f"Scanning current directory state: {target}")
    new_files = scan_directory(Path(target), exclude=exclude, follow_symlinks=follow_symlinks)

    changes = compare_baseline(old_files, new_files)

    created = changes.get("created", [])
    modified = changes.get("modified", [])
    deleted = changes.get("deleted", [])

    if not (created or deleted or modified):
        print("No changes found. Baseline is already up-to-date.")
        return

    print("\n=== Proposed Baseline Update ===")

    if created:
        print("\n[CREATED]")
        for f in created:
            print(" +", f)

    if modified:
        print("\n[MODIFIED]")
        for f in modified:
            print(" *", f)

    if deleted:
        print("\n[DELETED]")
        for f in deleted:
            print(" -", f)

    if not getattr(args, "yes", False):
        confirm = input("\nApply these changes to baseline? (y/N): ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Update cancelled.")
            return
    else:
        print("Auto-confirm enabled: applying changes to baseline.")

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup = baseline_path.with_name(f"{baseline_path.name}.bak.{ts}")

    try:
        shutil.copy2(baseline_path, backup)
        print(f"Backup created: {backup}")
    except Exception as e:
        print(f"ERROR: Failed to create backup: {e}")
        print("Baseline update aborted for safety.")
        return

    new_baseline = build_baseline_structure(str(Path(target).resolve()), new_files)
    save_json(baseline_path, new_baseline)
    print(f"Baseline updated: {baseline_path}")

    append_log(log_path, {
        "event": "baseline_update",
        "target": str(Path(target).resolve()),
        "backup": str(backup),
        "created": created,
        "modified": modified,
        "deleted": deleted
    })

    print(f"Update event logged to {log_path}")


# ===========================
# WATCH COMMAND
# ===========================


def watch_command(args: Any) -> None:
    args.exclude = _flatten_exclude(args.exclude)
    settings = build_settings(args, args.config)

    target = Path(settings["target"]).resolve()
    baseline_path = Path(settings["baseline"])
    # Design rule: watch mode must never write logs inside the watched tree.
    # If user did not provide --log explicitly, choose a safe default outside.
    if getattr(args, "log", None):
        log_path = Path(args.log).expanduser()
        if not log_path.is_absolute():
            log_path = (Path.cwd() / log_path).resolve()
        if is_path_within(log_path, target):
            print("ERROR: Refusing to write watch log inside the watched directory.")
            print(f"  watched: {target}")
            print(f"  log:     {log_path}")
            print("Choose a log path outside the watched tree (e.g. under %LOCALAPPDATA%\\fim\\logs).")
            return
    else:
        log_path = default_watch_log_path(target)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    exclude = settings.get("exclude", [])

    baseline = load_json(baseline_path)
    if baseline is None:
        print(f"ERROR: Baseline not found at: {baseline_path}. Run `fim init` first.")
        return

    baseline_files_raw = baseline.get("files", {})
    baseline_files = {normalize_rel_path(k): v for k, v in baseline_files_raw.items()}
    print(f"Loaded baseline from {baseline_path} with {len(baseline_files)} files.")
    print(f"Log file: {log_path}")

    watch(target, baseline_files, exclude, log_path)


# ===========================
# CLI PARSER
# ===========================

def build_cli():
    parser = argparse.ArgumentParser(prog="fim", description="File Integrity Monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    # INIT
    p_init = sub.add_parser("init", help="Create a baseline")
    p_init.add_argument("target", help="Directory to scan")
    p_init.add_argument("--config", help="YAML config file", default=None)
    p_init.add_argument("--baseline", help="Baseline file", default=None)
    p_init.add_argument("--log", help="Log file", default=None)
    p_init.add_argument("--exclude", nargs="*", default=[])
    p_init.add_argument("--follow-symlinks", action="store_true", default=False,
                        help="Follow symlinks while scanning")

    # CHECK
    p_check = sub.add_parser("check", help="Check integrity against baseline")
    p_check.add_argument("target", help="Directory to scan")
    p_check.add_argument("--config", help="YAML config file", default=None)
    p_check.add_argument("--baseline", help="Baseline file", default=None)
    p_check.add_argument("--log", help="Log file", default=None)
    p_check.add_argument("--exclude", nargs="*", default=[])
    p_check.add_argument("--follow-symlinks", action="store_true", default=False,
                         help="Follow symlinks while scanning")

    # UPDATE
    p_update = sub.add_parser("update", help="Update baseline safely")
    p_update.add_argument("target", help="Directory to scan")
    p_update.add_argument("--config", help="YAML config file", default=None)
    p_update.add_argument("--baseline", help="Baseline file", default=None)
    p_update.add_argument("--log", help="Log file", default=None)
    p_update.add_argument("--exclude", nargs="*", default=[])
    p_update.add_argument("--follow-symlinks", action="store_true", default=False,
                          help="Follow symlinks while scanning")
    p_update.add_argument("-y", "--yes", action="store_true", default=False,
                          help="Auto-confirm baseline updates (non-interactive)")

    # WATCH
    p_watch = sub.add_parser("watch", help="Watch target for real-time changes")
    p_watch.add_argument("target", help="Directory to watch")
    p_watch.add_argument("--config", help="YAML config file", default=None)
    p_watch.add_argument("--baseline", help="Baseline file", default=None)
    p_watch.add_argument("--log", help="Log file", default=None)
    p_watch.add_argument("--exclude", nargs="*", default=[])

    return parser


# ===========================
# MAIN
# ===========================

def main():
    args = build_cli().parse_args()

    if args.command == "init":
        init_command(args)
    elif args.command == "check":
        check_command(args)
    elif args.command == "update":
        update_command(args)
    elif args.command == "watch":
        watch_command(args)
    else:
        print("Unknown command")


if __name__ == "__main__":
    main()
