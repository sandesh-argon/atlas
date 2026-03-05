"""
Request Logging Middleware

Logs all API requests for debugging and auditing.
"""

import logging
import time
from pathlib import Path
from fastapi import Request
from typing import Callable
import json

# Ensure logs directory exists
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# File handler for API requests
file_handler = logging.FileHandler(LOG_DIR / "api_requests.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
))

# Create logger
request_logger = logging.getLogger("api.requests")
request_logger.addHandler(file_handler)
request_logger.addHandler(console_handler)
request_logger.setLevel(logging.INFO)


async def log_requests_middleware(request: Request, call_next: Callable):
    """Log all API requests with timing info."""

    start_time = time.time()

    # Get client IP
    forwarded = request.headers.get("X-Forwarded-For")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )

    # Log request
    log_entry = {
        "method": request.method,
        "path": request.url.path,
        "query": str(request.query_params) if request.query_params else None,
        "client_ip": client_ip,
        "user_agent": request.headers.get("User-Agent", "unknown")[:100]
    }

    # For POST requests, try to get body size
    if request.method == "POST":
        content_length = request.headers.get("Content-Length", "0")
        log_entry["content_length"] = content_length

    request_logger.info(f"Request: {json.dumps(log_entry)}")

    # Process request
    try:
        response = await call_next(request)
        duration = time.time() - start_time

        # Log response
        response_entry = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2)
        }

        if response.status_code >= 400:
            request_logger.warning(f"Response: {json.dumps(response_entry)}")
        else:
            request_logger.info(f"Response: {json.dumps(response_entry)}")

        # Add timing header
        response.headers["X-Process-Time"] = f"{duration:.4f}"

        return response

    except Exception as e:
        duration = time.time() - start_time
        request_logger.error(f"Error: {request.method} {request.url.path} - {str(e)} ({duration:.3f}s)")
        raise
