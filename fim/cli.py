import argparse
from pathlib import Path

from .scanner import scan_directory
from .storage.json_store import save_json
from .schema import build_baseline_structure
from .config import DEFAULT_BASELINE_PATH
from .utils import resolve_path
from .storage.json_store import load_json
from .comparator import compare_baseline
from .logger import append_log



def init_command(target: str, baseline_path: str = None):
    target_path = resolve_path(target)

    if baseline_path:
        baseline_file = resolve_path(baseline_path)
    else:
        baseline_file = DEFAULT_BASELINE_PATH

    print(f"Scanning directory: {target_path}")

    files = scan_directory(target_path)

    print(f"Found {len(files)} files. Building baseline...")

    baseline = build_baseline_structure(str(target_path), files)

    save_json(baseline_file, baseline)

    print(f"Baseline saved to {baseline_file}")


def build_cli():
    parser = argparse.ArgumentParser(prog="fim", description="File Integrity Monitor")

    sub = parser.add_subparsers(dest="command", required=True)

    # init command
    p_init = sub.add_parser("init", help="Create baseline JSON for a directory")
    p_init.add_argument("target", help="Directory to scan")
    p_init.add_argument("--baseline", help="Path to baseline JSON file")

    # check command
    p_check = sub.add_parser("check", help="Compare current state with baseline")
    p_check.add_argument("target", help="Directory to scan")
    p_check.add_argument("--baseline", help="Path to baseline")
    p_check.add_argument("--log", help="Log file path", default="changes_log.jsonl")


    return parser


def main():
    parser = build_cli()
    args = parser.parse_args()

    if args.command == "init":
        init_command(args.target, args.baseline)
    
    if args.command == "check":
        check_command(args.target, args.baseline, args.log)


def check_command(target: str, baseline_path: str = None, log_path: str = "changes_log.jsonl"):
    target_path = resolve_path(target)

    # Baseline file
    baseline_file = resolve_path(baseline_path) if baseline_path else DEFAULT_BASELINE_PATH
    baseline = load_json(baseline_file)

    if baseline is None:
        print(f"ERROR: Baseline not found at: {baseline_file}")
        return

    print(f"Scanning current directory state: {target_path}")
    new_files = scan_directory(target_path)

    print("Comparing with baseline...")

    changes = compare_baseline(baseline["files"], new_files)

    created = changes["created"]
    deleted = changes["deleted"]
    modified = changes["modified"]

    # Human-readable output
    if not (created or deleted or modified):
        print("No changes detected. Everything is clean.")
    else:
        print("\n=== Changes Detected ===")
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

    # Log entry
    append_log(Path(log_path), {
        "target": str(target_path),
        "created": created,
        "modified": modified,
        "deleted": deleted
    })

    print(f"\nLogged to {log_path}") 

