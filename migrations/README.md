# StreamVault Database Migrations

This directory contains database migration scripts for StreamVault.

## How Migrations Work

1. Migrations are automatically run when the application starts
2. Each migration script is run only once
3. Successful migrations are recorded in the database
4. New migrations are identified and applied on each restart
5. The run sequence is serialized (PostgreSQL advisory lock) and idempotent

## Creating New Migrations

To create a new migration:

1. Run `alembic revision -m "describe the change"`.
2. Implement `upgrade()` in the generated revision under
   `migrations/alembic/versions` using Alembic operations or SQLAlchemy Core.
3. Keep the revision independent of application ORM models and make downgrade
   behavior explicitly data-safe.
4. Exercise the revision on fresh and upgraded PostgreSQL databases before
   deploying.

## Migration Invocation Contract (Phase 2 persistence foundation)

The migration service loads each script and invokes the first of
`upgrade()` / `run_migration()` that is present. Scripts that expose
`upgrade(target_engine=None)` (the Alembic-style signatures used by
`039`/`040`/`041`) receive the current engine explicitly so they can be
exercised against isolated test databases; plain no-argument functions keep
working unchanged.

### Run guarantees

- **Serialized**: the complete discovery + apply sequence holds a PostgreSQL
  advisory lock (`6005076117384319316`) when running against PostgreSQL.
  SQLite requires no lock.
- **Idempotent**: already-applied scripts are skipped; re-running the
  sequence is a no-op.
- **Only successful migrations are recorded**: the service writes the
  tracking row only after `upgrade()`/`run_migration()` returns without
  raising. A failed migration leaves no `success` record and remains pending
  for the next run — it is never marked applied.
- **Explicit transaction ownership**: tracking-table writes use
  `engine.begin()`; the service never commits on behalf of a migration, and
  no generic repository hides commits inside a script.
- **No data resets**: migrations only add/alter schema (and repair data in
  idempotent ways); nothing drops or truncates user data.

### Tracking table

The `migrations` table is created on demand through SQLAlchemy inspection
(`inspect(engine).has_table(...)`) and Core `Table.create(...)`, so fresh
SQLite databases start up without PostgreSQL-only `information_schema`
queries. Legacy schema fixups (renaming `name` → `script_name`, adding
`script_name`) are preserved.

## Alembic bridge

The numbered migration system predates Alembic. Startup now performs a one-way,
lossless handoff:

1. A database that already has an `alembic_version` identity runs only canonical
   Alembic revisions.
2. An unversioned database completes the frozen numbered migration ledger while
   holding the existing PostgreSQL advisory lock.
3. The bridge verifies all 48 required script identities. It also accepts the 15
   documented date/name identities retained in `old_migrations_backup`; any other
   successful identity fails closed for operator review.
4. Only a complete successful ledger is stamped as `20260922_legacy`. The bridge
   revision contains no schema or data operations, so stamping cannot replay DDL
   or modify application rows. Future migrations must be Alembic revisions below
   `migrations/alembic/versions`.

Interrupted runs remain safe: successful numbered migrations are retained, a
failure is not recorded or stamped, and restart resumes at the first missing
identity. PostgreSQL first starts remain serialized across processes. Historical
migration files use SQLAlchemy Core rather than current ORM models.

Before upgrading, back up the PostgreSQL database using the deployment's normal
backup procedure. On failure, keep the database and restart after correcting the
reported migration; do not delete migration rows or manually stamp Alembic. A
rollback restores the pre-upgrade database backup together with the matching
application image. Downgrading the baseline revision intentionally does not drop
legacy tables or user data.

The destructive real-PostgreSQL acceptance probe requires a disposable database
whose name ends in `_migration_test`:

```bash
PYTHONPATH=. \
  DATABASE_URL=postgresql+psycopg://.../streamvault_migration_test \
  .venv/bin/python tests/postgres_alembic_bridge_probe.py
```

It covers fresh, current, representative legacy (`name` ledger), interrupted,
concurrent first-start and immediate-restart paths while comparing schema identity
and asserting sentinel data preservation.

## Example Alembic revision

```python
"""Add a column without importing application ORM models."""

from alembic import op
import sqlalchemy as sa

revision = "20261001_example"
down_revision = "20260922_legacy"


def upgrade() -> None:
    op.add_column("my_table", sa.Column("new_column", sa.Integer()))


def downgrade() -> None:
    op.drop_column("my_table", "new_column")
```

## Migration Service

The migration service manages the process of:

1. Identifying which migrations need to be run
2. Running migrations in a consistent way
3. Recording successful migrations
4. Handling migration failures

You don't need to interact with the service directly. It runs automatically
when the application starts.