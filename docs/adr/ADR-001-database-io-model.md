# ADR-001: Database I/O and incremental typed model split

- Status: Accepted
- Date: 2026-09-22
- Issue: https://github.com/Serph91P/StreamVault/issues/842
- Base: `develop@61eef2b097f1fb2ddb893056ef4b6c823bb950e6`

## Context

StreamVault is an async FastAPI application, but most request paths still execute synchronous SQLAlchemy sessions directly on the event loop. A lazy `AsyncEngine`/`AsyncSession` foundation and three async repositories also exist, so the application currently has two I/O styles. `app/models.py` additionally registers all 24 tables in one untyped module. A big-bang conversion would put PostgreSQL data, recording/playback identity, migration history, and public API contracts at unnecessary risk.

The production runtime is CPython 3.14 and PostgreSQL. SQLite remains a test backend only. Alembic adoption and migration orchestration are explicitly handled in P6, not by this decision.

## Decision

Async request paths will converge on SQLAlchemy 2 `AsyncSession` and `select()` repositories. The category/favorite path is the first bounded vertical slice because it already has a router/service/repository seam and no recording or playback ownership behavior.

Rules:

1. FastAPI dependencies create one request-scoped `AsyncSession` via `get_async_db`.
2. Repositories execute queries and may add/delete/flush, but do not silently commit or rollback.
3. The service boundary owns write commit/rollback. Route handlers own neither sessions nor transactions.
4. ORM relationships used after an await must be eagerly loaded or avoided; no hidden lazy I/O is allowed.
5. Existing synchronous paths remain compatibility debt and must not call sync SQL directly from newly converted async slices. Each later conversion must be vertical (dependency, repository, service, route, tests) rather than adding another mixed call chain.
6. Models move feature-by-feature into `app.models.<feature>` using `Mapped`/`mapped_column`. `app.models` remains the stable re-export surface until all callers intentionally migrate.
7. Wire schemas stay in `app.schemas`; ORM models must not become API schemas.

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

Wrapping every complete sync unit of work in a bounded threadpool could be coherent, but it retains duplicate concurrency controls (thread tokens plus the SQLAlchemy pool), complicates cancellation, and does not use the already accepted psycopg 3 async foundation. It is permitted only for an unconverted legacy boundary and must be off the event loop; it is not the target architecture.

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
3. Convert one repository/service/route vertical at a time to `AsyncSession`; remove its sync compatibility use in the same change.
4. Remove `_legacy.py`, `SessionLocal`, and the sync engine only after all production call sites are converted and measured.
