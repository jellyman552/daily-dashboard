"""Restricts the API to loopback (SSH tunnel) and Tailscale traffic only.

Defense-in-depth: even if the systemd unit's bind address or Oracle's cloud
firewall were ever misconfigured to expose this port publicly, requests
from outside these ranges get rejected before touching any route. This is
not a substitute for the cloud-level firewall — it's a second, independent
check that doesn't depend on being able to verify Oracle's console config
from here.
"""
import ipaddress

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_ALLOWED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("100.64.0.0/10"),  # Tailscale's IPv4 CGNAT range
    ipaddress.ip_network("fd7a:115c:a1e0::/48"),  # Tailscale's IPv6 ULA range
]


def _extra_networks():
    from app.config import get_settings

    raw = get_settings().extra_trusted_networks
    return [ipaddress.ip_network(c.strip()) for c in raw.split(",") if c.strip()]


def _is_allowed(host: str) -> bool:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr in network for network in _ALLOWED_NETWORKS + _extra_networks())


class TrustedNetworkMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client = request.client
        if client is None or not _is_allowed(client.host):
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
        return await call_next(request)
