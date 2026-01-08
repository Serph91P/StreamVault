"""
Migration initialization script to run pending migrations at application startup
"""

import logging
from app.config.settings import settings

logger = logging.getLogger("streamvault")


def run_migrations() -> None:
    """Run all pending database migrations"""
    # Ensure we have a valid database connection before proceeding
    if not settings.DATABASE_URL:
        logger.error("No database URL configured. Skipping migrations.")
        return

    logger.info("🔄 Running database migrations...")

    try:
        # Use the unified migration service that handles both numbered and old migrations
        from app.services.system.migration_service import MigrationService

        results = MigrationService.run_pending_migrations()

        if not results:
            logger.info("No migrations were applied - database is up to date")
            return

        # Log migration results
        for result in results:
            migration_name, success, message = result  # Ensure consistent 3-element tuple unpacking
            if success:
                logger.info(f"✅ Successfully applied migration: {migration_name}")
            else:
                logger.error(f"❌ Failed to apply migration: {migration_name}")

    except Exception as e:
        logger.error(f"❌ Error during migrations: {e}")
        # In production, don't crash the app due to migration failures
        # Instead, continue with a warning
        logger.warning("⚠️ Continuing application startup despite migration issues")
        return

    success_count = sum(1 for _, success, _ in results if success)
    failed_count = len(results) - success_count

    if failed_count > 0:
        logger.warning(f"Applied {success_count} migrations, {failed_count} migrations failed")
        for script_name, success, message in results:
            if not success:
                logger.error(f"Migration failed: {script_name} - {message}")
    else:
        logger.info(f"Successfully applied {success_count} migrations")
        for script_name, _, _ in results:
            logger.info(f"Applied migration: {script_name}")
