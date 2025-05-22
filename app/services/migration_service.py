"""
Migration service to automatically run all migrations on application startup
"""
import os
import importlib.util
import logging
import glob
from typing import List, Tuple

from app.config.settings import settings
from app.database import SessionLocal, engine

logger = logging.getLogger("streamvault")

class MigrationService:
    """Service to manage database migrations"""
    
    @staticmethod
    def get_all_migration_scripts() -> List[str]:
        """Get all migration scripts from the migrations directory"""
        migrations_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'migrations')
        migration_scripts = glob.glob(os.path.join(migrations_dir, '*.py'))
        # Filter out __init__.py and any other non-migration files
        migration_scripts = [script for script in migration_scripts if os.path.basename(script) != '__init__.py']
        return migration_scripts
    
    @staticmethod
    def run_migration_script(script_path: str) -> Tuple[bool, str]:
        """Run a single migration script"""
        try:
            # Get the script filename for logging
            script_name = os.path.basename(script_path)
            logger.info(f"Running migration: {script_name}")
            
            # Load the module dynamically
            spec = importlib.util.spec_from_file_location("migration_module", script_path)
            if not spec or not spec.loader:
                return False, f"Failed to load module for {script_name}"
                
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            
            # Look for and run the migration function
            if hasattr(migration_module, 'run_migration'):
                migration_module.run_migration()
                logger.info(f"Successfully ran migration: {script_name}")
                return True, f"Successfully ran migration: {script_name}"
            else:
                logger.warning(f"Migration script {script_name} does not have a run_migration function")
                return False, f"Migration script {script_name} does not have a run_migration function"
                
        except Exception as e:
            logger.error(f"Error running migration {script_path}: {str(e)}", exc_info=True)
            return False, f"Error running migration {script_path}: {str(e)}"
    
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
        from sqlalchemy import Column, String, DateTime, Boolean, MetaData, Table
        from sqlalchemy.sql import text
        import datetime
        
        try:
            # Check if migrations table exists
            metadata = MetaData()
            migrations_table = Table(
                'migrations',
                metadata,
                Column('script_name', String, primary_key=True),
                Column('applied_at', DateTime, default=datetime.datetime.utcnow),
                Column('success', Boolean, default=True),
            )
            
            # Create table if it doesn't exist
            if not engine.dialect.has_table(engine.connect(), 'migrations'):
                logger.info("Creating migrations table")
                migrations_table.create(engine)
        except Exception as e:
            logger.error(f"Error creating migrations table: {str(e)}", exc_info=True)
    
    @classmethod
    def record_migration(cls, script_name: str, success: bool) -> None:
        """Record that a migration has been run"""
        try:
            with SessionLocal() as session:
                session.execute(
                    text("INSERT INTO migrations (script_name, applied_at, success) VALUES (:script_name, NOW(), :success)"),
                    {"script_name": script_name, "success": success}
                )
                session.commit()
        except Exception as e:
            logger.error(f"Error recording migration: {str(e)}", exc_info=True)
    
    @classmethod
    def get_applied_migrations(cls) -> List[str]:
        """Get list of migration scripts that have already been applied"""
        try:
            with SessionLocal() as session:
                result = session.execute(text("SELECT script_name FROM migrations WHERE success = TRUE"))
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
                    # Initialize migrations table if needed
                    cls.initialize_migrations_table()
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed to connect to database after {max_retries} attempts")
                        raise
                    logger.warning(f"Database not ready (attempt {attempt + 1}/{max_retries}): {e}")
                    import time
                    time.sleep(retry_delay)
            
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
                logger.info("No pending migrations to apply")
                return []
            
            logger.info(f"Found {len(pending_scripts)} pending migrations to apply")
            
            # Run each pending migration
            results = []
            for script_path in pending_scripts:
                script_name = os.path.basename(script_path)
                success, message = cls.run_migration_script(script_path)
                results.append((script_name, success, message))
                
                # Record the migration
                if success:
                    cls.record_migration(script_name, success)
            
            return results
        except Exception as e:
            logger.error(f"Error running pending migrations: {str(e)}", exc_info=True)
            return []
