import hashlib
from pathlib import Path
from typing import Optional

CHUNK_SIZE = 8192  # 8 KB chunks (safe for large files)

def hash_file(path: Path) -> Optional[str]:
    """
    Returns SHA-256 hash of the file at 'path'.
    Returns None if file can't be read (permissions, etc.).
    """
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()

    except (PermissionError, FileNotFoundError, IsADirectoryError):
        return None
