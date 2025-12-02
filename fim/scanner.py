import os
from pathlib import Path
from .hasher import hash_file

def scan_directory(target: Path, exclude: list[str] = None):
    """
    Recursively scans a directory and returns a dictionary of:
    {
        "relative/path.txt": {
            "hash": "...",
            "size": 1234,
            "mtime": 1700000000
        },
        ...
    }
    """
    if exclude is None:
        exclude = []

    results = {}
    target = target.resolve()

    for root, dirs, files in os.walk(target):
        for filename in files:
            file_path = Path(root) / filename
            rel_path = file_path.relative_to(target)

            # Skip excluded patterns
            if any(pattern in str(rel_path) for pattern in exclude):
                continue

            # Collect metadata
            try:
                stat = file_path.stat()
                file_hash = hash_file(file_path)

                if file_hash is None:
                    continue  # skip unreadable files

                results[str(rel_path)] = {
                    "hash": file_hash,
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime)
                }

            except FileNotFoundError:
                # File disappeared mid-scan (rare but possible)
                continue

    return results
