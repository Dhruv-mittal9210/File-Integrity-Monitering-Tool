import os
from pathlib import Path
from typing import Union
from typing import Union
from pathlib import Path

def resolve_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def normalize_rel_path(p: Union[str, Path]) -> str:
    """
    Normalize relative paths for consistent dictionary keys.

    - Normalizes separators to forward slashes (replaces backslashes).
    - Normalizes case to lower-case (consistent across platforms).
    """
    s = str(p).replace("\\", "/")
    return s.lower()


def is_path_within(child: Path, parent: Path) -> bool:
    """
    True if `child` is inside `parent` (or equal), with Windows case normalization.
    Safe across different drives (returns False).
    """
    try:
        child_s = os.path.normcase(str(child.expanduser().resolve()))
        parent_s = os.path.normcase(str(parent.expanduser().resolve()))
        return os.path.commonpath([child_s, parent_s]) == parent_s
    except Exception:
        # e.g. ValueError on Windows when paths are on different drives
        return False


def default_watch_log_path(target: Path) -> Path:
    """
    Choose a default watch log path OUTSIDE the watched target.
    Uses a per-user writable directory on Windows.
    """
    # Prefer user-writable locations; ProgramData often requires elevation.
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))

    logs_dir = root / "fim" / "logs"
    # include target name to avoid collisions between different watched roots
    safe_name = target.name or "watch"
    return logs_dir / f"changes-{safe_name}.jsonl"
