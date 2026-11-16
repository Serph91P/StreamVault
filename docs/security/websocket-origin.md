# WebSocket Origin policy

`/ws` validates every supplied `Origin` **before any WebSocket accept**, including
when authentication is missing, invalid, or unavailable. Exactly one header value
must match an entry in `settings.allowed_origins`. Empty values, `null`, duplicate
headers (even identical ones), lists, paths, and nonmatching schemes or ports are
rejected before upgrade (ASGI close code 1008; network servers normally return
HTTP 403 for a pre-accept close).

The allowlist is the existing public `BASE_URL` origin plus explicitly configured
`CORS_ADDITIONAL_ORIGINS`; existing development-only origins remain development-only.
For example, `BASE_URL=https://vault.example.test` allows
`Origin: https://vault.example.test` even if a reverse proxy forwards to an internal
HTTP host. Host, forwarded host/protocol, and Fetch-Site headers do not grant Origin
access. Configure additional public origins explicitly, not with wildcards or
same-site/subdomain assumptions. This is an exact string match, not URL normalization.

## Non-browser compatibility

Clients that **omit** `Origin` retain the existing cookie/Bearer credential
validation and legacy-session fallback. Missing Origin is not a credential or a
permission grant. Invalid or absent credentials still fail authentication; an
allowed Origin also never substitutes for credentials. Clients supplying an Origin,
including Bearer clients, must satisfy the same allowlist as browsers.

Cookie flags, HTTP CSRF checks, authentication scopes, manager limits, and replay
behavior are unchanged. SameSite cookies and HTTP CORS are complementary controls,
not substitutes for the WebSocket handshake check.

## Isolated verification

Run `uv run pytest tests/test_websocket_origin.py -q`. These tests exercise the
registered production `/ws` route and manager, including the application factory
and legacy middleware wiring. Only credential/database boundaries are inert doubles;
no JWTs, sessions, database writes, provider calls, or public sockets are needed.
ASGI frames prove rejection before accept, not merely a later disconnect.
The application factory is exercised without its startup lifespan, which would
initialize databases, keys, and background services. These are synthetic handshake
checks, not evidence of cookie delivery in a deployed browser or an internet exploit.

Reference: [OWASP WebSocket Security Cheat Sheet — Origin header validation](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html#origin-header-validation).
