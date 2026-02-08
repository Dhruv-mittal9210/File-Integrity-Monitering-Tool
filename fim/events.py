from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class FileEvent:
    event_type: str  # CREATED | MODIFIED | DELETED
    path: str
    hash_before: Optional[str]
    hash_after: Optional[str]
    timestamp: datetime
