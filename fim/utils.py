from pathlib import Path

def resolve_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()
