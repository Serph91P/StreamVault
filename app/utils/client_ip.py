"""
Client IP extraction utilities for reverse proxy environments.
"""

import logging

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

            if client_ip and is_valid_ip(client_ip):
                logger.debug(f"Real client IP found in {header_name}: {client_ip}")
                return client_ip

    # Fallback to direct connection IP
    if hasattr(request_or_websocket, "client") and request_or_websocket.client:
        fallback_ip = request_or_websocket.client.host
        logger.debug(f"Using fallback IP from direct connection: {fallback_ip}")
        return fallback_ip

    return "unknown"


def is_valid_ip(ip: str) -> bool:
    """
    Basic IP address validation.

    Args:
        ip: IP address string to validate

    Returns:
        True if the IP appears valid
    """
    if not ip or ip in ["unknown", "localhost", "127.0.0.1", "::1"]:
        return False

    # Remove port if present (IPv4:port or [IPv6]:port)
    if ":" in ip and not ip.startswith("["):
        # IPv4 with port
        ip = ip.split(":")[0]
    elif ip.startswith("[") and "]:" in ip:
        # IPv6 with port
        ip = ip[1 : ip.rindex("]")]

    # Basic IPv4 validation
    if "." in ip:
        parts = ip.split(".")
        if len(parts) == 4:
            try:
                return all(0 <= int(part) <= 255 for part in parts)
            except ValueError:
                return False

    # Basic IPv6 validation (simplified)
    if ":" in ip:
        return len(ip.split(":")) <= 8 and all(
            len(part) <= 4 and all(c in "0123456789abcdefABCDEF" for c in part) for part in ip.split(":") if part
        )

    return False


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
