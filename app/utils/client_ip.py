"""
Client IP extraction utilities for reverse proxy environments.
"""

import ipaddress
import logging

from app.config.settings import settings

logger = logging.getLogger("streamvault")


def get_real_client_ip(request_or_websocket) -> str:
    """
    Extract the real client IP from reverse proxy headers.

    Args:
        request_or_websocket: FastAPI Request or WebSocket object

    Returns:
        The real client IP address
    """
    # Headers to check in order of preference
    ip_headers = [
        "cf-connecting-ip",  # Cloudflare
        "x-real-ip",  # Nginx
        "x-forwarded-for",  # Standard proxy header
        "x-client-ip",  # Alternative
        "x-cluster-client-ip",  # Load balancer
        "forwarded",  # RFC 7239
    ]

    direct_ip = "unknown"
    if hasattr(request_or_websocket, "client") and request_or_websocket.client:
        direct_ip = request_or_websocket.client.host

    # Forwarding headers are attacker-controlled unless the socket peer is a
    # configured reverse proxy. HTTP and WebSocket callers deliberately share
    # this function so they cannot disagree about client identity.
    if not settings.is_trusted_proxy(direct_ip):
        return direct_ip

    headers = request_or_websocket.headers

    # Check each header for IP address
    for header_name in ip_headers:
        header_value = headers.get(header_name)
        if header_value:
            # X-Forwarded-For can contain multiple IPs (client, proxy1, proxy2, ...)
            # The first one is usually the real client IP
            if header_name == "x-forwarded-for":
                ips = [ip.strip() for ip in header_value.split(",")]
                client_ip = ips[0] if ips else None
            elif header_name == "forwarded":
                # RFC 7239 format: for=client_ip;proto=https;host=example.com
                for part in header_value.split(";"):
                    if part.strip().startswith("for="):
                        client_ip = part.split("=", 1)[1].strip().strip('"')
                        break
                else:
                    client_ip = None
            else:
                client_ip = header_value.strip()

            parsed_ip = _parse_client_ip(client_ip) if client_ip else None
            if parsed_ip is not None:
                logger.debug("Real client IP found in %s: %s", header_name, parsed_ip)
                return parsed_ip

    # Fallback to direct connection IP
    if direct_ip != "unknown":
        logger.debug(f"Using fallback IP from direct connection: {direct_ip}")
        return direct_ip

    return "unknown"


def _parse_client_ip(value: str) -> str | None:
    """Normalize a literal address, optionally with an unambiguous port."""
    if not value or "%" in value:
        return None
    address = value
    port = None
    if value.startswith("["):
        address, separator, suffix = value[1:].partition("]")
        if not separator or (suffix and not suffix.startswith(":")):
            return None
        if suffix:
            port = suffix[1:]
    elif value.count(":") == 1:
        address, port = value.rsplit(":", 1)
    try:
        if port is not None and (
            not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535
        ):
            return None
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return None
    # A forwarded loopback must not bypass the limiter's local-peer exemption.
    if parsed.is_loopback:
        return None
    return str(parsed)


def is_valid_ip(ip: str) -> bool:
    """Whether a forwarded value is a valid non-loopback literal address."""
    return _parse_client_ip(ip) is not None


def get_client_info(request_or_websocket) -> dict:
    """
    Get comprehensive client information including IP, user agent, etc.

    Args:
        request_or_websocket: FastAPI Request or WebSocket object

    Returns:
        Dictionary with client information
    """
    headers = request_or_websocket.headers
    real_ip = get_real_client_ip(request_or_websocket)

    # Get proxy IP for comparison
    proxy_ip = "unknown"
    if hasattr(request_or_websocket, "client") and request_or_websocket.client:
        proxy_ip = request_or_websocket.client.host

    return {
        "real_ip": real_ip,
        "proxy_ip": proxy_ip,
        "user_agent": headers.get("user-agent", "unknown"),
        "forwarded_proto": headers.get("x-forwarded-proto", "unknown"),
        "forwarded_host": headers.get("x-forwarded-host", "unknown"),
        "is_reverse_proxied": real_ip != proxy_ip,
    }
