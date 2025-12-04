import os
from pathlib import Path
from typing import Dict, List
from fnmatch import fnmatch

from .hasher import hash_file

def _matches_exclude_patterns(rel_path: str, patterns: List[str]) -> bool:
    """
    Return True if rel_path should be excluded according to patterns.
    Supports simple glob patterns (fnmatch) and negation with leading '!'.
    Rules:
      - Patterns are checked in order. A matching positive pattern excludes the path.
      - If a later negation pattern ('!pattern') matches, the path is included again.
    This is a simplified gitignore-like behavior.
    """
    if not patterns:
        return False

    excluded = False
    for pat in patterns:
        if pat == "":
            continue
        if pat.startswith("!"):
            neg = pat[1:]
            # if negation matches, un-exclude
            if fnmatch(rel_path, neg):
                excluded = False
        else:
            # positive match -> exclude
            if fnmatch(rel_path, pat):
                excluded = True
    return excluded

def scan_directory(target: Path, exclude: List[str] = None, follow_symlinks: bool = False) -> Dict[str, dict]:
    """
    Recursively scans a directory and returns a dictionary mapping relative
    paths to metadata:
    {
        "relative/path.txt": {
            "hash": "...",
            "size": 1234,
            "mtime": 1700000000
        },
        ...
    }

    exclude: list of glob patterns (fnmatch-style). Use '!pattern' to negate.
    follow_symlinks: whether to follow symlinks while walking.
    """
    if exclude is None:
        exclude = []

    results: Dict[str, dict] = {}
    target = target.resolve()

    for root, dirs, files in os.walk(target, followlinks=follow_symlinks):
        # root is absolute Path string
        for filename in files:
            file_path = Path(root) / filename
            try:
                rel_path = str(file_path.relative_to(target))
            except Exception:
                # if file not under target for some reason, skip
                continue

            # Skip excluded patterns (supports glob and simple negation)
            if _matches_exclude_patterns(rel_path, exclude):
                continue

            # Collect metadata
            try:
                stat = file_path.stat()
                file_hash = hash_file(file_path)

                if file_hash is None:
                    # unreadable or hashing failed — skip (hasher already logs)
                    continue

                results[rel_path] = {
                    "hash": file_hash,
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime)
                }

            except FileNotFoundError:
                # File disappeared mid-scan (rare but possible)
                continue
            except PermissionError:
                # If stat fails due to permissions, skip the file
                # (optionally log elsewhere)
                continue

    return results
