from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_call(
    fn: Callable[[], T],
    attempts: int,
    backoff_seconds: float,
    max_backoff_seconds: float | None = None,
    jitter_ratio: float = 0.2,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as exc:  # type: ignore[misc]
            last_error = exc
            if attempt >= attempts:
                break
            sleep_for = backoff_seconds * (2 ** (attempt - 1))
            if max_backoff_seconds is not None:
                sleep_for = min(sleep_for, max_backoff_seconds)
            if jitter_ratio > 0:
                jitter = sleep_for * jitter_ratio
                sleep_for += random.uniform(-jitter, jitter)
            time.sleep(max(0, sleep_for))
    assert last_error is not None
    raise last_error
