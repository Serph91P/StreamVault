# Backend target architecture

This target is the staged #842 destination, not a claim about P0 completion.
Compatibility is preserved at every step: existing API paths/statuses and
OpenAPI path/methods, environment names/default behavior, cookie/API-key and
WebSocket message shapes, notification names, recording/media identity, port
7000, UID/GID and persistent volume paths.

## Target boundaries

- `app.main` remains a small composition root with injectable app construction.
  Imports must not open network/database connections, create files/processes,
  mutate persistent state or generate secrets.
- Configuration is pure Pydantic Settings v2. Key generation/persistence is an
  explicit, post-migration service; secret values are redacted at every sink.
- Each task and child process has a named owner, bounded output/queue/retry,
  cancellation and awaited shutdown path. No fire-and-forget service work.
- Feature routers call application/domain services through explicit session and
  transaction boundaries. ORM models, wire schemas and infrastructure adapters
  are separate.
- PostgreSQL is the production authority. Migration startup is serialized,
  fails closed, and a legacy-to-Alembic bridge preserves supported data/history.
- Managed HTTP clients, trusted-proxy parity, CSRF for cookie mutations,
  bounded WebSocket queues/replay and monotonic rate limiting protect public
  boundaries without changing approved contracts.
- Health separates liveness, startup, readiness and authenticated diagnostics.
  Readiness covers migrations/DB, critical services, writable recordings, tools
  and persistent keys.

## Contract governance

P0's versioned snapshot is the comparison point before each vertical slice.
An intentional change must include its consumer/migration/deprecation strategy
and an updated snapshot in the same reviewed PR. Removals or shape changes are
not accepted as incidental refactoring. The snapshot is inventory, not a source
of secrets or a permission to expose an endpoint.

## Acceptance boundaries

P0 establishes documentation and a contract guard only. It does not establish
real PostgreSQL fresh/upgrade/concurrent/restart evidence, Docker/Unraid
operation, performance comparisons, or live Twitch/EventSub/recording
acceptance. The #841 live-media canary remains a separately authorized
operations gate; synthetic tests cannot substitute for it.
