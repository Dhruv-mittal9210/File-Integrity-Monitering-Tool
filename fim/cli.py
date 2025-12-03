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


if __name__ == "__main__":
    main()
