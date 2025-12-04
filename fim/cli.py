#!/usr/bin/env python3
"""
CLI entrypoint for the FIM project.

Usage examples:
  python -m fim init . --config examples/config.example.yml
  python -m fim check . --exclude __pycache__ --log mylog.jsonl
"""

import argparse
from pathlib import Path
from typing import Any

from .scanner import scan_directory
from .storage.json_store import save_json, load_json
from .schema import build_baseline_structure
from .comparator import compare_baseline
from .logger import append_log
from .settings import build_settings

import shutil
from datetime import datetime

def update_command(args: Any) -> None:

    settings = build_settings(args, args.config)
    target = settings["target"]
    baseline_path = Path(settings["baseline"])
    log_path = Path(settings["log"])
    exclude = settings.get("exclude", [])

    # Load baseline
    old_baseline = load_json(baseline_path)
    if old_baseline is None:
        print(f"ERROR: Baseline not found at: {baseline_path}. Create one with `fim init` first.")
        return

    # Scan current state
    print(f"Scanning current directory state: {target}")
    new_files = scan_directory(Path(target), exclude=exclude)

    # Compare
    changes = compare_baseline(old_baseline.get("files", {}), new_files)
    created = changes.get("created", [])
    deleted = changes.get("deleted", [])
    modified = changes.get("modified", [])

    if not (created or deleted or modified):
        print("No changes detected. Baseline is up-to-date. Nothing to update.")
        return

    # Show user the changes that will be applied
    print("\n=== Proposed baseline update (these changes will be accepted) ===")
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

    # Ask for confirmation
    ans = input("\nApply these changes to the baseline? (y/N): ").strip().lower()
    if ans not in ("y", "yes"):
        print("Update cancelled by user. Baseline unchanged.")
        return

    # Backup old baseline (timestamped)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_path = baseline_path.with_name(f"{baseline_path.name}.bak.{ts}")
    try:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline_path, backup_path)
        print(f"Backup created: {backup_path}")
    except Exception as e:
        print(f"WARNING: could not create baseline backup: {e}")
        # Decide: continue or abort? We'll abort to be safe.
        print("Aborting update to avoid accidental data loss.")
        return

    # Write the new baseline (use the same schema builder)
    new_baseline = build_baseline_structure(str(Path(target).resolve()), new_files)
    save_json(baseline_path, new_baseline)
    print(f"Baseline updated and saved to {baseline_path}")

    # Log update event
    append_log(log_path, {
        "event": "baseline_update",
        "target": str(Path(target).resolve()),
        "backup": str(backup_path),
        "created": created,
        "modified": modified,
        "deleted": deleted
    })
    print(f"Update event logged to {log_path}")

def init_command(args: Any) -> None:
    """
    Create a baseline based on settings (defaults <- config <- CLI).
    """
    settings = build_settings(args, args.config)

    target = settings["target"]
    baseline_path = Path(settings["baseline"])
    exclude = settings.get("exclude", [])

    print(f"Scanning directory: {target}")
    files = scan_directory(Path(target), exclude=exclude)

    print(f"Found {len(files)} files. Building baseline...")
    baseline = build_baseline_structure(str(Path(target).resolve()), files)

    save_json(baseline_path, baseline)
    print(f"Baseline saved to {baseline_path}")


def check_command(args: Any) -> None:
    """
    Check current directory state against baseline and log any changes.
    """
    settings = build_settings(args, args.config)

    target = settings["target"]
    baseline_path = Path(settings["baseline"])
    log_path = Path(settings["log"])
    exclude = settings.get("exclude", [])

    baseline = load_json(baseline_path)
    if baseline is None:
        print(f"ERROR: Baseline not found at: {baseline_path}")
        return

    print(f"Scanning current directory state: {target}")
    new_files = scan_directory(Path(target), exclude=exclude)

    print("Comparing with baseline...")
    changes = compare_baseline(baseline.get("files", {}), new_files)

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

    # Append to JSONL log
    append_log(log_path, {
        "target": str(Path(target).resolve()),
        "created": created,
        "modified": modified,
        "deleted": deleted
    })

    print(f"\nLogged to {log_path}")


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fim", description="File Integrity Monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    # update subcommand
    p_update = sub.add_parser("update", help="Update baseline after reviewing changes")
    p_update.add_argument("target", help="Directory to scan")
    p_update.add_argument("--config", help="Path to YAML config file", default=None)
    p_update.add_argument("--baseline", help="Path to baseline JSON file", default=None)
    p_update.add_argument("--log", help="Path to JSONL log file", default=None)
    p_update.add_argument(
        "--exclude",
        nargs="*",
        action="append",
        help="Exclude patterns (can be passed multiple times)",
        default=None,
    )


    # init subcommand
    p_init = sub.add_parser("init", help="Create baseline JSON for a directory")
    p_init.add_argument("target", help="Directory to scan")
    p_init.add_argument("--config", help="Path to YAML config file", default=None)
    p_init.add_argument("--baseline", help="Path to baseline JSON file", default=None)
    p_init.add_argument("--log", help="Path to JSONL log file", default=None)
    p_init.add_argument(
        "--exclude",
        nargs="*",
        action="append",
        help="Exclude patterns (can be passed multiple times)",
        default=None,
    )

    # check subcommand
    p_check = sub.add_parser("check", help="Compare current state with baseline")
    p_check.add_argument("target", help="Directory to scan")
    p_check.add_argument("--config", help="Path to YAML config file", default=None)
    p_check.add_argument("--baseline", help="Path to baseline JSON file", default=None)
    p_check.add_argument("--log", help="Path to JSONL log file", default=None)
    p_check.add_argument(
        "--exclude",
        nargs="*",
        action="append",
        help="Exclude patterns (can be passed multiple times)",
        default=None,
    )

    return parser


def main() -> None:
    parser = build_cli()
    args = parser.parse_args()

    if args.command == "init":
        init_command(args)
    elif args.command == "check":
        check_command(args)
    else:
        parser.print_help()
        
    if args.command == "init":
        init_command(args)
    elif args.command == "check":
        check_command(args)
    elif args.command == "update":
        update_command(args)
    else:
        parser.print_help()



if __name__ == "__main__":
    main()
