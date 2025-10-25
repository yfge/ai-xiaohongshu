"""In-memory rate limiter keyed by API key id."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class RateConfig:
    window_seconds: int
    max_requests: int


class RateLimiter:
    def __init__(self, config: RateConfig) -> None:
        self._config = config
        # key -> (window_reset_epoch_s, count)
        self._buckets: dict[str, tuple[float, int]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        win = float(max(1, self._config.window_seconds))
        max_req = max(1, self._config.max_requests)
        reset, count = self._buckets.get(key, (now + win, 0))
        if now >= reset:
            # new window
            reset = now + win
            count = 0
        if count + 1 > max_req:
            # deny; keep old window
            self._buckets[key] = (reset, count)
            return False
        self._buckets[key] = (reset, count + 1)
        return True

