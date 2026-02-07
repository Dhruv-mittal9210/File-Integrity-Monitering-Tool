# File Integrity Monitoring Tool - AI Coding Instructions

## Project Overview
A Python-based file integrity monitoring (FIM) tool that creates baselines of directory contents and detects changes. It supports four CLI commands:
- `init`: one-time baseline creation
- `check`: one-time scan against baseline
- `update`: safely update baseline with backup
- `watch`: real-time monitoring via `watchdog`

There is also a Windows Service wrapper that loads `baseline.json` and runs watch mode in a background thread.

## Architecture

### Core Data Flow (Init/Check/Update)
1. **Scan** (`fim/scanner.py`) -> directory traversal with hash computation
2. **Baseline** (`fim/schema.py`) -> build baseline structure + timestamps
3. **Compare** (`fim/comparator.py`) -> detect created/modified/deleted
4. **Log** (`fim/logger.py`) -> append JSONL change events
5. **Storage** (`fim/storage/json_store.py`) -> persistent baseline and logs

### Core Data Flow (Watch)
1. **WatchHandler** (`fim/watch.py`) -> debounce + normalize events
2. **Compare one file** (`compare_file` in `fim/watch.py`)
3. **Log** (`fim/logger.py`) -> JSONL, one event per decision

### Key Components
- **Scanner** (`fim/scanner.py`): recursive walk, SHA-256 hashing, exclude patterns with `!` negation
- **Comparator** (`fim/comparator.py`): stateless baseline diff
- **Watch** (`fim/watch.py`): event-driven handler with debounce, retry-on-unreadable
- **CLI** (`fim/cli.py`): `init`, `check`, `update`, `watch`
- **Settings** (`fim/settings.py`): merges defaults <- YAML <- CLI args
- **Config** (`fim/config.py`): YAML parsing + defaults
- **Schema** (`fim/schema.py`): baseline structure and version
- **Service** (`fim/service.py`): Windows Service; loads baseline + starts watch thread
- **Storage** (`fim/storage/json_store.py`): JSON persistence
- **Logger** (`fim/logger.py`): JSONL change events
- **Utils** (`fim/utils.py`): path normalization + safe log locations

## Data Structures

**Baseline (JSON)**:
```json
{
  "schema_version": 1,
  "created_at": "2026-02-06T...",
  "target": "C:/full/path",
  "hash_algo": "sha256",
  "files": {
    "relative/path.txt": { "hash": "...", "size": 1234, "mtime": 1700000000 }
  }
}
```

**Change Log (JSONL)** - one JSON object per line:
```json
{ "timestamp": "2026-02-06T...", "event": "init|check|baseline_update|watch", ... }
```

## Critical Patterns & Conventions

### Error Handling
- `hash_file()` returns `None` on any failure; caller skips file (logs warning).
- Scanner skips unreadable files (permission/IO errors).
- Watch mode uses `_build_file_meta()`; unreadable files return `(None, True)`.
- Watch mode retries once on unreadable before reporting (debounced retry).

### Path Normalization
- Always use `normalize_rel_path()` for baseline keys (lowercase, forward slashes).
- Use `is_path_within()` to prevent writing watch logs inside the watched tree.

### Configuration Merging
- Settings priority: defaults <- `config.yml` <- CLI args (non-None).
- CLI `--exclude` may be list-of-lists; normalize with `_flatten_exclude()` in `fim/cli.py`.

### Watch Mode Design
Watch is stateless and idempotent:
- Baseline is source of truth; never rebuilt in watch.
- Each event is normalized (`normalize_event`).
- `compare_file()` performs the single-file decision.
- Debounce per path avoids noisy Windows events.
- Default watch log path is outside the watched tree (`default_watch_log_path`).
- If user-supplied `--log` is inside the watched tree, refuse and exit.

### Windows Service Notes
- `fim/service.py` must remain safe when started by SCM (no package context).
- The service bootstraps the project root into `sys.path` before `fim.*` imports.
- Service uses a supervisor thread to restart `watch()` if the watch thread dies.
- Keep `fim/__init__.py` side-effect-free to avoid importing CLI/config (and PyYAML) in service context.

### Baseline Update Workflow
- `update` compares current state vs baseline.
- Creates backup `baseline.json.bak.<UTC timestamp>` before overwriting.
- Prompts for confirmation unless `--yes` is provided.

## Developer Workflows

### Run CLI Locally
```bash
# Create baseline
python -m fim init --target . --baseline baseline.json

# Check for changes
python -m fim check --baseline baseline.json --log changes_log.jsonl

# Update baseline safely
python -m fim update --baseline baseline.json --log changes_log.jsonl

# Watch in real-time
python -m fim watch --baseline baseline.json
```

### Run Tests
```bash
pytest tests/
pytest -v
```

### Test Patterns
- `tmp_path` fixture for isolated files.
- `test_watch.py` exercises `normalize_event`, `normalize_rel_path`, and `compare_file`.
- `tests/` covers scanner and comparator behavior.

## Dependencies & Integrations
- `watchdog` (`fim/watch.py`): file system event monitoring
- `PyYAML` (`fim/config.py`): config parsing
- `pywin32` (`fim/service.py`): Windows service framework
- `pytest`: test runner
- `logging`: standard library; configured in `fim/__main__.py`

## Code Style & Practices
- Type hints are encouraged (see `fim/watch.py`, `fim/cli.py`).
- Use `Path` from `pathlib`.
- Keep watch logic pure and stateless; all side effects live in handlers/loggers.

## Integration Points for Extensions
- New storage backends: add modules under `fim/storage/`.
- Custom comparators: extend `fim/comparator.py` or add new compare strategies.
- Watch mode custom handlers: subclass `FileSystemEventHandler` in `fim/watch.py`.
- New CLI commands: add in `fim/cli.py`, register in argparse.

## Quick Reference
| File | Purpose |
|------|---------|
| `fim/scanner.py` | Directory walk + hash computation |
| `fim/comparator.py` | Baseline diff logic |
| `fim/watch.py` | Real-time monitoring (watchdog-based) |
| `fim/cli.py` | Command-line interface (init/check/update/watch) |
| `fim/settings.py` | Settings merge: defaults <- config <- CLI |
| `fim/config.py` | YAML config + defaults |
| `fim/schema.py` | Baseline structure/version |
| `fim/storage/json_store.py` | Baseline/log persistence |
| `fim/logger.py` | JSONL change event append |
| `fim/utils.py` | Path normalization & helpers |
| `fim/service.py` | Windows Service wrapper (loads baseline, starts watch) |
| `tests/` | Unit tests for core modules |
| `test_watch.py` | Watch-mode focused tests |
