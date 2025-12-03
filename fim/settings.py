from pathlib import Path
from typing import Any, Dict, List, Optional
from .config import DEFAULT_CONFIG, load_config

def _to_list_arg(value: Optional[List[str]]) -> Optional[List[str]]:
    """
    Normalize CLI exclude arg handling.
    argparse may give None, a list of single string, or multiple entries.
    We want either None or a flat list.
    """
    if value is None:
        return None
    # if user passed multiple --exclude arguments, flatten them
    flat = []
    for v in value:
        if isinstance(v, list):
            flat.extend(v)
        else:
            flat.append(v)
    return flat

def build_settings(args: Any, config_path: Optional[str]) -> Dict[str, Any]:
    """
    Build final settings using priority:
      DEFAULTS <- config file <- CLI args (non-None)
    Args:
      args: argparse.Namespace (CLI arguments)
      config_path: explicit config file path (string) or None
    Returns:
      dict with keys: target, baseline, log, exclude
    """
    # 1) Load defaults and config file
    cfg_path = Path(config_path) if config_path else Path("config.yml")
    user_cfg = load_config(cfg_path) if cfg_path.exists() else DEFAULT_CONFIG.copy()

    final = DEFAULT_CONFIG.copy()
    final.update(user_cfg)  # config overrides defaults

    # 2) CLI overrides (only if provided / not None)
    # We expect CLI args named: target, baseline, log, exclude
    if hasattr(args, "target") and args.target:
        final["target"] = args.target

    if hasattr(args, "baseline") and args.baseline:
        final["baseline"] = args.baseline

    if hasattr(args, "log") and args.log:
        final["log"] = args.log

    # normalize exclude
    cli_excludes = None
    if hasattr(args, "exclude"):
        cli_excludes = _to_list_arg(args.exclude)

    if cli_excludes is not None:
        final["exclude"] = cli_excludes

    # ensure types: enforce exclude is a list
    final["exclude"] = final.get("exclude") or []

    return final
