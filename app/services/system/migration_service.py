"""
Migration service for StreamVault database migrations.

This service handles database migrations using separate migration files.

Foundations (Phase 2):
- The tracking table is created via SQLAlchemy inspection/create so fresh
  SQLite databases (and PostgreSQL) work without PostgreSQL-only
  ``information_schema`` queries.
- Migration execution is serialized (PostgreSQL advisory lock) and
  idempotent: only successful migrations are recorded. A failed migration is
  never marked applied and stays pending for the next run.
- Transactions are owned explicitly: the tracking-table writes use
  ``engine.begin()`` and nothing commits on behalf of a migration script.
"""

import os
import glob
import logging
import importlib.util
import inspect as py_inspect
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    inspect as sa_inspect,
    text,
)

from app.database import engine

logger = logging.getLogger("streamvault")

_MIGRATIONS_SAFE_NAME = "migrations"


class MigrationService:
    _POSTGRES_MIGRATION_LOCK_ID = 6005076117384319316

    @classmethod
    @contextmanager
    def _migration_orchestration_lock(cls) -> Iterator[None]:
        """Serialize the complete migration sequence between PostgreSQL processes."""
        if engine.dialect.name != "postgresql":
            yield
            return

        with engine.connect() as lock_connection:
            logger.info("Waiting for PostgreSQL migration orchestration lock...")
            lock_connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"),
                {"lock_id": cls._POSTGRES_MIGRATION_LOCK_ID},
            )
            logger.info("PostgreSQL migration orchestration lock acquired")
            try:
                yield
            finally:
                lock_connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": cls._POSTGRES_MIGRATION_LOCK_ID},
                )
                logger.info("PostgreSQL migration orchestration lock released")

    @classmethod
    def _migrations_table_definition(cls) -> Table:
        """Return the Core Table definition for the tracking table."""
        metadata = MetaData()
        return Table(
            _MIGRATIONS_SAFE_NAME,
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("script_name", String(255), nullable=False, unique=True),
            Column(
                "applied_at",
                DateTime(timezone=True),
                server_default=text("CURRENT_TIMESTAMP"),
            ),
            Column("success", Boolean, nullable=False, server_default=text("TRUE")),
        )

    @staticmethod
    def ensure_migrations_table():
        """Create the migrations table if it doesn't exist (dialect-agnostic).

        Uses SQLAlchemy inspection instead of PostgreSQL-only
        ``information_schema`` queries so SQLite startup works. The legacy
        ``name``/missing-column fixups are preserved.
        """
        try:
            with engine.connect() as connection:
                inspector = sa_inspect(connection)
                if not inspector.has_table(_MIGRATIONS_SAFE_NAME):
                    logger.info("Creating migrations table...")
                    table = MigrationService._migrations_table_definition()
                    with engine.begin() as setup_connection:
                        table.create(setup_connection, checkfirst=True)
                    logger.info("✅ Migrations table created")
                    return

                columns = {
                    column["name"]
                    for column in inspector.get_columns(_MIGRATIONS_SAFE_NAME)
                }
                if "script_name" not in columns:
                    logger.info("Updating migrations table schema...")
                    with engine.begin() as setup_connection:
                        if "name" in columns:
                            setup_connection.execute(
                                text(
                                    "ALTER TABLE migrations RENAME COLUMN name TO script_name"
                                )
                            )
                            logger.info("✅ Renamed 'name' column to 'script_name'")
                        else:
                            setup_connection.execute(
                                text(
                                    "ALTER TABLE migrations ADD COLUMN script_name VARCHAR(255)"
                                )
                            )
                            logger.info("✅ Added 'script_name' column")
                else:
                    logger.info(
                        "✅ Migrations table already exists with correct schema"
                    )
        except Exception as e:
            logger.error(f"❌ Failed to ensure migrations table: {e}")
            raise

    @staticmethod
    def is_migration_applied(migration_name: str) -> bool:
        """Check if a migration has been applied (successfully)."""
        try:
            with engine.connect() as connection:
                result = connection.execute(
                    text(
                        "SELECT COUNT(*) FROM migrations "
                        "WHERE script_name = :name AND success = TRUE"
                    ),
                    {"name": migration_name},
                ).scalar()
                return result > 0
        except Exception as e:
            logger.error(f"Error checking migration status: {e}")
            raise

    @staticmethod
    def mark_migration_applied(migration_name: str, success: bool = True):
        """Record a successful migration only.

        A failed migration is never recorded (``success=False`` is a no-op) so
        it stays pending and is retried on the next run. The write is an
        explicit transaction owned by ``engine.begin()``.
        """
        if not success:
            logger.warning(
                f"Skipping failure record for migration {migration_name} "
                "(only successful migrations are recorded)"
            )
            return
        try:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO migrations (script_name, applied_at, success)
                        VALUES (:name, CURRENT_TIMESTAMP, TRUE)
                        ON CONFLICT (script_name) DO UPDATE SET
                            applied_at = CURRENT_TIMESTAMP,
                            success = TRUE
                        """
                    ),
                    {"name": migration_name},
                )
        except Exception as e:
            logger.error(f"Error marking migration as applied: {e}")
            raise

    @classmethod
    def run_migrations(cls):
        """Run all database migrations"""
        logger.info("🔄 Starting database migrations...")

        with cls._migration_orchestration_lock():
            # Ensure migrations table exists
            cls.ensure_migrations_table()

            # Run all file-based migrations from the migrations directory
            file_migration_results = cls._run_pending_migrations()

        successful_migrations = len([r for r in file_migration_results if r[1]])
        failed_migrations = len([r for r in file_migration_results if not r[1]])

        logger.info(
            f"🎯 Migration summary: {successful_migrations} successful, {failed_migrations} failed"
        )
        return failed_migrations == 0

    @staticmethod
    def run_safe_migrations():
        """Run all database migrations safely (alias for run_migrations)"""
        return MigrationService.run_migrations()

    @staticmethod
    def get_all_migration_scripts() -> List[str]:
        """Get all migration scripts from the migrations directory"""
        # Based on Dockerfile structure:
        # This service is at: /app/app/services/system/migration_service.py
        # Migrations are at: /app/migrations/
        # Path depth constants for clarity
        MIGRATION_SERVICE_DEPTH = 3  # From /app/app/services/system/ to /app/
        FALLBACK_DEPTH = 2  # From /app/app/services/system/ to /app/app/

        current_file = Path(__file__)

        # Try the correct path based on Dockerfile structure
        migrations_dir = (
            current_file.parents[MIGRATION_SERVICE_DEPTH] / "migrations"
        )  # /app/migrations

        if not migrations_dir.exists() or not migrations_dir.is_dir():
            logger.warning(
                f"Expected migrations directory not found at: {migrations_dir}"
            )
            # Try fallback paths
            fallback_paths = [
                Path("/app/migrations"),  # Absolute path
                Path("./migrations"),  # Relative to working directory
                current_file.parents[FALLBACK_DEPTH]
                / "migrations",  # /app/app/migrations
            ]

            for path in fallback_paths:
                if path.exists() and path.is_dir():
                    migrations_dir = path
                    logger.info(
                        f"Found migrations directory at fallback path: {migrations_dir}"
                    )
                    break
            else:
                logger.error(
                    f"Could not find migrations directory. Tried paths: {[str(p) for p in fallback_paths]}"
                )
                return []
        else:
            logger.info(f"Found migrations directory at: {migrations_dir}")

        # Get migration scripts - prioritize new numbered system
        migration_scripts = []

        # First, look for new numbered migrations (001_, 002_, etc.)
        numbered_migrations = glob.glob(str(migrations_dir / "[0-9][0-9][0-9]_*.py"))
        if numbered_migrations:
            numbered_migrations.sort()  # Sort numerically
            migration_scripts.extend(numbered_migrations)
            logger.info(f"Found {len(numbered_migrations)} numbered migrations")

        # Then, get any old migrations that haven't been moved to backup
        old_migrations = glob.glob(str(migrations_dir / "20[0-9][0-9]*_*.py"))
        if old_migrations:
            old_migrations.sort()  # Sort by date
            migration_scripts.extend(old_migrations)
            logger.info(f"Found {len(old_migrations)} old date-based migrations")

        # Filter out non-migration files
        migration_scripts = [
            script
            for script in migration_scripts
            if os.path.basename(script) not in ["__init__.py", "manage.py", "README.md"]
        ]

        logger.info(
            f"Found {len(migration_scripts)} migration scripts in {migrations_dir}"
        )
        for script in migration_scripts:
            logger.debug(f"Migration script: {os.path.basename(script)}")

        return migration_scripts

    @staticmethod
    def _invoke(migration_function, target_engine):
        """Invoke a migration function, injecting the engine when it accepts one.

        Migrations exposing ``upgrade(target_engine=None)`` (e.g. 039/040/041)
        receive the engine explicitly so they can be tested against isolated
        databases; plain ``upgrade()``/``run_migration()`` scripts keep working
        unchanged.
        """
        try:
            signature = py_inspect.signature(migration_function)
            parameters = list(signature.parameters.values())
        except (TypeError, ValueError):
            parameters = None

        if parameters:
            first = parameters[0].name
            if first == "target_engine":
                return migration_function(target_engine=target_engine)
            if first == "engine":
                return migration_function(engine=target_engine)
        return migration_function()

    @staticmethod
    def run_migration_script(script_path: str) -> Tuple[bool, str]:
        """Run a single migration script.

        Only successful migrations are recorded; a raised exception leaves no
        record so the migration remains pending.
        """
        script_name = os.path.basename(script_path)
        try:
            logger.info(f"Running migration: {script_name}")

            # Check if this migration was already applied
            if MigrationService.is_migration_applied(script_name):
                logger.info(f"Migration {script_name} already applied, skipping")
                return True, "Already applied"

            # Load the migration module
            spec = importlib.util.spec_from_file_location("migration", script_path)
            if not spec or not spec.loader:
                return False, "Could not load migration module"

            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)

            # For simple Alembic-style migrations, we'll use direct SQLAlchemy
            if hasattr(migration_module, "upgrade"):
                MigrationService._invoke(
                    migration_module.upgrade, MigrationService._engine()
                )
            elif hasattr(migration_module, "run_migration"):
                MigrationService._invoke(
                    migration_module.run_migration, MigrationService._engine()
                )
            else:
                return False, "Migration has no upgrade() or run_migration() function"

            MigrationService.mark_migration_applied(script_name)
            logger.info(f"✅ Successfully applied migration: {script_name}")
            return True, "Migration completed successfully"

        except Exception as e:
            logger.error(
                f"Error running migration {script_path}: {str(e)}", exc_info=True
            )
            # Intentionally no record: a failed migration must not be marked applied.
            return False, str(e)

    @staticmethod
    def _engine():
        """Return the active engine used for migration orchestration."""
        lifecycle = getattr(engine, "_lifecycle", None)
        return lifecycle.sync_engine if lifecycle is not None else engine

    @classmethod
    def run_all_migrations(cls) -> List[Tuple[str, bool, str]]:
        """Run all migration scripts in the migrations directory"""
        results = []

        # Get all migration scripts
        migration_scripts = cls.get_all_migration_scripts()
        logger.info(f"Found {len(migration_scripts)} migration scripts")

        # Run each migration script
        for script_path in migration_scripts:
            script_name = os.path.basename(script_path)
            success, message = cls.run_migration_script(script_path)
            results.append((script_name, success, message))

        return results

    @classmethod
    def initialize_migrations_table(cls) -> None:
        """Create a migrations table to track which migrations have been run"""
        cls.ensure_migrations_table()

    @classmethod
    def record_migration(cls, script_name: str, success: bool) -> None:
        """Record a migration run; only successes are persisted."""
        cls.mark_migration_applied(script_name, success)

    @classmethod
    def get_applied_migrations(cls) -> List[str]:
        """Get list of migration scripts that have already been applied"""
        try:
            with engine.connect() as connection:
                result = connection.execute(
                    text(
                        "SELECT script_name FROM migrations WHERE success = TRUE "
                        "ORDER BY applied_at, id"
                    )
                ).fetchall()
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Error getting applied migrations: {str(e)}", exc_info=True)
            raise

    @classmethod
    def run_pending_migrations(cls) -> List[Tuple[str, bool, str]]:
        """Run only migrations that haven't been applied yet"""
        with cls._migration_orchestration_lock():
            return cls._run_pending_migrations()

    @classmethod
    def _run_pending_migrations(cls) -> List[Tuple[str, bool, str]]:
        """Run pending migrations while the orchestration lock is held."""
        try:
            # Wait for database to be ready
            max_retries = 5
            retry_delay = 2

            for attempt in range(max_retries):
                try:
                    with engine.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    logger.info("✅ Database connection successful")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.info(
                            f"Database not ready (attempt {attempt + 1}/{max_retries}), waiting {retry_delay}s..."
                        )
                        import time

                        time.sleep(retry_delay)
                    else:
                        logger.error(
                            f"Failed to connect to database after {max_retries} attempts: {e}"
                        )
                        return [("database_connection", False, str(e))]

            # Ensure migrations table exists
            cls.ensure_migrations_table()

            # Get list of already applied migrations
            applied_migrations = cls.get_applied_migrations()
            logger.info(
                f"Found {len(applied_migrations)} previously applied migrations"
            )

            # Get all available migration scripts
            all_scripts = cls.get_all_migration_scripts()

            # Filter out already applied migrations
            pending_scripts = [
                script
                for script in all_scripts
                if os.path.basename(script) not in applied_migrations
            ]

            if not pending_scripts:
                logger.info("No pending migrations found")
                return []

            logger.info(f"Found {len(pending_scripts)} pending migrations to apply")

            # Run each pending migration
            results = []
            for script_path in pending_scripts:
                script_name = os.path.basename(script_path)
                success, message = cls.run_migration_script(script_path)
                results.append((script_name, success, message))

                # Stop on first failure to maintain consistency
                if not success:
                    logger.error(
                        f"Migration {script_name} failed, stopping migration process"
                    )
                    break

            return results
        except Exception as e:
            logger.error(f"Error running pending migrations: {str(e)}", exc_info=True)
            return [("migration_orchestration", False, str(e))]


# Global migration service instance
migration_service = MigrationService()
