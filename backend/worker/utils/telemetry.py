from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime
from threading import Lock
from typing import Any


class TelemetryStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._last_event_at: dict[str, str] = {}
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=50)

    def record(self, event: str, **fields: Any) -> None:
        timestamp = datetime.now(UTC).isoformat()
        key_parts = [event]
        for name in sorted(fields):
            value = fields[name]
            if value in (None, "", [], {}):
                continue
            key_parts.append(f"{name}={value}")
        counter_key = "|".join(key_parts)
        with self._lock:
            self._counters[counter_key] += 1
            self._last_event_at[event] = timestamp
            self._recent_events.append(
                {
                    "timestamp": timestamp,
                    "event": event,
                    **fields,
                }
            )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(sorted(self._counters.items())),
                "last_event_at": dict(self._last_event_at),
                "recent_events": list(self._recent_events),
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._last_event_at.clear()
            self._recent_events.clear()


telemetry = TelemetryStore()
