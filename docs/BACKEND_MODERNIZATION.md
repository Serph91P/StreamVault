# Backend modernization operations guide

This guide describes the modular FastAPI backend introduced by issue #826 and
its operational contracts. It supplements, not replaces, the user-facing
installation guide.

## Architecture and compatibility

`app.main.create_app()` is the application composition root. It installs the
lifespan, exception envelope, HTTP middleware, auth middleware, modular routers,
SPA/static mounts and the compatibility `app` export. Public API paths remain
unversioned under their existing `/api/...` contracts; the OpenAPI document is
served at `/api/openapi.json` and the interactive documentation at `/api/docs`.

The semantic route inventory changed by extraction, not by an API-v1 rewrite:

| Contract | Before | After | Evidence |
| --- | --- | --- | --- |
| Application composition | Inline registrations in `app.main` | Explicit router registration in `create_app()` | `tests/test_phase4b_composition.py` |
| EventSub callbacks | `/eventsub` GET, HEAD and POST | Same operations in `app.routes.eventsub` | Frozen OpenAPI contract test |
| Realtime events | `/api/realtime/events` | Same operation in `app.routes.realtime` | Frozen OpenAPI contract test |
| Existing health check | `/api/health` | Preserved compatibility response | `tests/test_observability_hardening.py` |
| New operational endpoints | None | `/api/health/live`, `/api/health/ready`, opt-in `/api/metrics` | Application/OpenAPI and observability tests |
| SPA fallback | Browser paths serve the SPA, missing `/api/*` stays 404 | Preserved | Composition contract test |

The source-level decorator count is not itself an API contract: the frozen base
had 253 decorator declarations in its monolithic layout and this candidate has
234 after router extraction. The tests above verify effective path and method
registrations, duplicate prevention, selected frozen operation IDs, WebSocket
registration and SPA/API fallback semantics.

## Required configuration

Use a non-committed `.env` file for local or Compose deployment. The application
has typed settings and fails closed for JWT issuance in production.

| Variable | Required | Purpose |
| --- | --- | --- |
| `TWITCH_APP_ID`, `TWITCH_APP_SECRET` | Yes | Twitch application credentials for EventSub and API access. |
| `BASE_URL` | Yes | Public application origin and EventSub callback base. |
| `EVENTSUB_SECRET` | Yes in production | HMAC secret for EventSub callback verification. |
| `AUTH_JWT_SECRET` | Yes in production | At least 32 characters; signs short-lived access tokens. |
| `DATABASE_URL` | Yes in production | PostgreSQL connection URL. Compose derives it from the PostgreSQL variables. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Compose | Database container identity and database name. |
| `ENVIRONMENT` | Recommended | Use `production` for deployed instances and `development` locally. |
| `TRUSTED_HOSTS`, `TRUSTED_PROXY_CIDRS` | Production | Comma-separated allowed hosts and proxy CIDRs. Empty proxy CIDRs do not trust forwarded headers. |
| `CORS_ADDITIONAL_ORIGINS` | Optional | Comma-separated additional browser origins. |
| `METRICS_ENABLED`, `METRICS_AUTH_TOKEN` | Optional | Explicit metrics exposure and its dedicated bearer token. |
| `READINESS_TIMEOUT_SECONDS`, `READINESS_REQUIRED_COMPONENTS` | Optional | Bound readiness probes and required components. |

Generate unique secrets with `openssl rand -hex 32`. Do not reuse EventSub,
JWT, database, Twitch, proxy or metrics credentials. Do not commit `.env`, log
its contents, or copy tokens into issue or PR comments.

## Authentication and authorization

Login writes `HttpOnly` access and refresh cookies. Access tokens use HS256 with
issuer, audience, token type and time validation. The default access lifetime is
15 minutes. Refresh tokens are opaque, stored as hashes, rotate on use, and a
replayed or revoked token invalidates its whole refresh family.

Browser refresh requests use `POST /auth/refresh`. The existing hashed `session`
cookie remains a compatibility path during migration. New frontend code must not
mirror HttpOnly cookies into local storage.

`require_scopes(...)` protects scope-aware endpoints. Administrators receive the
default administrative scope set; non-admin users receive `recording:read`.
Missing authentication returns 401 and insufficient scope returns 403. API keys
are not interactive browser sessions.

## Database and migrations

Production uses PostgreSQL. SQLite remains a test and development path but is
not a substitute for PostgreSQL deployment validation. On startup the migration
service serializes discovery and execution with a PostgreSQL advisory lock. A
successful migration is tracked only after it returns successfully; failed work
is not marked applied and can be recovered after its cause is fixed.

Application startup invokes the migration service. CI checks migration tracking,
idempotency, failure no-mutation, and PostgreSQL advisory-lock behavior with
`tests/test_migration_foundation.py` and
`tests/test_migration_service_orchestration.py`. For clean installs and
representative PostgreSQL upgrades, use
`tests/run_fresh_postgres_proxy_migrations.sh`. The numbered migration runner
supports safe `upgrade()` or `run_migration()` functions. Some migrations provide
a safe `downgrade()`; do not run a downgrade blindly against live data. Take a
verified PostgreSQL backup first, stop new writes, validate downgrade
preconditions, run the migration-specific downgrade, and then re-run the
upgrade/recovery checks if rollback is aborted.

Recovery note: a malformed or failed migration must leave no success tracking
row. Inspect the sanitized application logs, repair the migration or deployment
configuration, and re-run the normal migration entry point. Do not delete the
migration tracking table or reset production schemas to force progress.

## Health, readiness, metrics and recording ownership

- `GET /api/health/live` proves the ASGI event loop answers and is the Compose
  and image healthcheck endpoint.
- `GET /api/health` remains a compatibility endpoint and reports bounded database
  availability.
- `GET /api/health/ready` checks configured required components such as database,
  FFmpeg and Streamlink within `READINESS_TIMEOUT_SECONDS`; it returns 503 with
  sanitized component names when not ready.
- `GET /api/metrics` is disabled by default. In production it requires a separate
  bearer token and returns 404 when disabled or unauthorized. Metrics intentionally
  exclude request and user identifiers.

`RecordingManager` is the typed process-scoped facade for start, stop, status,
reconciliation and shutdown. Local process dictionaries are caches only. Durable
multi-instance ownership is enforced by PostgreSQL-backed leases via the Twitch
upstream coordinator; startup reconciliation releases stale leases before local
recovery. A deployment must not treat an in-memory dictionary as a cross-instance
lock.

## Local development and CI parity

The repository CI targets Python 3.14 and Node 24. Use isolated environments and
run the workflow commands from the repository root:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov httpx ruff mypy
pytest tests/ -v --cov=app --cov-report=xml --cov-report=html --cov-report=term-missing --tb=short
pytest -v --tb=short tests/test_migration_foundation.py tests/test_migration_service_orchestration.py
ruff check app/
ruff format --check app/
mypy --follow-imports=skip --ignore-missing-imports app/config/settings.py app/core/exceptions.py app/middleware/logging.py app/observability.py app/routes/health.py
cd app/frontend
npm ci --prefer-offline
npm run lint
npm run lint:tokens
npm run type-check
npm run build
npm audit --audit-level high
```

The mypy target is intentionally bounded to the modernized typed surface. The
historical SQLAlchemy 1.x-style modules have existing typing debt and are not
silenced through a blanket `|| true` gate.

The no-push image workflow builds `docker/Dockerfile` for `linux/amd64`. Run
`tests/run_fresh_postgres_proxy_migrations.sh` against that image: it creates a
fresh PostgreSQL-backed disposable deployment with non-production placeholders,
verifies liveness, readiness, static frontend serving, OpenAPI, request IDs and
the metrics-token policy, and removes only the containers and network it created.

## Troubleshooting

| Symptom | Check | Safe response |
| --- | --- | --- |
| Login returns a server error | `AUTH_JWT_SECRET`, issuer/audience and cookie TLS configuration | Configure a unique 32+ character JWT secret; do not weaken token validation. |
| Readiness is 503 | `/api/health/ready` response | Fix only the named required dependency, then retry. Liveness may remain 200. |
| Metrics return 404 | `METRICS_ENABLED` and `METRICS_AUTH_TOKEN` | Explicitly enable the endpoint and use its dedicated bearer token. |
| Migration startup fails | Sanitized migration logs and migration tests | Preserve data and migration tracking; repair the cause and rerun normally. |
| Duplicate recording activity | PostgreSQL connectivity and lease records | Keep only the durable lease owner; do not manually clear local caches as a distributed fix. |
| Browser cannot call API | `BASE_URL`, CORS and trusted-host settings | Add explicit origins/hosts and trusted proxy CIDRs, then retest through the real proxy. |

## Security gate policy

Bandit high-severity/high-confidence findings, `pip-audit`, `npm audit` at high
severity, Gitleaks, Trivy high/critical findings and Hadolint error-level
Dockerfile findings are CI gates. Informational and warning-level Dockerfile
findings remain a documented historical baseline rather than a silent bypass.
The previously accepted GitGuardian finding on an old test-only `token=ABC`
fixture is a documented external false positive; no credential value is present
in the current source and published history was not rewritten.
