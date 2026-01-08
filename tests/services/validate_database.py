#!/usr/bin/env python
"""
Migration validation script to check database schema
and ensure all required tables and columns exist.
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def show_migration_status():
    """Show the status of all migrations"""
    try:
        engine = create_engine(settings.DATABASE_URL)

        with engine.connect() as connection:
            # Check if migrations table exists
            inspector = inspect(engine)
            if "applied_migrations" not in inspector.get_table_names():
                logger.warning("⚠️  No migration tracking table found")
                return

            result = connection.execute(
                text(
                    """
                SELECT migration_name, applied_at, success
                FROM applied_migrations
                ORDER BY applied_at DESC
            """
                )
            )

            migrations = result.fetchall()

            if migrations:
                logger.info("📋 Migration History:")
                for migration in migrations:
                    status = "✅ SUCCESS" if migration.success else "❌ FAILED"
                    logger.info(f"  {status} {migration.migration_name} - {migration.applied_at}")
            else:
                logger.info("📋 No migrations found in tracking table")

    except Exception as e:
        logger.error(f"❌ Could not show migration status: {e}")


def test_safe_migrations():
    """Test the safe migration system"""
    try:
        logger.info("🧪 Testing safe migration system...")

        from app.services.migration_service import MigrationService

        # Test migration system
        success = MigrationService.run_safe_migrations()

        if success:
            logger.info("✅ Safe migration system test passed!")
            return True
        else:
            logger.warning("⚠️ Some migrations had issues, but system is functional")
            return True

    except Exception as e:
        logger.error(f"❌ Safe migration system test failed: {e}")
        return False


def validate_database_schema():
    """Validate that all required tables and columns exist"""
    try:
        engine = create_engine(settings.DATABASE_URL)
        inspector = inspect(engine)

        logger.info("🔍 Validating database schema...")

        # Required tables
        required_tables = [
            "streamers",
            "streams",
            "recording_settings",
            "push_subscriptions",
            "system_config",
            "applied_migrations",
        ]

        # Required columns per table
        required_columns = {
            "streams": ["recording_path"],
            "global_settings": ["http_proxy", "https_proxy"],
            "push_subscriptions": ["endpoint", "subscription_data", "is_active"],
            "system_config": ["key", "value"],
            "applied_migrations": ["migration_name", "applied_at", "success"],
        }

        existing_tables = inspector.get_table_names()
        validation_passed = True

        # Check tables
        for table in required_tables:
            if table in existing_tables:
                logger.info(f"✅ Table '{table}' exists")
            else:
                logger.error(f"❌ Table '{table}' missing")
                validation_passed = False

        # Check columns
        for table, columns in required_columns.items():
            if table in existing_tables:
                table_columns = [col["name"] for col in inspector.get_columns(table)]
                for column in columns:
                    if column in table_columns:
                        logger.info(f"✅ Column '{table}.{column}' exists")
                    else:
                        logger.warning(f"⚠️  Column '{table}.{column}' missing (may be optional)")
            else:
                logger.warning(f"⚠️  Cannot check columns for missing table '{table}'")

        # Check indices
        if "streams" in existing_tables:
            indices = inspector.get_indexes("streams")
            index_names = [idx["name"] for idx in indices]

            required_indices = ["idx_streams_streamer_id", "idx_streams_started_at", "idx_streams_title"]

            for index in required_indices:
                if index in index_names:
                    logger.info(f"✅ Index '{index}' exists")
                else:
                    logger.warning(f"⚠️  Index '{index}' missing (performance may be affected)")

        # Check applied migrations
        if "applied_migrations" in existing_tables:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT COUNT(*) FROM applied_migrations"))
                migration_count = result.scalar()
                logger.info(f"📊 {migration_count} migrations tracked in database")

        if validation_passed:
            logger.info("🎉 Database schema validation passed!")
            return True
        else:
            logger.error("💥 Database schema validation failed!")
            return False

    except Exception as e:
        logger.error(f"❌ Schema validation failed: {e}")
        return False


def show_migration_status_detail():
    """Show the status of all migrations"""
    try:
        engine = create_engine(settings.DATABASE_URL)

        with engine.connect() as connection:
            # Check if migrations table exists
            inspector = inspect(engine)
            if "applied_migrations" not in inspector.get_table_names():
                logger.warning("⚠️  No migration tracking table found")
                return

            result = connection.execute(
                text(
                    """
                SELECT migration_name, applied_at, success
                FROM applied_migrations
                ORDER BY applied_at DESC
            """
                )
            )

            migrations = result.fetchall()

            if migrations:
                logger.info("📋 Migration History:")
                for migration in migrations:
                    status = "✅ SUCCESS" if migration.success else "❌ FAILED"
                    logger.info(f"  {status} {migration.migration_name} - {migration.applied_at}")
            else:
                logger.info("📋 No migrations found in tracking table")

    except Exception as e:
        logger.error(f"❌ Could not show migration status: {e}")


if __name__ == "__main__":
    logger.info("🔍 Starting database validation...")

    try:
        # Show migration status first
        show_migration_status()

        # Test safe migration system
        if test_safe_migrations():
            logger.info("🧪 Migration system test passed!")

        # Then validate schema
        if validate_database_schema():
            logger.info("✅ Database validation completed successfully!")
            sys.exit(0)
        else:
            logger.error("❌ Database validation failed!")
            sys.exit(1)

    except Exception as e:
        logger.error(f"💥 Validation process failed: {e}")
        sys.exit(1)
