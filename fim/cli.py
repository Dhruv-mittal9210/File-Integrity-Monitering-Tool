#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import Any
import shutil
from datetime import datetime

from .scanner import scan_directory
from .storage.json_store import save_json, load_json
from .schema import build_baseline_structure
from .comparator import compare_baseline
from .logger import append_log
from .settings import build_settings


# ===========================
# INIT COMMAND
# ===========================

def init_command(args: Any) -> None:
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


# ===========================
# CHECK COMMAND
# ===========================

def check_command(args: Any) -> None:
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
    settings = build_settings(args, args.config)

    target = settings["target"]
    baseline_path = Path(settings["baseline"])
    log_path = Path(settings["log"])
    exclude = settings.get("exclude", [])

    old_baseline = load_json(baseline_path)
    if old_baseline is None:
        print(f"ERROR: Baseline not found at {baseline_path}. Run `fim init` first.")
        return

    print(f"Scanning current directory state: {target}")
    new_files = scan_directory(Path(target), exclude=exclude)

    changes = compare_baseline(old_baseline.get("files", {}), new_files)

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

    confirm = input("\nApply these changes to baseline? (y/N): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Update cancelled.")
        return

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
    p_init.add_argument("--exclude", nargs="*", action="append", default=None)

    # CHECK
    p_check = sub.add_parser("check", help="Check integrity against baseline")
    p_check.add_argument("target", help="Directory to scan")
    p_check.add_argument("--config", help="YAML config file", default=None)
    p_check.add_argument("--baseline", help="Baseline file", default=None)
    p_check.add_argument("--log", help="Log file", default=None)
    p_check.add_argument("--exclude", nargs="*", action="append", default=None)

    # UPDATE
    p_update = sub.add_parser("update", help="Update baseline safely")
    p_update.add_argument("target", help="Directory to scan")
    p_update.add_argument("--config", help="YAML config file", default=None)
    p_update.add_argument("--baseline", help="Baseline file", default=None)
    p_update.add_argument("--log", help="Log file", default=None)
    p_update.add_argument("--exclude", nargs="*", action="append", default=None)

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
    else:
        print("Unknown command")


if __name__ == "__main__":
    main()
