from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def log_event(settings: Any, level: str, message: str, **fields: Any) -> None:
    if level == "DEBUG" and not settings.debug:
        return

    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level,
        "message": message,
        **fields,
    }
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)
