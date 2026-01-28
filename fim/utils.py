import os
from pathlib import Path
from typing import Union

def resolve_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def normalize_rel_path(p: Union[str, Path]) -> str:
    """
    Normalize relative paths for consistent dictionary keys.

    - Normalizes separators to forward slashes via Path(...).as_posix()
    - On Windows, normalizes case (case-insensitive filesystem)
    """
    s = Path(p).as_posix()
    if os.name == "nt":
        return s.lower()
    return s
