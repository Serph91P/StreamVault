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

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
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
    ALEMBIC_LEGACY_BASELINE = "20260922_legacy"
    LEGACY_MIGRATION_IDENTITIES = (
        "001_create_base_tables.py",
        "002_create_main_entities.py",
        "003_create_dependent_tables.py",
        "004_add_database_indexes.py",
        "005_add_max_streams_columns.py",
        "006_add_cleanup_policy_columns.py",
        "007_add_proxy_settings.py",
        "008_add_active_recording_fields.py",
        "009_add_cascade_constraints.py",
        "010_setup_category_images.py",
        "011_add_recording_path_to_streams.py",
        "012_add_created_at_to_recordings.py",
        "013_add_episode_number_to_streams.py",
        "014_add_streamer_preferences.py",
        "015_add_default_settings.py",
        "016_add_use_global_cleanup_policy.py",
        "017_add_xml_chapters_column.py",
        "018_enable_session_cleanup.py",
        "018_remove_unused_metadata_columns.py",
        "019_create_share_tokens.py",
        "019_update_twitch_profile_urls.py",
        "020_remove_unused_metadata_columns.py",
        "021_add_xml_chapters_column.py",
        "022_add_recording_processing_state.py",
        "023_add_last_stream_info.py",
        "024_add_codec_preferences.py",
        "025_add_multi_proxy_support.py",
        "026_encrypt_proxy_credentials.py",
        "027_add_recording_error_tracking.py",
        "028_add_system_notification_settings.py",
        "029_add_is_test_data_flag.py",
        "030_add_notification_state.py",
        "031_add_per_streamer_codecs.py",
        "032_add_proxy_encryption_key.py",
        "033_add_twitch_token_refresh.py",
        "034_add_twitch_access_token.py",
        "035_add_segments_dir_path.py",
        "036_add_streamer_description.py",
        "037_add_api_keys.py",
        "038_add_refresh_tokens.py",
        "038_add_system_state.py",
        "039_add_unique_twitch_stream_id.py",
        "040_add_twitch_upstream_leases.py",
        "041_encrypt_proxy_credentials_after_schema.py",
        "042_add_api_key_expiry.py",
        "043_add_twitch_auth_priority.py",
        "044_twitch_auth_handoff_state.py",
        "20251110_add_streamer_banner.py",
    )
    SUPPORTED_LEGACY_ALIASES = (
        "20250117_add_cascade_constraint_to_active_recordings.py",
        "20250522_add_stream_indices.py",
        "20250609160908_add_recording_path_to_streams.py",
        "20250617_add_proxy_settings.py",
        "20250620_add_push_subscriptions.py",
        "20250620_add_system_config.py",
        "20250625_add_recording_model.py",
        "20250702_setup_category_images.py",
        "20250714_add_active_recordings_state.py",
        "20250714_add_database_indexes.py",
        "20250715_add_episode_number_to_streams.py",
        "20250723_add_created_at_to_recordings.py",
        "add_cleanup_policy.py",
        "add_cleanup_policy_v2.py",
        "add_max_streams.py",
    )

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
        """Bring legacy databases to their final identity and hand off to Alembic."""
        logger.info("🔄 Starting database migrations...")

        with cls._migration_orchestration_lock():
            if cls._alembic_revision() is None:
                cls.ensure_migrations_table()
                file_migration_results = cls._run_pending_migrations()
                if any(not result[1] for result in file_migration_results):
                    logger.error("Legacy migration failed; Alembic bridge not stamped")
                    return False
                cls._bridge_legacy_history_to_alembic()
            else:
                file_migration_results = []
                cls._upgrade_alembic()

        successful_migrations = len([r for r in file_migration_results if r[1]])
        failed_migrations = len([r for r in file_migration_results if not r[1]])

        logger.info(
            f"🎯 Migration summary: {successful_migrations} successful, {failed_migrations} failed"
        )
        return failed_migrations == 0

    @classmethod
    def _alembic_config(cls, connection=None) -> Config:
        """Build an Alembic config rooted at the installed repository."""
        repository_root = Path(__file__).resolve().parents[3]
        config = Config(str(repository_root / "alembic.ini"))
        config.set_main_option(
            "script_location", str(repository_root / "migrations" / "alembic")
        )
        # Migrations run inside the application process. Alembic's default
        # fileConfig call would replace the host's handlers (including test
        # capture and production structured logging).
        config.attributes["configure_logger"] = False
        if connection is not None:
            config.attributes["connection"] = connection
        return config

    @classmethod
    def _alembic_revision(cls) -> str | None:
        """Return the database's Alembic identity without creating its table."""
        target = cls._engine()
        with target.connect() as connection:
            inspector = sa_inspect(connection)
            if not inspector.has_table("alembic_version"):
                return None
            return MigrationContext.configure(connection).get_current_revision()

    @classmethod
    def _upgrade_alembic(cls) -> None:
        """Apply canonical Alembic revisions using the active engine."""
        target = cls._engine()
        with target.begin() as connection:
            command.upgrade(cls._alembic_config(connection), "head")

    @classmethod
    def _bridge_legacy_history_to_alembic(cls) -> None:
        """Stamp the exact, complete legacy ledger without changing app data."""
        applied = set(cls.get_applied_migrations())
        required = set(cls.LEGACY_MIGRATION_IDENTITIES)
        supported = required | set(cls.SUPPORTED_LEGACY_ALIASES)
        unknown = sorted(applied - supported)
        if unknown:
            raise RuntimeError(
                "unsupported legacy migration identities: " + ", ".join(unknown)
            )
        missing = sorted(required - applied)
        if missing:
            raise RuntimeError(
                "legacy migration history is incomplete: " + ", ".join(missing)
            )

        target = cls._engine()
        with target.begin() as connection:
            config = cls._alembic_config(connection)
            command.stamp(config, cls.ALEMBIC_LEGACY_BASELINE)
            command.upgrade(config, "head")

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
