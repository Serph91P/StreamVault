# Code Review: Full Application Security Audit

**Date:** 2026-02-24  
**Scope:** Entire StreamVault application (backend, frontend, Docker, infrastructure)  
**Ready for Production:** No  
**Critical Issues:** 3  
**High Issues:** 6  
**Medium Issues:** 10  
**Low Issues:** 8  

---

## Priority 1 — Must Fix ⛔

### C1: Auth Middleware Fails Open on Exception
**File:** `app/middleware/auth.py` lines 106–108  
**OWASP:** A01 Broken Access Control  
**CWE:** CWE-280 Improper Handling of Insufficient Permissions

```python
except Exception as e:
    logger.error(f"Auth middleware error for {request.url.path}: {e}")
    return await self.app(scope, receive, send)  # PASSES THROUGH UNAUTHENTICATED
```

If the auth middleware encounters **any** exception (e.g., database unavailable, connection pool exhausted), the request passes through **without authentication**. A transient DB failure would make every protected endpoint publicly accessible.

**Fix:**
```python
except Exception as e:
    logger.error(f"Auth middleware error for {request.url.path}: {e}")
    return await JSONResponse(
        {"error": "Authentication service unavailable"},
        status_code=503
    )(scope, receive, send)
```

---

### C2: WebSocket Endpoint Has Zero Authentication
**File:** `app/middleware/auth.py` lines 18–20, `app/main.py` line 682  
**OWASP:** A01 Broken Access Control

```python
# auth.py — WebSocket connections bypass ALL auth
if scope["type"] == "websocket":
    return await self.app(scope, receive, send)

# main.py — No session validation in handler
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)  # No auth check
```

Any unauthenticated user can connect to `/ws` and receive all real-time data (recording statuses, streamer updates, queue status, system notifications).

**Fix:** Validate the session cookie during WebSocket handshake:
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_token = websocket.cookies.get("session")
    if not session_token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    db = SessionLocal()
    try:
        auth_service = AuthService(db=db)
        if not await auth_service.validate_session(session_token):
            await websocket.close(code=4001, reason="Invalid session")
            return
    finally:
        db.close()
    await websocket_manager.connect(websocket)
    # ...
```

---

### C3: `get_current_user()` Provides No Actual Authentication
**File:** `app/dependencies.py` lines 72–76  
**OWASP:** A01 Broken Access Control

```python
def get_current_user(db: Session = Depends(get_db)) -> Optional["User"]:
    user = db.query(User).filter(User.is_admin.is_(True)).first()
    return user  # Returns ANY admin user, no session validation!
```

This dependency is used as `Depends(get_current_user)` in proxy and category routes. It unconditionally returns the first admin user from the database regardless of who is making the request.

**Fix:** Extract session from the request and validate it:
```python
def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional["User"]:
    session_token = request.cookies.get("session")
    if not session_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    auth_service = AuthService(db=db)
    # Validate session and return associated user
    session = db.query(Session).filter(Session.token == session_token).first()
    if not session or session.is_expired():
        raise HTTPException(status_code=401, detail="Session expired")
    return session.user
```

---

## Priority 2 — High Severity 🔴

### H1: Global Error Handler Leaks Exception Details
**File:** `app/middleware/error_handler.py` line 10  
**OWASP:** A05 Security Misconfiguration

```python
return JSONResponse(status_code=500, content={"message": "Internal server error", "detail": str(exc)})
```

Raw exception strings expose database schemas, file paths, library versions, and internal logic to clients. This aids attackers in reconnaissance.

**Fix:** Never return raw `str(exc)` to the client. Log it server-side, return a generic message:
```python
return JSONResponse(status_code=500, content={"message": "Internal server error"})
```

---

### H2: Path Traversal via `startswith()` Instead of `validate_path_security()`
**File:** `app/routes/admin_post_processing.py` lines 353–354  
**OWASP:** A01 Broken Access Control, CWE-22

```python
normalized_path = os.path.normpath(os.path.join(RECORDINGS_ROOT, ts_file_path))
if not normalized_path.startswith(RECORDINGS_ROOT):
```

Uses `os.path.normpath()` + string `startswith()` instead of `validate_path_security()`. This is vulnerable to:
- If `RECORDINGS_ROOT = "/recordings"`, path `/recordings_evil/file` passes the check
- No symlink resolution (`os.path.realpath()` not used)
- No `os.sep` boundary check

**Fix:** Replace with `validate_path_security()`.

---

### H3: Twitch Access Token Passed in URL
**File:** `app/routes/twitch_auth.py` line 85  
**OWASP:** A02 Cryptographic Failures

```python
return RedirectResponse(url=f"/add-streamer?token={access_token}&auth_success=true")
```

Tokens in URLs are logged in browser history, server access logs, proxy logs, and leak via `Referer` headers.

**Fix:** Store the token server-side (in the session or database) and redirect without it in the URL.

---

### H4: Session Tokens Stored in Plaintext in Database
**File:** `app/models.py` — `Session.token` column  
**OWASP:** A02 Cryptographic Failures

If the database is compromised, all active sessions are immediately hijackable. Best practice is to store `SHA-256(token)` in the database and compare hashes.

---

### H5: No Rate Limiting on Login Endpoint
**File:** `app/routes/auth.py` — `/auth/login`  
**OWASP:** A07 Identification and Authentication Failures

The adaptive rate limiter allows ~120 mutation requests before throttling. The `/auth/login` endpoint has no specific brute-force protection — no account lockout, no per-IP rate limiting for auth attempts.

**Fix:** Implement separate, stricter rate limiting for `/auth/login` (e.g., 5 attempts per minute per IP), with exponential backoff or account lockout.

---

### H6: Debug/Test Endpoints Expose Internal Paths Without Auth
**File:** `app/routes/videos.py` — multiple debug endpoints  
**OWASP:** A01 Broken Access Control, A05 Security Misconfiguration

Endpoints like `test_video_access`, `debug_videos_database`, `debug_recordings_directory` expose full filesystem paths, file sizes, request headers, session tokens, and directory structures. Some have inconsistent or missing authentication checks.

**Fix:** Remove debug endpoints from production builds, or gate them behind an explicit `DEBUG` environment variable check with proper auth.

---

## Priority 3 — Medium Severity 🟡

### M1: Numerous Routes Return `str(e)` in Error Responses
**Files:** `app/routes/admin.py`, `app/routes/settings.py`, and others  
**OWASP:** A05 Security Misconfiguration

Multiple endpoints expose raw Python exception strings via `detail=str(e)`, leaking internal paths, SQL errors, and library details.

**Fix:** Log the exception server-side, return generic error messages to the client.

---

### M2: No CSRF Token Verification
**OWASP:** A01 Broken Access Control

Only `SameSite=Lax` cookies provide CSRF protection. This does NOT protect against same-site subdomain attacks or scenarios where the user's browser doesn't support SameSite cookies well.

---

### M3: CSP Allows `unsafe-eval`
**File:** `app/main.py` line 482  
**OWASP:** A03 Injection

```
script-src 'self' 'unsafe-inline' 'unsafe-eval';
```

Vue 3 production builds do NOT require `unsafe-eval`. Removing it significantly strengthens XSS protection.

---

### M4: Unauthenticated Static Mounts Expose `.media` and `/data/`
**Files:** `app/main.py` lines 972–985, `app/middleware/auth.py` lines 55–60  
**OWASP:** A01 Broken Access Control

The `.media` directory is served unauthenticated under three URL prefixes (`/recordings/.media/`, `/api/media/`, `/data/images/`). All files under `/data/` are also public. If sensitive data is placed in these directories, it is exposed.

---

### M5: SSRF Risk via User-Controlled Apprise Notification URLs
**File:** `app/routes/settings.py` — notification URL configuration  
**OWASP:** A10 Server-Side Request Forgery

Apprise supports many protocols (`json://`, `xml://`, `http://`, `slack://`) — a user-configured notification URL could target internal services.

---

### M6: SSRF Risk via User-Controlled Proxy URLs
**File:** `app/services/proxy/proxy_health_service.py` line 287  
**OWASP:** A10 SSRF

Proxy URLs are user-provided and used in `aiohttp.ClientSession(proxy=proxy_url)`. Validation only checks `http://` or `https://` prefix — does not block internal network addresses.

---

### M7: Proxy Encryption Key Stored in Same Database as Encrypted Data
**File:** `app/utils/proxy_encryption.py` lines 66–73  
**OWASP:** A02 Cryptographic Failures

If the database is compromised, the attacker gets both the encrypted proxy credentials AND the encryption key. The key should be stored separately (environment variable or keystore).

---

### M8: `CORS_ALLOW_HEADERS: ["*"]`
**File:** `app/config/settings.py` line 158  
**OWASP:** A05 Security Misconfiguration

Overly permissive CORS header configuration. Should be restricted to known required headers.

---

### M9: Proxy Encryption Debug Logging Leaks Plaintext
**File:** `app/utils/proxy_encryption.py`

```python
logger.debug(f"🔒 Encrypted proxy URL: {plaintext[:20]}...")
```

Leaks the first 20 characters of proxy URLs (may contain scheme + username) to log files.

---

### M10: Missing `credentials: 'include'` in Several Frontend Fetch Calls
**Files:**
- `app/frontend/src/components/admin/AdminPanel.vue` line 587
- `app/frontend/src/components/settings/LoggingPanel.vue` line 346
- `app/frontend/src/components/settings/NotificationSettingsPanel.vue` line 390
- `app/frontend/src/components/settings/PWAPanel.vue` line 257

These fetch calls to protected endpoints won't send the session cookie, causing the operations to fail silently.

---

## Priority 4 — Low Severity / Suggestions 🔵

### L1: `EVENTSUB_SECRET` Regenerated on Every Restart
**File:** `app/config/settings.py` line 128

Regenerated with `secrets.token_urlsafe(32)` on each restart. Breaks existing Twitch EventSub subscriptions. Should be persisted.

### L2: `db.execute("SELECT 1")` Missing `text()` Wrapper
**File:** `app/routes/status.py` line 237

Will trigger deprecation warning in SQLAlchemy 2.x.

### L3: Developer's Local Filesystem Path Hardcoded
**File:** `app/routes/admin.py` line 328

```python
"/home/maxe/Dokumente/private_projects/StreamVault/app.log"
```

Information leak of developer's filesystem path in production code.

### L4: OpenAPI Docs Always Enabled
**File:** `app/main.py` lines 391–394

`/api/docs` and `/api/redoc` are always available. Should be disabled or gated in production.

### L5: No Session Fixation Prevention
No old sessions are invalidated when a user logs in. An attacker who obtains a pre-auth session token can use it after the victim authenticates.

### L6: Unlimited Concurrent Sessions
No limit on concurrent sessions per user. A stolen session survives legitimate logouts.

### L7: Dead PWA Session Storage Code
**File:** `app/frontend/src/composables/useAuth.ts` lines 83–88

Attempts to read HttpOnly cookie via `document.cookie` (always returns null). Dead code.

### L8: Docker Base Image Not Pinned by Digest
**File:** `docker/Dockerfile` line 7

`python:3.14-alpine` uses floating tag. Should use `@sha256:...` for reproducible builds.

---

## Positive Findings ✅

| Area | Assessment |
|------|------------|
| **Password hashing** | Argon2 via `argon2-cffi` — **Excellent** |
| **Session token generation** | `secrets.token_urlsafe(32)` — **Excellent** |
| **SQL injection** | All queries use SQLAlchemy ORM or parameterized `text()` queries — **No vulnerabilities found** |
| **Command injection** | All subprocess calls use list-based arguments — **No vulnerabilities found** |
| **XSS** | Zero `v-html`, `innerHTML`, `eval()`, `Function()` usage in frontend — **Excellent** |
| **Frontend API client** | Centralized client auto-injects `credentials: 'include'` — **Good** |
| **Security headers** | Full set: HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy — **Good** |
| **Cookie security** | HttpOnly, SameSite=Lax, configurable Secure flag — **Good** |
| **Docker security** | Non-root user, multi-stage build, database not exposed, resource limits — **Good** |
| **No insecure deserialization** | No pickle, yaml.unsafe_load, eval with user input — **Good** |
| **Path validation utility** | `validate_path_security()` using `Path.is_relative_to()` — **Good implementation** |
| **EventSub HMAC** | SHA-256 with `hmac.compare_digest()` timing-safe comparison — **Excellent** |
| **`.dockerignore`** | Properly excludes `.env`, `.git`, tests — **Good** |

---

## Summary Table

| Severity | Count | Key Themes |
|----------|-------|------------|
| **Critical** | 3 | Auth middleware fail-open, WebSocket no auth, fake `get_current_user` |
| **High** | 6 | Error info leak, path traversal, token in URL, plaintext sessions, no login rate limit, debug endpoints |
| **Medium** | 10 | CSRF, CSP, SSRF, CORS, public static mounts, crypto key storage, logging leaks |
| **Low** | 8 | Config persistence, dead code, Docker hardening, session management |

### Priority Remediation Order
1. Fix auth middleware to fail closed (C1) — **Immediate**
2. Add WebSocket authentication (C2) — **Immediate**
3. Rewrite `get_current_user()` to validate sessions (C3) — **Immediate**
4. Stop leaking exception details to clients (H1) — **This week**
5. Replace `startswith()` path check with `validate_path_security()` (H2) — **This week**
6. Remove token from redirect URL (H3) — **This week**
7. Hash session tokens in DB (H4) — **This sprint**
8. Add login brute-force protection (H5) — **This sprint**
9. Remove/gate debug endpoints (H6) — **This sprint**
