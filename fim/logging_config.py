from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from typing import Optional


_DEFAULT_MAX_BYTES = 5 * 1024 * 1024
_DEFAULT_BACKUP_COUNT = 5
_ENV_LOG_PATH = "FIM_LOG_PATH"


def get_logger(
    name: str,
    log_path: Optional[str] = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    backup_count: int = _DEFAULT_BACKUP_COUNT,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    resolved_path = log_path or os.environ.get(_ENV_LOG_PATH) or "fim.log"
    resolved_path = os.path.abspath(resolved_path)

    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and os.path.normcase(
            getattr(handler, "baseFilename", "")
        ) == os.path.normcase(resolved_path):
            return logger

    handler = RotatingFileHandler(
        resolved_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
