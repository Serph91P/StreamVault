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

1. Create a new Python file in this directory with a zero-padded numeric
   prefix (e.g. `042_my_change.py`)
2. Implement an `upgrade()` function that performs the database changes
3. Handle errors appropriately in your migration
4. Test your migration locally before deploying

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

## Alembic Compatibility / Removal Plan

The numbered custom migration system predates Alembic. The long-term target
is to converge on Alembic while keeping deployments safe:

1. **Bridge (only if fully testable without schema/data changes)**: a safe
   bridge could stamp Alembic's `alembic_version` table from the existing
   `migrations` table and treat future changes as Alembic revisions. Because
   the two systems must never run the same DDL twice, the bridge must be offline-tested
   against a fresh SQLite database and a copy of an existing production-shaped
   database before being enabled. No bridge is enabled yet.
2. **Migration of numbered scripts**: fold retained numbered scripts into
   Alembic revisions (`alembic revision --autogenerate`) once a baseline is
   established, mapping each `migrations` row to its equivalent revision.
3. **Removal**: custom file discovery and the advisory-lock orchestration
   remain until Alembic owns orchestration; then `ensure_migrations_table`
   becomes Alembic's own bookkeeping and the custom runner is deleted.

## Example Migration

```python
#!/usr/bin/env python
"""
Migration description
"""
import logging
from sqlalchemy import text
from app.database import engine

logger = logging.getLogger("streamvault")


def upgrade(target_engine=None):
    """Migration implementation function"""
    target = target_engine or engine
    with target.begin() as connection:
        connection.execute(text("ALTER TABLE my_table ADD COLUMN new_column INT"))
    logger.info("Migration completed successfully")
```

## Migration Service

The migration service manages the process of:

1. Identifying which migrations need to be run
2. Running migrations in a consistent way
3. Recording successful migrations
4. Handling migration failures

You don't need to interact with the service directly. It runs automatically
when the application starts.