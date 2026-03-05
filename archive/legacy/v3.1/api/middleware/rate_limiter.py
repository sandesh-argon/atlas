"""
Rate Limiting Middleware

Prevents API abuse with per-IP request limits.

Limits:
- 100 requests/minute per IP
- 1000 requests/hour per IP
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from collections import defaultdict
from typing import Dict, List
import time


class RateLimiter:
    """In-memory rate limiter with sliding window."""

    def __init__(self, requests_per_minute: int = 100, requests_per_hour: int = 1000):
        self.rpm_limit = requests_per_minute
        self.rph_limit = requests_per_hour
        self.minute_requests: Dict[str, List[float]] = defaultdict(list)
        self.hour_requests: Dict[str, List[float]] = defaultdict(list)

    def _clean_old_requests(self, ip: str) -> None:
        """Remove requests older than their respective windows."""
        now = time.time()

        # Clean minute window (keep last 60 seconds)
        self.minute_requests[ip] = [
            ts for ts in self.minute_requests[ip]
            if now - ts < 60
        ]

        # Clean hour window (keep last 3600 seconds)
        self.hour_requests[ip] = [
            ts for ts in self.hour_requests[ip]
            if now - ts < 3600
        ]

    def check_rate_limit(self, ip: str) -> bool:
        """
        Check if IP has exceeded rate limits.

        Returns:
            True if request is allowed, False if rate limited
        """
        now = time.time()
        self._clean_old_requests(ip)

        # Check minute limit
        if len(self.minute_requests[ip]) >= self.rpm_limit:
            return False

        # Check hour limit
        if len(self.hour_requests[ip]) >= self.rph_limit:
            return False

        # Add current request
        self.minute_requests[ip].append(now)
        self.hour_requests[ip].append(now)

        return True

    def get_remaining(self, ip: str) -> Dict[str, int]:
        """Get remaining requests for an IP."""
        self._clean_old_requests(ip)
        return {
            "minute": max(0, self.rpm_limit - len(self.minute_requests[ip])),
            "hour": max(0, self.rph_limit - len(self.hour_requests[ip]))
        }

    def reset(self, ip: str = None) -> None:
        """Reset rate limits (for testing)."""
        if ip:
            self.minute_requests[ip] = []
            self.hour_requests[ip] = []
        else:
            self.minute_requests.clear()
            self.hour_requests.clear()


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """Middleware to enforce rate limits."""

    # Get client IP (handle proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    # Skip rate limiting for health checks
    if request.url.path == "/health":
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
                "X-RateLimit-Remaining-Hour": str(remaining["hour"])
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
