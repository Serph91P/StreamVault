import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config.settings import settings
from app.config.logging_config import request_context
from app.middleware.logging import logging_middleware

import logging

logger = logging.getLogger("streamvault")


@dataclass
class _TokenBucket:
    capacity: int
    refill_per_sec: float
    tokens: float
    last_refill: float
    lock: asyncio.Lock

    def refill(self) -> None:
        now = time.time()
        if now > self.last_refill:
            delta = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + delta * self.refill_per_sec)
            self.last_refill = now


class AdaptiveLimiter:
    def __init__(self) -> None:
        self.enabled = settings.RATE_LIMIT_ENABLED
        self.default_capacity = settings.RATE_LIMIT_CAPACITY
        self.default_refill = settings.RATE_LIMIT_REFILL_PER_SEC
        self.max_wait_ms = settings.RATE_LIMIT_MAX_WAIT_MS
        self._buckets: Dict[str, _TokenBucket] = {}
        self._lock = asyncio.Lock()

    def _route_params(self, path: str, method: str) -> Tuple[int, float]:
        # Allow higher throughput for safe, read-only endpoints
        method = method.upper()
        if method == "GET":
            if (
                path.startswith("/api/background-queue/")
                or path.startswith("/api/streamers")
                or path.startswith("/api/status")
                or path.startswith("/api/streams")
            ):
                return (800, 20.0)
            # Default GET budget
            return (500, 10.0)
        # Mutations: stricter by default
        return (120, 2.0)

    def _key(
        self, path: str, method: str, client_ip: str, auth_header: Optional[str]
    ) -> str:
        if auth_header and auth_header.startswith("Bearer ") and len(auth_header) > 7:
            token = auth_header[7:].strip()
            # Use a longer digest segment to reduce collision risk
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:32]
            return f"auth:{digest}"
        return f"ip:{client_ip}"

    async def _get_bucket(self, key: str, capacity: int, refill: float) -> _TokenBucket:
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _TokenBucket(
                    capacity, refill, float(capacity), time.time(), asyncio.Lock()
                )
                self._buckets[key] = bucket
            else:
                bucket.capacity = capacity
                bucket.refill_per_sec = refill
            return bucket

    async def acquire(
        self, *, path: str, method: str, client_ip: str, auth_header: Optional[str]
    ) -> Tuple[bool, int, int, int]:
        """Attempt to consume a token.
        Returns (allowed, retry_after_seconds, remaining_tokens, capacity)
        """
        if not self.enabled:
            cap = self.default_capacity
            return True, 0, cap, cap

        capacity, refill = self._route_params(path, method)
        key = self._key(path, method, client_ip, auth_header)
        bucket = await self._get_bucket(key, capacity, refill)

        async with bucket.lock:
            bucket.refill()
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0, max(0, int(bucket.tokens)), capacity

            # Soft wait to reduce spiky 429s
            deadline = time.time() + (self.max_wait_ms / 1000.0)
            while time.time() < deadline:
                await asyncio.sleep(0.05)
                bucket.refill()
                if bucket.tokens >= 1.0:
                    bucket.tokens -= 1.0
                    return True, 0, max(0, int(bucket.tokens)), capacity

            # Still no tokens
            needed = 1.0 - bucket.tokens
            # Ensure refill_per_sec is never zero to avoid permanent lockout
            effective_refill = (
                bucket.refill_per_sec if bucket.refill_per_sec > 0 else 0.1
            )
            retry_after = max(1, int(needed / effective_refill))
            return False, retry_after, max(0, int(bucket.tokens)), capacity


async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # Set proper content types for specific files
    path = request.url.path

    # Special handling for service worker
    if path == "/registerSW.js" or path.endswith("registerSW.js"):
        response.headers["Content-Type"] = "application/javascript"
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        # Don't set X-Content-Type-Options for service worker
        return response

    # Set content types based on file extension
    content_type_map = {
        ".js": "application/javascript",
        ".json": "application/json",
        ".css": "text/css",
        ".ico": "image/x-icon",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webmanifest": "application/manifest+json",
        ".xml": "application/xml",
        ".html": "text/html",
        ".webp": "image/webp",
    }

    for ext, content_type in content_type_map.items():
        if path.endswith(ext):
            response.headers["Content-Type"] = content_type
            break

    # Security headers (only if enabled in settings)
    if settings.SECURE_HEADERS_ENABLED:
        # Basic security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS (only for HTTPS)
        if settings.is_secure:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains"
            )

        # Content Security Policy (if configured)
        if settings.CONTENT_SECURITY_POLICY:
            response.headers["Content-Security-Policy"] = (
                settings.CONTENT_SECURITY_POLICY
            )
        else:
            # Default CSP
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline'",  # Required for Vue.js; unsafe-eval removed for XSS protection
                "style-src 'self' 'unsafe-inline'",  # Required for inline styles
                "img-src 'self' data: https: blob:",  # Allow images from various sources
                "font-src 'self' data:",
                "connect-src 'self' wss: ws: https:",  # WebSocket and API connections
                "media-src 'self' blob:",  # For video playback
                "worker-src 'self' blob:",  # For service workers
                "manifest-src 'self'",
                "frame-ancestors 'none'",
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Permissions Policy (modern replacement for Feature Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

    return response


async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    request_token = request_context.set(request_id)

    # Skip logging for frequent background queue polling endpoints to reduce log spam
    skip_logging_paths = [
        "/api/background-queue/stats",
        "/api/background-queue/active-tasks",
    ]

    # Add request ID to logger context (skip frequent polling endpoints)
    if request.url.path not in skip_logging_paths:
        logger.info(f"Request {request_id}: {request.method} {request.url.path}")
    else:
        # Log at debug level for background queue endpoints
        logger.debug(f"Request {request_id}: {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_context.reset(request_token)


async def rate_limit_middleware(request: Request, call_next):
    limiter: AdaptiveLimiter = request.app.state.rate_limiter

    # Skip rate limiting for health checks, static files, and internal API calls
    if (
        request.url.path in ["/health", "/favicon.ico"]
        or request.url.path.startswith("/assets/")
        or request.url.path.startswith("/api/images/")  # Skip for image API calls
        or request.url.path.startswith(
            "/recordings/.media/"
        )  # Skip for cached image files
        or request.url.path.startswith("/api/sync/")  # Skip for sync API calls
        or request.url.path.startswith("/data/")
    ):
        return await call_next(request)

    # Get client IP (respect reverse proxy)
    client_ip = request.client.host
    if request.headers.get("X-Forwarded-For"):
        client_ip = request.headers["X-Forwarded-For"].split(",")[0].strip()

    # Skip for localhost/internal
    if client_ip in ["127.0.0.1", "localhost", "::1"]:
        return await call_next(request)

    allowed, retry_after, remaining, capacity = await limiter.acquire(
        path=request.url.path,
        method=request.method,
        client_ip=client_ip,
        auth_header=request.headers.get("Authorization"),
    )

    if not allowed:
        logger.warning(
            f"Rate limit: 429 path={request.url.path} ip={client_ip} retry_after={retry_after}s"
        )
        return Response(
            content="Rate limit exceeded",
            status_code=429,
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(capacity),
                "X-RateLimit-Remaining": str(remaining),
            },
        )

    response = await call_next(request)
    # Expose dynamic headers for clients
    response.headers["X-RateLimit-Limit"] = str(capacity)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


def install_http_middleware(app: FastAPI) -> None:
    """Install all HTTP middleware in the same order as the legacy main module.

    The adaptive rate limiter's mutable bucket state lives on ``app.state``
    rather than a module-level global.
    """
    app.state.rate_limiter = AdaptiveLimiter()

    # Add Trusted Host middleware (security best practice)
    if settings.is_secure:
        # Only allow requests to our configured domain in production
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[
                settings.domain,
                f"www.{settings.domain}",
                "localhost",  # For health checks
            ],
        )

    # Add CORS middleware with secure configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,  # Use computed origins from settings
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        max_age=settings.CORS_MAX_AGE,
    )

    # Add custom middleware
    app.middleware("http")(logging_middleware)
    app.middleware("http")(add_security_headers)
    app.middleware("http")(add_request_id)
    app.middleware("http")(rate_limit_middleware)
