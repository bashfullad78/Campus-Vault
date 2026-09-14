"""In-process sliding-window rate limiter.

V1 decision (vision.txt): Redis is deferred, so V1 ships a per-instance,
in-memory limiter applied to POST /auth/login, POST /auth/register and
POST /notes. It resets on restart and is not shared across workers; a
Redis-backed limiter replaces it in a later version.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from backend.config import settings

_PERIOD_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()
_calls_since_cleanup = 0


def _parse(limit: str) -> tuple[int, int]:
    """'5/minute' -> (5, 60). Raises ValueError on malformed specs."""
    try:
        count_text, _, period_text = limit.partition("/")
        count = int(count_text)
        seconds = _PERIOD_SECONDS[period_text.strip().lower()]
    except (ValueError, KeyError):
        raise ValueError(f"invalid rate limit spec: {limit!r}") from None
    if count <= 0:
        raise ValueError(f"rate limit must be positive: {limit!r}")
    return count, seconds


def rate_limit(limit: str, scope: str):
    """Dependency factory: allow `limit` requests per client IP per scope."""

    max_requests, period = _parse(limit)

    def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        global _calls_since_cleanup
        client_ip = request.client.host if request.client else "unknown"
        key = f"{scope}:{client_ip}"
        now = time.monotonic()

        with _lock:
            _calls_since_cleanup += 1
            if _calls_since_cleanup >= 10_000:
                # Occasional sweep so long-running instances don't grow forever.
                _calls_since_cleanup = 0
                stale = [k for k, w in _hits.items() if not w or w[-1] <= now - period]
                for k in stale:
                    del _hits[k]

            window = _hits[key]
            cutoff = now - period
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= max_requests:
                retry_after = max(1, int(window[0] + period - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )
            window.append(now)

    return dependency
