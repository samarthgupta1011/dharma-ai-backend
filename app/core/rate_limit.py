"""
app/core/rate_limit.py
──────────────────────
In-memory sliding-window rate limiter as a FastAPI dependency.

Usage:
    from app.core.rate_limit import RateLimiter

    @router.post("/waitlist", dependencies=[Depends(RateLimiter(max_calls=5, window_seconds=60))])
    async def join_waitlist(...): ...

No external dependencies (Redis, etc.) required. Suitable for a
single-instance Container App deployment. If scaling horizontally,
replace with a Redis-backed limiter.
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status


class RateLimiter:
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_calls: int = 5, window_seconds: int = 60):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 300  # purge stale entries every 5 min

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        with self._lock:
            # Periodic cleanup of expired entries to prevent memory leak
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup(now)
                self._last_cleanup = now

            # Remove timestamps outside the current window
            cutoff = now - self.window_seconds
            self._hits[client_ip] = [
                t for t in self._hits[client_ip] if t > cutoff
            ]

            if len(self._hits[client_ip]) >= self.max_calls:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                )

            self._hits[client_ip].append(now)

    def _cleanup(self, now: float) -> None:
        """Remove IPs with no recent hits to prevent unbounded memory growth."""
        cutoff = now - self.window_seconds
        stale_keys = [
            ip for ip, timestamps in self._hits.items()
            if not timestamps or timestamps[-1] <= cutoff
        ]
        for key in stale_keys:
            del self._hits[key]
