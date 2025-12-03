BASELINE_SCHEMA_VERSION = 1

def build_baseline_structure(target: str, files: dict) -> dict:
    from datetime import datetime

    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "target": target,
        "hash_algo": "sha256",
        "files": files,
    }
