# ADR-001: Database I/O and incremental typed model split

- Status: Accepted category slice; #842 hybrid amendment pending independent PR1070 review
- Date: 2026-09-22
- Issue: https://github.com/Serph91P/StreamVault/issues/842
- Base: `develop@61eef2b097f1fb2ddb893056ef4b6c823bb950e6`

## Context

StreamVault is an async FastAPI application, but most request paths still execute synchronous SQLAlchemy sessions directly on the event loop. A lazy `AsyncEngine`/`AsyncSession` foundation and three async repositories also exist, so the application currently has two I/O styles. `app/models.py` additionally registers all 24 tables in one untyped module. A big-bang conversion would put PostgreSQL data, recording/playback identity, migration history, and public API contracts at unnecessary risk.

The production runtime is CPython 3.14 and PostgreSQL. SQLite remains a test backend only. Alembic adoption and migration orchestration are explicitly handled in P6, not by this decision.

## Decision

The original category/favorite decision uses SQLAlchemy 2 `AsyncSession` and `select()` repositories. That already integrated slice is preserved. The originally proposed universal convergence is superseded by the measured hybrid amendment below, not used to justify another category rewrite.

Rules:

1. FastAPI dependencies create one request-scoped `AsyncSession` via `get_async_db`.
2. Repositories execute queries and may add/delete/flush, but do not silently commit or rollback.
3. The service boundary owns write commit/rollback. Route handlers own neither sessions nor transactions.
4. ORM relationships used after an await must be eagerly loaded or avoided; no hidden lazy I/O is allowed.
5. Synchronous work must not run on the async event loop. Remaining legacy units follow the complete-worker/session/DTO boundary below. Any later async conversion must be vertical (dependency, repository, service, route, tests), not another mixed call chain.
6. Models move feature-by-feature into `app.models.<feature>` using `Mapped`/`mapped_column`. `app.models` remains the stable re-export surface until all callers intentionally migrate.
7. Wire schemas stay in `app.schemas`; ORM models must not become API schemas.

## #842 measured hybrid amendment

The implemented target permits two explicit boundaries: the existing category async transaction, and complete synchronous units executed by the existing cancellation-draining worker helper. This is a bounded application architecture, not permission for inline legacy SQL or a claim that every call site has passed verification.

For the second boundary, the application supplies its own session factory, Settings/root, logger and dependent services. Open/query/project/commit-or-rollback/close happen in the same worker unit. Only immutable scalar values/DTOs and owned non-ORM resources escape it; no request Session or mapped row crosses a transport/task await. Filesystem and blocking process operations belong inside that unit too. Cancellation must drain the owned operation before returning; existing admission, transport, subprocess and shutdown budgets are retained. This helper is not a promise that arbitrary unbounded synchronous third-party code becomes interruptible.

Factory composition/import remains nonmutating. Lifecycle initializes persistent identities and app resources explicitly, and closes only that application's tasks/clients/processes. Stable legacy synchronous entry points remain available for their explicit standalone callers, not as implicit alternate owners for requests.

The same-lock/CPython3.14.10/PostgreSQL18 comparison in [backend-performance.md](../architecture/backend-performance.md) ran three fresh matched base49b61a8/candidatecf30e62 pairs. Startup median was 4.573824→4.628688s, post-startup RSS168416→169328KiB, and image719388752→719524109bytes. Catalog median/p95 was28.039/51.552→23.029/34.930ms with unchanged12SQL statements; streamer reads were21.104→24.105ms and44→43statements. Queue46.544602→45.901111jobs/s and several tail latencies worsen. Full tables, raw samples, profiling, provenance and limitations are in that document. There is no global performance win or elimination-of-N+1 claim.

Choose the hybrid for demonstrated ownership/session/cancellation correctness while preserving the already integrated async slice and the PostgreSQL/API/schema contracts. The experiment does not justify a risky universal ORM/driver rewrite, nor prove maximum throughput. Costs are thread-token plus connection-pool coordination, explicit DTO projection, and cancellation/drain complexity; the dedicated boundary/peer/cancellation tests and real-PG operational checks are required mitigations. A future async conversion needs a concrete workload/contract benefit and the same vertical regression evidence, not the old universal-convergence assertion.

Rollback remains source-only for these boundaries: restore one verified application revision and its composition together. This amendment creates no migration, rotates no identity, changes no schema and authorizes no live rollback/deployment. Module coverage, strict rewritten-code typing and final exact-head CI are independent gates, not inferred from these performance measurements.

## Preserved contracts and invariants

- `app.main:app`, port 7000, environment names, Compose/Unraid and UID/GID contracts are unchanged.
- All existing table names, column names/order/types/nullability/defaults, foreign keys, constraints, and indexes remain unchanged. This ADR creates no migration.
- `from app.models import <Model>` remains valid and resolves to the same single mapped class used by `Base.metadata`.
- All 24 historical tables register exactly once when `app.models` is imported.
- Category paths, methods, operation IDs, status codes, and response fields remain unchanged.
- Favorite writes are atomic at the service boundary; failures roll back the request session.
- Recording, playback, stream, and lease identifiers are untouched.
- Importing model modules does not construct an engine or connect to the database.

## First slice

`Category` and `FavoriteCategory` move to `app/models/categories.py` with typed SQLAlchemy 2 mappings. `app/models/__init__.py` explicitly re-exports every historical model while the untouched declarations live temporarily in `_legacy.py`. The category repository and service become async end to end, and the four category CRUD routes await that boundary.

The split is intentionally narrow: it proves package import compatibility, metadata stability, cross-module relationships to `User`, explicit transactions, and API compatibility before higher-risk stream/recording models move.

## Alternatives rejected

### Keep synchronous sessions on async routes

Rejected: synchronous SQL directly on the async event loop. The original decision also classified complete worker units as transitional only; the amendment supersedes that restriction for explicitly scoped, cancellation-drained units. It retains the stated coordination/cancellation costs rather than pretending a threadpool removes them.

### Convert all models and call sites at once

Rejected because the monolith has hundreds of sync session call sites and high-risk recording, migration, lease, and recovery behavior. Review and rollback would be unsafe.

### Rename tables or generate a migration during the split

Rejected. Module layout and Python typing do not require schema changes. P6 owns migration-engine work.

## Risks and mitigations

- Duplicate mapper/table registration: explicit package imports plus a 24-table metadata regression.
- Circular model imports: string relationship targets and a single package composition root.
- Async lazy-loading failures: repositories return only data the service serializes directly; later slices require explicit eager loading.
- Partial commits: repositories only flush; services commit or roll back.
- SQLite sync/async in-memory isolation in tests: integration tests use a file-backed database; PostgreSQL checks remain authoritative.
- API drift: frozen OpenAPI/route tests and representative endpoint response tests.
- PostgreSQL differences: run fresh/current/restart integration and the real-PostgreSQL suite before approval.

## Verification and rollout

Each extraction requires a demonstrated RED before implementation and GREEN afterward for:

- package/re-export identity and typed mapping;
- complete metadata plus exact affected-table contract;
- representative relationship round-trip;
- async repository/service transaction behavior;
- route dependency/await structure and OpenAPI contract.

Quality gates are CPython 3.14 focused/full tests, Ruff format/check, configured mypy scope, Bandit on changed production paths, `git diff --check`, and real PostgreSQL fresh/current/restart where locally available. Rollback is one commit: restore the affected declarations and sync category boundary; no database rollback is needed because this slice changes no schema or data.

## Next bounded work packages

1. Extract identity/auth models after transaction and concurrency tests cover refresh-token families.
2. Extract stream/recording models only with explicit eager-load and identity regressions.
3. Convert another repository/service/route vertical to `AsyncSession` only when a concrete measured or contractual need justifies it; remove that vertical's old request boundary together.
4. `_legacy.py` removal/model extraction is independent of driver selection. The amended hybrid intentionally retains the scoped sync engine and explicit standalone compatibility; it does not promise universal `SessionLocal` removal.
