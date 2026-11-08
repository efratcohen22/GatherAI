"""In-process sliding-window limiter (see DECISIONS D6)."""
import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock

from fastapi import HTTPException, Request, status

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def reset_rate_limits() -> None:
    with _lock:
        _hits.clear()


def rate_limit(scope: str, limit: int, window_seconds: int = 60) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        key = f"{scope}:{request.client.host if request.client else 'unknown'}"
        now = time.monotonic()
        with _lock:
            hits = _hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please try again shortly.")
            hits.append(now)

    return dependency
