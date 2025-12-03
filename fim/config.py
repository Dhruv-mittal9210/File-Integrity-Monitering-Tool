import yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "target": ".",
    "baseline": "baseline.json",
    "log": "changes_log.jsonl",
    "exclude": []
}

def load_config(path: Path) -> dict:
    # If config file missing → return defaults
    if not path.exists():
        return DEFAULT_CONFIG.copy()

    # Load YAML
    with path.open("r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    # Merge defaults with user config
    final_config = DEFAULT_CONFIG.copy()
    final_config.update(user_config)

    return final_config
