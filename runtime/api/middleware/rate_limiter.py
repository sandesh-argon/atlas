"""
Rate Limiting Middleware

Prevents API abuse with per-IP request limits.

Limits:
- 100 requests/minute per IP
- 1000 requests/hour per IP
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from collections import OrderedDict
from typing import Dict, List
import time
from ..config import (
    RATE_LIMIT_PER_HOUR,
    RATE_LIMIT_PER_MINUTE,
    RATE_LIMIT_MAX_TRACKED_IPS,
    RATE_LIMIT_EVICT_FRACTION,
)
from .client_ip import get_client_ip


class RateLimiter:
    """In-memory rate limiter with sliding window."""

    def __init__(
        self,
        requests_per_minute: int = RATE_LIMIT_PER_MINUTE,
        requests_per_hour: int = RATE_LIMIT_PER_HOUR,
        max_tracked_ips: int = RATE_LIMIT_MAX_TRACKED_IPS,
        evict_fraction: float = RATE_LIMIT_EVICT_FRACTION,
    ):
        self.rpm_limit = requests_per_minute
        self.rph_limit = requests_per_hour
        self.max_tracked_ips = max(100, max_tracked_ips)
        self.evict_fraction = min(0.5, max(0.01, evict_fraction))
        self.minute_requests: "OrderedDict[str, List[float]]" = OrderedDict()
        self.hour_requests: "OrderedDict[str, List[float]]" = OrderedDict()

    def _ensure_ip(self, ip: str) -> None:
        if ip not in self.minute_requests:
            self.minute_requests[ip] = []
        if ip not in self.hour_requests:
            self.hour_requests[ip] = []

    def _touch_ip(self, ip: str) -> None:
        self.minute_requests.move_to_end(ip)
        self.hour_requests.move_to_end(ip)

    def _evict_if_needed(self) -> None:
        if len(self.minute_requests) <= self.max_tracked_ips:
            return
        over_by = len(self.minute_requests) - self.max_tracked_ips
        evict_count = max(int(self.max_tracked_ips * self.evict_fraction), over_by, 1)
        for _ in range(min(evict_count, len(self.minute_requests))):
            oldest_ip, _ = self.minute_requests.popitem(last=False)
            self.hour_requests.pop(oldest_ip, None)

    def _clean_old_requests(self, ip: str) -> None:
        """Remove requests older than their respective windows."""
        now = time.time()

        # Clean minute window (keep last 60 seconds)
        self.minute_requests[ip] = [
            ts for ts in self.minute_requests.get(ip, [])
            if now - ts < 60
        ]

        # Clean hour window (keep last 3600 seconds)
        self.hour_requests[ip] = [
            ts for ts in self.hour_requests.get(ip, [])
            if now - ts < 3600
        ]

        # Drop empty tracked keys to keep memory bounded.
        if not self.minute_requests.get(ip) and not self.hour_requests.get(ip):
            self.minute_requests.pop(ip, None)
            self.hour_requests.pop(ip, None)

    def check_rate_limit(self, ip: str) -> bool:
        """
        Check if IP has exceeded rate limits.

        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        self._ensure_ip(ip)
        self._touch_ip(ip)
        self._evict_if_needed()
        self._clean_old_requests(ip)

        # Check minute limit
        if len(self.minute_requests.get(ip, [])) >= self.rpm_limit:
            return False

        # Check hour limit
        if len(self.hour_requests.get(ip, [])) >= self.rph_limit:
            return False

        # Add current request
        self.minute_requests.setdefault(ip, []).append(now)
        self.hour_requests.setdefault(ip, []).append(now)

        return True

    def get_remaining(self, ip: str) -> Dict[str, int]:
        """Get remaining requests for an IP."""
        self._clean_old_requests(ip)
        return {
            "minute": max(0, self.rpm_limit - len(self.minute_requests.get(ip, []))),
            "hour": max(0, self.rph_limit - len(self.hour_requests.get(ip, [])))
        }

    def reset(self, ip: str = None) -> None:
        """Reset rate limits (for testing)."""
        if ip:
            self.minute_requests[ip] = []
            self.hour_requests[ip] = []
        else:
            self.minute_requests.clear()
            self.hour_requests.clear()


# Global rate limiter instance (wired to environment config)
rate_limiter = RateLimiter(
    requests_per_minute=RATE_LIMIT_PER_MINUTE,
    requests_per_hour=RATE_LIMIT_PER_HOUR,
    max_tracked_ips=RATE_LIMIT_MAX_TRACKED_IPS,
    evict_fraction=RATE_LIMIT_EVICT_FRACTION,
)


async def rate_limit_middleware(request: Request, call_next):
    """Middleware to enforce rate limits."""

    client_ip = get_client_ip(request)

    # Skip rate limiting for health checks
    if request.url.path in {"/health", "/health/detailed"}:
        return await call_next(request)

    # Check rate limit
    if not rate_limiter.check_rate_limit(client_ip):
        remaining = rate_limiter.get_remaining(client_ip)
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please try again later.",
                "limits": {
                    "per_minute": rate_limiter.rpm_limit,
                    "per_hour": rate_limiter.rph_limit
                },
                "remaining": remaining
            },
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit-Minute": str(rate_limiter.rpm_limit),
                "X-RateLimit-Limit-Hour": str(rate_limiter.rph_limit),
                "X-RateLimit-Remaining-Minute": str(remaining["minute"]),
                "X-RateLimit-Remaining-Hour": str(remaining["hour"]),
            }
        )

    # Process request
    response = await call_next(request)

    # Add rate limit headers to successful responses
    remaining = rate_limiter.get_remaining(client_ip)
    response.headers["X-RateLimit-Limit-Minute"] = str(rate_limiter.rpm_limit)
    response.headers["X-RateLimit-Limit-Hour"] = str(rate_limiter.rph_limit)
    response.headers["X-RateLimit-Remaining-Minute"] = str(remaining["minute"])
    response.headers["X-RateLimit-Remaining-Hour"] = str(remaining["hour"])

    return response
