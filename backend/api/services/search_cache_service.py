from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    expires_at: datetime


class SearchCacheService:
    """Simple daily cache for dynamic quote searches.

    This cache is intentionally small and in-memory so we can optimize repeated
    searches without adding infrastructure now. The public API is kept simple so
    it can be swapped for Redis in the future without changing route handlers.
    """

    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def build_daily_key(self, namespace: str, payload: dict[str, Any]) -> str:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        return f"{namespace}:{today}:{digest}"

    def get(self, key: str) -> Any | None:
        now = datetime.now(UTC)
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return None
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        expires_at = datetime.now(UTC) + timedelta(seconds=max(1, ttl_seconds))
        with self._lock:
            self._entries[key] = CacheEntry(value=value, expires_at=expires_at)

