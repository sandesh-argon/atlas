"""
Client IP extraction helpers.

Only trusts forwarding headers when the immediate peer is a trusted proxy.
"""

from __future__ import annotations

import ipaddress
from typing import Optional

from fastapi import Request

from ..config import TRUST_PROXY_IPS


def _parse_ip(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    candidate = raw.split(",")[0].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def get_client_ip(request: Request) -> str:
    """Get client IP with proxy-header safety checks."""
    peer_ip = _parse_ip(request.client.host if request.client else None)

    if peer_ip and peer_ip in TRUST_PROXY_IPS:
        for header in ("CF-Connecting-IP", "X-Real-IP", "X-Forwarded-For"):
            forwarded_ip = _parse_ip(request.headers.get(header))
            if forwarded_ip:
                return forwarded_ip

    return peer_ip or "unknown"

