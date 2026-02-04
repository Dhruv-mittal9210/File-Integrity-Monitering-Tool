# File Integrity Monitoring Tool - AI Coding Instructions

## Project Overview
A Python-based **file integrity monitoring (FIM) tool** that creates baselines of directory contents and detects changes. It supports two modes:
- **Check mode**: One-time scan against baseline
- **Watch mode**: Real-time monitoring via `watchdog` library

## Architecture

### Core Data Flow
1. **Scan** ([fim/scanner.py](fim/scanner.py)) → Directory traversal with hash computation
2. **Compare** ([fim/comparator.py](fim/comparator.py)) → Detect created/modified/deleted files
3. **Log** ([fim/logger.py](fim/logger.py)) → Append JSONL change events
4. **Storage** ([fim/storage/json_store.py](fim/storage/json_store.py)) → Persistent baselines and logs

### Key Components

- **Scanner** ([fim/scanner.py](fim/scanner.py)): Recursively walks directories, computes SHA-256 hashes, supports gitignore-like glob exclusions with negation patterns (`!pattern`)
- **Comparator** ([fim/comparator.py](fim/comparator.py)): Stateless function comparing old vs. new file metadata (hash-based detection)
- **Watch** ([fim/watch.py](fim/watch.py)): Event-driven handler using `watchdog` Observer; idempotent (same event twice → same outcome)
- **CLI** ([fim/cli.py](fim/cli.py)): Entry point; commands: `init`, `check`, `watch`, `tail`
- **Config** ([fim/config.py](fim/config.py)): YAML-based with priority: **Defaults ← YAML file ← CLI args**

### Data Structures

**Baseline (JSON)**:
```json
{
  "schema_version": 1,
  "created_at": "2025-01-30T...",
  "target": "/full/path",
  "hash_algo": "sha256",
  "files": {
    "relative/path.txt": { "hash": "...", "size": 1234, "mtime": 1700000000 }
  }
}
```

**Change Log (JSONL)** - One JSON object per line:
```json
{ "timestamp": "2025-01-30T...", "event": "init|check|watch_event", ... }
```

## Critical Patterns & Conventions

### Error Handling
- **Graceful degradation**: Unreadable/permission-denied files are **logged and skipped**, never fatal ([hasher.py](fim/hasher.py#L12))
- **Hashing failures return `None`**; caller checks and skips ([scanner.py](fim/scanner.py#L70))
- Watch mode **retries once on unreadable** before logging change ([watch.py](fim/watch.py#L40))
- Use `_build_file_meta()` in watch mode to safely handle missing/unreadable files; returns `(meta, unreadable_flag)` tuple ([watch.py](fim/watch.py#L88))

### Path Normalization
- **Always use `normalize_rel_path()`** for dictionary keys ([utils.py](fim/utils.py#L8))
- On Windows: lowercase + forward slashes; on Unix: forward slashes only
- For safety checks: use `is_path_within()` which handles case-insensitive filesystems ([utils.py](fim/utils.py#L20))

### Configuration Merging
- Settings use **3-tier priority**: hardcoded defaults < config.yml < CLI args
- CLI `--exclude` may come as list-of-lists from argparse; flatten via `_flatten_exclude()` ([cli.py](fim/cli.py#L16))
- Config path defaults to `config.yml` in working directory; missing file → use defaults

### Watch Mode Design
Watch is **stateless and idempotent**:
- Never rebuilds baseline in watch mode
- Each event independently compared to baseline
- Duplicate events handled gracefully (e.g., rapid file writes)
- Default watch log saved OUTSIDE watched directory ([utils.py](fim/utils.py#L35)) to avoid self-monitoring loops
- **Event normalization**: Raw watchdog events (MOVED, CREATED, MODIFIED, DELETED) normalized to explicit security events via `normalize_event()` ([watch.py](fim/watch.py#L60)); MOVED becomes DELETE+CREATE
- **Single-file comparison**: `CompareResult` dataclass ([watch.py](fim/watch.py#L30)) encapsulates change_type (created/modified/deleted), metadata, and unreadable flag
- **Double-check pattern**: On permission errors, retry once with fresh stat/hash before reporting as unreadable

### Exclusion Patterns
Supports fnmatch-style globs with **negation**:
```
patterns = ["*.pyc", "__pycache__", "!keep_this.pyc"]
```
Patterns checked **in order**; negation (`!`) un-excludes if it matches later. Both scanner and watch mode use `_matches_exclude_patterns()` ([scanner.py](fim/scanner.py#L8)) for consistent behavior.

## Developer Workflows

### Run CLI Locally
```bash
# Create baseline
python -m fim init --target . --baseline my_baseline.json

# Check for changes
python -m fim check --baseline my_baseline.json --log changes.jsonl

# Watch in real-time (with fallback to polling on network drives)
python -m fim watch --baseline my_baseline.json

# Stream recent log entries
python -m fim tail --log changes.jsonl
```

### Run Tests
```bash
pytest tests/  # Unit tests for scanner, comparator, hasher
pytest -v      # Verbose output
```

### Test Patterns
- Use `tmp_path` fixture for isolated file creation ([test_scanner.py](tests/test_scanner.py))
- Minimal test cases: create files, assert metadata keys exist ([test_comparator.py](tests/test_comparator.py))
- No external dependencies in tests; all fixtures are in-memory
- Test exclusion patterns with both positive and negation rules

## Dependencies & Integrations

- **watchdog** ([fim/watch.py](fim/watch.py)): File system event monitoring; falls back to polling on some drives
- **PyYAML** ([fim/config.py](fim/config.py)): Config parsing
- **pytest**: Test runner (in `requirements.txt`)
- **logging**: Standard library; initialized in `__main__.py` with ISO timestamps

## Code Style & Practices

- **Type hints**: Optional but encouraged (seen in [cli.py](fim/cli.py), [scanner.py](fim/scanner.py))
- **Docstrings**: Use for public functions; explain non-obvious behavior (e.g., exclusion rules)
- **Logging**: Use module-level `logger = logging.getLogger(__name__)` ([hasher.py](fim/hasher.py#L4))
- **Pathlib**: Prefer `Path` over `os.path` for modern Python
- **Settings priority**: Always respect YAML ← CLI ordering when adding features

## Integration Points for Extensions

- **New storage backends**: Implement interface in [fim/storage/](fim/storage/) (swap `json_store.py`)
- **Custom comparators**: Extend [fim/comparator.py](fim/comparator.py) to add new change detection logic
- **Watch mode custom handlers**: Subclass `FileSystemEventHandler` in [fim/watch.py](fim/watch.py#L24)
- **New CLI commands**: Add command function in [fim/cli.py](fim/cli.py), register in argparse

## Quick Reference
| File | Purpose |
|------|---------|
| `fim/scanner.py` | Directory walk + hash computation |
| `fim/comparator.py` | Baseline diff logic |
| `fim/watch.py` | Real-time monitoring (watchdog-based) |
| `fim/cli.py` | Command-line interface (init/check/watch/tail) |
| `fim/config.py` | YAML config + default merging |
| `fim/storage/json_store.py` | Baseline/log persistence |
| `fim/logger.py` | JSONL change event append |
| `fim/utils.py` | Path normalization & helpers |
| `tests/` | Unit tests for core modules |
