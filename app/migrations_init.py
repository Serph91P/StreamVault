"""
Migration initialization script to run pending migrations at application startup
"""
import logging
import os
from app.services.system.migration_service import MigrationService
from app.config.settings import settings

logger = logging.getLogger("streamvault")

def run_migrations() -> None:
    """Run all pending database migrations"""
    # Ensure we have a valid database connection before proceeding
    if not settings.DATABASE_URL:
        logger.error("No database URL configured. Skipping migrations.")
        return

    # In development mode, we rely on the entrypoint.sh script
    if os.getenv("ENVIRONMENT") == "development":
        logger.info("Development mode: migrations will be handled by entrypoint.sh")
        return
        
    logger.info("Production mode: Checking for pending database migrations...")
    
    results = MigrationService.run_pending_migrations()
    
    if not results:
        logger.info("No migrations were applied - database is up to date")
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
