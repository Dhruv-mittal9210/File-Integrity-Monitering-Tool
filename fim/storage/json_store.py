import json
from pathlib import Path
from typing import Optional

def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)
