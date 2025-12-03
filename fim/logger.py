import json
from datetime import datetime
from pathlib import Path

def append_log(path: Path, event: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    event["timestamp"] = datetime.utcnow().isoformat() + "Z"

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
