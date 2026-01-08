"""
Migration service for StreamVault database migrations.

This service handles database migrations using separate migration files.
"""

import os
import glob
import logging
import importlib.util
import importlib
from pathlib import Path
from typing import List, Tuple
from sqlalchemy import text

from app.database import engine, SessionLocal

logger = logging.getLogger("streamvault")


class MigrationService:

    @staticmethod
    def ensure_migrations_table():
        """Create the migrations table if it doesn't exist"""
        try:
            with engine.connect() as connection:
                # Check if table exists and what columns it has
                result = connection.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'migrations'
                    AND table_schema = 'public'
                """)).fetchall()

                existing_columns = [row[0] for row in result]

                if not existing_columns:
                    # Table doesn't exist, create it
                    logger.info("Creating migrations table...")
                    connection.execute(text("""
                        CREATE TABLE migrations (
                            id SERIAL PRIMARY KEY,
                            script_name VARCHAR(255) NOT NULL UNIQUE,
                            applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            success BOOLEAN DEFAULT TRUE
                        )
                    """))
                    connection.commit()
                    logger.info("✅ Migrations table created")
                elif 'script_name' not in existing_columns:
                    # Table exists but has old schema, fix it
                    logger.info("Updating migrations table schema...")
                    if 'name' in existing_columns:
                        # Rename old column
                        connection.execute(text("ALTER TABLE migrations RENAME COLUMN name TO script_name"))
                        connection.commit()
                        logger.info("✅ Renamed 'name' column to 'script_name'")
                    else:
                        # Add new column
                        connection.execute(text("ALTER TABLE migrations ADD COLUMN script_name VARCHAR(255)"))
                        connection.commit()
                        logger.info("✅ Added 'script_name' column")
                else:
                    logger.info("✅ Migrations table already exists with correct schema")

        except Exception as e:
            logger.error(f"❌ Failed to ensure migrations table: {e}")
            # Don't raise the exception, just log it
            logger.warning("⚠️ Continuing without migrations table")

    @staticmethod
    def is_migration_applied(migration_name: str) -> bool:
        """Check if a migration has been applied"""
        try:
            with SessionLocal() as db:
                result = db.execute(
                    text("SELECT COUNT(*) FROM migrations WHERE script_name = :name AND success = TRUE"),
                    {"name": migration_name}
                ).scalar()
                return result > 0
        except Exception as e:
            logger.error(f"Error checking migration status: {e}")
            return False

    @staticmethod
    def mark_migration_applied(migration_name: str, success: bool = True):
        """Mark a migration as applied"""
        try:
            with SessionLocal() as db:
                db.execute(
                    text("""
                        INSERT INTO migrations (script_name, applied_at, success)
                        VALUES (:name, NOW(), :success)
                        ON CONFLICT (script_name) DO UPDATE SET
                        applied_at = NOW(), success = :success
                    """),
                    {"name": migration_name, "success": success}
                )
                db.commit()
        except Exception as e:
            logger.error(f"Error marking migration as applied: {e}")

    @staticmethod
    def run_migrations():
        """Run all database migrations"""
        logger.info("🔄 Starting database migrations...")

        # Ensure migrations table exists
        MigrationService.ensure_migrations_table()

        # Run all file-based migrations from the migrations directory
        file_migration_results = MigrationService.run_pending_migrations()

        successful_migrations = len([r for r in file_migration_results if r[1]])
        failed_migrations = len([r for r in file_migration_results if not r[1]])

        logger.info(f"🎯 Migration summary: {successful_migrations} successful, {failed_migrations} failed")
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
        FALLBACK_DEPTH = 2           # From /app/app/services/system/ to /app/app/

        current_file = Path(__file__)

        # Try the correct path based on Dockerfile structure
        migrations_dir = current_file.parents[MIGRATION_SERVICE_DEPTH] / 'migrations'  # /app/migrations

        if not migrations_dir.exists() or not migrations_dir.is_dir():
            logger.warning(f"Expected migrations directory not found at: {migrations_dir}")
            # Try fallback paths
            fallback_paths = [
                Path('/app/migrations'),                                    # Absolute path
                Path('./migrations'),                                      # Relative to working directory
                current_file.parents[FALLBACK_DEPTH] / 'migrations',      # /app/app/migrations
            ]

            for path in fallback_paths:
                if path.exists() and path.is_dir():
                    migrations_dir = path
                    logger.info(f"Found migrations directory at fallback path: {migrations_dir}")
                    break
            else:
                logger.error(f"Could not find migrations directory. Tried paths: {[str(p) for p in fallback_paths]}")
                return []
        else:
            logger.info(f"Found migrations directory at: {migrations_dir}")

        # Get migration scripts - prioritize new numbered system
        migration_scripts = []

        # First, look for new numbered migrations (001_, 002_, etc.)
        numbered_migrations = glob.glob(str(migrations_dir / '[0-9][0-9][0-9]_*.py'))
        if numbered_migrations:
            numbered_migrations.sort()  # Sort numerically
            migration_scripts.extend(numbered_migrations)
            logger.info(f"Found {len(numbered_migrations)} numbered migrations")

        # Then, get any old migrations that haven't been moved to backup
        old_migrations = glob.glob(str(migrations_dir / '20[0-9][0-9]*_*.py'))
        if old_migrations:
            old_migrations.sort()  # Sort by date
            migration_scripts.extend(old_migrations)
            logger.info(f"Found {len(old_migrations)} old date-based migrations")

        # Filter out non-migration files
        migration_scripts = [script for script in migration_scripts if os.path.basename(script) not in [
            '__init__.py', 'manage.py', 'README.md'
        ]]

        logger.info(f"Found {len(migration_scripts)} migration scripts in {migrations_dir}")
        for script in migration_scripts:
            logger.debug(f"Migration script: {os.path.basename(script)}")

        return migration_scripts

    @staticmethod
    def run_migration_script(script_path: str) -> Tuple[bool, str]:
        """Run a single migration script"""
        try:
            script_name = os.path.basename(script_path)
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
            if hasattr(migration_module, 'upgrade'):
                migration_module.upgrade()
                MigrationService.mark_migration_applied(script_name, True)
                logger.info(f"✅ Successfully applied migration: {script_name}")
                return True, "Migration completed successfully"
            elif hasattr(migration_module, 'run_migration'):
                migration_module.run_migration()
                MigrationService.mark_migration_applied(script_name, True)
                logger.info(f"✅ Successfully applied migration: {script_name}")
                return True, "Migration completed successfully"
            else:
                return False, "Migration has no upgrade() or run_migration() function"

        except Exception as e:
            logger.error(f"Error running migration {script_path}: {str(e)}", exc_info=True)
            MigrationService.mark_migration_applied(os.path.basename(script_path), False)
            return False, str(e)

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
        """Record that a migration has been run"""
        cls.mark_migration_applied(script_name, success)

    @classmethod
    def get_applied_migrations(cls) -> List[str]:
        """Get list of migration scripts that have already been applied"""
        try:
            with SessionLocal() as session:
                result = session.execute(
                    text("SELECT script_name FROM migrations WHERE success = TRUE ORDER BY applied_at")
                ).fetchall()
                return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Error getting applied migrations: {str(e)}", exc_info=True)
            return []

    @classmethod
    def run_pending_migrations(cls) -> List[Tuple[str, bool, str]]:
        """Run only migrations that haven't been applied yet"""
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
                        logger.info(f"Database not ready (attempt {attempt + 1}/{max_retries}), waiting {retry_delay}s...")
                        import time
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                        return []

            # Ensure migrations table exists
            cls.ensure_migrations_table()

            # Get list of already applied migrations
            applied_migrations = cls.get_applied_migrations()
            logger.info(f"Found {len(applied_migrations)} previously applied migrations")

            # Get all available migration scripts
            all_scripts = cls.get_all_migration_scripts()

            # Filter out already applied migrations
            pending_scripts = [
                script for script in all_scripts
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
                    logger.error(f"Migration {script_name} failed, stopping migration process")
                    break

            return results
        except Exception as e:
            logger.error(f"Error running pending migrations: {str(e)}", exc_info=True)
            return []


# Global migration service instance
migration_service = MigrationService()
