from pathlib import Path
import hashlib
from typing import Optional
import logging

logger = logging.getLogger(__name__)

def hash_file(path: Path) -> Optional[str]:
    """
    Compute SHA-256 of a file. Returns hex digest string on success,
    or None on failure (permission error, IO error, etc).
    """
    try:
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        # Log a warning but don't raise — caller will skip the file.
        logger.warning("Failed to hash %s: %s", path, e)
        return None
