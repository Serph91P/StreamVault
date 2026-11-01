# Backend target architecture (#842)

Status: implementation target, **not a claim that the migration is complete**.
Authority: the complete original request and current owner decisions. Compare the
observed exact-base inventory in `backend-baseline.md`, frozen contracts in
`contracts/base-842.json`, and criterion/evidence status in
`backend-acceptance-matrix.md`. Deployment, provider/device acceptance, merges and
the superseded Twitch authentication-priority feature are not authorized here.

## 1. Keep the modular monolith and its public boundary

Retain FastAPI, SQLAlchemy, Alembic, the existing locked dependencies, subprocess
media tools, feature routes and public compatibility exports. Do not introduce a
service container, generic repository framework, event bus replacement or a
whole-database async rewrite. Preserve paths/methods/auth/error/JSON/WebSocket and
media contracts, database identifiers, migration identities, persistent keys,
recording paths, queue dependencies and ownership/fencing rules.

`app/main.py` remains the small `app`/`create_app`/`lifespan` compatibility entry.
`app/bootstrap/application.py` composes the real routes, mounts, middleware,
exception handlers and dependencies. Explicit configurations and injected
resources build independent applications; the existing no-argument default export
remains compatible. Root/API adapters may resolve application state. Domain
services must instead receive their concrete configuration, session factory,
managed client and collaborator handles, never discover another application's
runtime through a module singleton or context-variable service locator.

## 2. Construction is pure; lifespan owns work

Settings validation, imports, model registration and factory composition must not
open engines/sessions/clients, generate or publish keys, create directories, start
threads/tasks/processes or contact providers. Static mounts defer filesystem
validation; lifespan prepares the existing configured directory layout.

An application's resource graph owns its database lifecycle, resolved settings
and key material, HTTP clients, recording/live services, event registry,
WebSocket connections/broadcast worker, queues, image/proxy workers and supervisor.
Compatibility module facades belong only to the default application, not to a
second explicitly configured application. Overrides remain explicit injection
seams, not hidden response or dependency overlays used to manufacture acceptance.

Startup order: validated runtime configuration and storage; database/legacy and
Alembic migrations; persisted identities; optional preparation; core service
reconciliation; background workers; readiness. Shutdown first stops admission and
producers, drains/cancels and awaits owned work, reaps owned physical children,
closes HTTP/services, then disposes only the owner's database. Failure during
partial startup still releases every already-acquired resource. No app may stop
another app's tasks, connections or pools.

## 3. Explicit hybrid database/I/O decision

Keep the accepted async category repository and request-scoped AsyncSession path.
Use async I/O directly where the feature already supports it. Retain sync
SQLAlchemy for the remaining legacy transactional/media operations while moving
each complete blocking operation off the event loop. This is the requested hybrid
choice, not permission to mark sync work `async def` and leave it blocking.

A sync callback opens its own session, performs the full transaction and eagerly
maps the result to an immutable typed value/DTO, then closes the session **inside
the worker**. Never pass a live Session/ORM row across awaits, tasks or threads.
Hashing, filesystem/media probing and other blocking libraries follow the same
explicit boundary. Native async clients stay on their owning event loop.

Reuse the existing `run_in_thread_pool` seam with standard `asyncio.to_thread`
(context/keyword propagation) and retained, named, shielded worker ownership.
Cancellation drains the actual worker's cleanup before propagating; it is not a
thread termination mechanism. Operations retain their existing driver/deadline
budgets. Async repository sessions remain scoped to one operation/request and
convert rows before session exit; no lazy serialization or property-triggered SQL.

DatabaseLifecycle selects the supplied validated configuration lazily, with no
SQLite fallback outside explicit test configuration. The explicit URL lifecycle
remains the test/injection seam. MigrationService's per-engine binding must govern
both ledger and actual historical script execution, lock, Alembic and reflection;
changing just the ledger is insufficient. Preserve all existing migration SQL and
identities, no new migration or existing-volume manipulation for code ownership.

## 4. Feature models and application boundaries

`app/models/__init__.py` remains a compatibility export. The existing typed
`models/categories.py` slice is retained. The former monolith now has typed
`Mapped`/`mapped_column` definitions in `identity`, `streams`, `recordings`,
`notifications`, `system`, `upstream` and `proxies`; `_legacy.py` only reexports
those identical classes. Relationships are explicit typed counterparts of the
old backrefs, preserving cardinality/cascades. All 24 exported model definitions
share the original Base; exact pre-extraction SQLite/PostgreSQL DDL, defaults,
column/attribute names and relationships are frozen in
`tests/fixtures/model-schema-baseline.json` (captured at b55754aa before edits).
Nullable legacy columns remain nullable even when they have non-null defaults;
annotations do not silently tighten persisted data. No migration or stored value
change accompanies extraction. Dormant priority/handoff storage is unchanged.

Models must ultimately hold persistence/data invariants, not session creation,
filesystem probes, provider calls or worker scheduling. `Streamer.is_recording`
now reads a typed SQLAlchemy `column_property` snapshot computed by an indexed,
correlated EXISTS in the caller's ordinary SELECT. Its getter has no session or
query lookup; transient models remain false, and loaded values survive detach.
This is a query-time snapshot, not an implicit live poll: callers that reuse a
session after a state transition must explicitly refresh/requery. Ordinary ORM
expiration rules still apply; this is not permission to transport ORM instances
across task/session boundaries. SQLite and actual PostgreSQL observe one SELECT
for four status values instead of five, with unchanged status predicate/schema.
The standard mapping is documented at
<https://docs.sqlalchemy.org/en/20/orm/mapped_sql_expr.html#using-column-property>.
Proxy codec resolution and other legacy model/session boundaries remain open;
extraction and this projection do **not** fulfill the whole hybrid-I/O contract.

Feature repositories own query/loading/transaction details. Application services
own decisions, state transitions and explicit outcomes. API adapters own bounded
request validation, current-user/scopes/CSRF enforcement and mapping to unchanged
responses. Media/process and provider adapters own their physical I/O. Typed
records cross these boundaries; no increased broad Any/ignore exclusions or
ORM-shaped transport payloads.

## 5. Existing safety contracts remain authoritative

Keep durable capture ownership, lease CAS/fencing, physical PID/PGID/start identity
and guarded admission. Unknown process state is not dead/completed. Discovery is
read-only; adoption is explicit and transactional. Deletion preserves catalog and
retry targets until required file removal is proven. Cleanup is preview-first,
explicitly confirmed and identity-bound. Queue handler failures remain failures;
retry budgets/backoff/dependency outcomes agree in both worker modes.

Current active DB-user policy and scopes determine admin access for every existing
credential form. Preserve atomic refresh families, replay revocation, legacy
sessions, cookie paths and configured security, SSRF/path/media protections and
WebSocket authentication. Exactly the three supported public precache icons stay
public; no blanket static/data/admin authorization exception. The successor #900
pluginAutoUpdate activated-to-reload client change is not implemented here.

## 6. Operational ownership and proof

Every task/process has an owner, name, observed outcome, bounded operation and
awaited cleanup. Managed HTTP clients retain policy-specific validation,
timeouts/pools/retry/error/redaction limits and close with their owner. Critical
and optional services have explicit distinct status; background failure cannot be
silently reported as successful readiness.

Liveness, readiness, authenticated diagnostics and metrics have distinct purposes.
Readiness checks the configured database/migration state, paths, required tools,
persistent identities and critical owner task state without exposing secrets.
Request/job/recording identifiers remain structured and redacted across worker
boundaries; diagnostics must not require unbounded blocking work.

Each vertical conversion requires regression-first proof, unchanged frozen public
contracts, current-policy authorization controls, real session/resource isolation,
loop responsiveness, cancellation/failure/restart checks and actual user-flow
execution. Final evidence includes matched performance/resource measurements,
real fresh/legacy/interrupted/concurrent PostgreSQL and native image/restart/media
scenarios, dependency/security scans, frontend/browser gates, exact-head CI and
one independent whole-candidate review. The acceptance matrix, not this target
text or an intermediate green suite, determines completion.
