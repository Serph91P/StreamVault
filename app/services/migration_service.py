"""
Migration service for StreamVault database migrations.

This service handles database migrations using separate migration files.
"""

import os
import glob
import logging
import importlib.util
import importlib
from typing import List, Tuple
from sqlalchemy import text, inspect
from sqlalchemy.sql import func

from app.database import engine, SessionLocal
from app.config.settings import get_settings

logger = logging.getLogger("streamvault")

class MigrationService:
    
    @staticmethod
    def ensure_migrations_table():
        """Create the migrations table if it doesn't exist"""
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE
                )
            """))
            connection.commit()
            
    @staticmethod
    def is_migration_applied(migration_name: str) -> bool:
        """Check if a migration has been applied"""
        try:
            with SessionLocal() as db:
                result = db.execute(
                    text("SELECT COUNT(*) FROM migrations WHERE name = :name AND success = TRUE"),
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
                    text("INSERT INTO migrations (name, success) VALUES (:name, :success) ON CONFLICT (name) DO UPDATE SET success = :success"),
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
        
        # All migrations are now file-based in the migrations/ directory
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
        migrations_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'migrations')
        migration_scripts = glob.glob(os.path.join(migrations_dir, '*.py'))
        # Filter out __init__.py and any other non-migration files
        migration_scripts = [script for script in migration_scripts if os.path.basename(script) != '__init__.py' 
                            and os.path.basename(script) != 'create_migration.py'
                            and os.path.basename(script) != 'template_migration.py'
                            and os.path.basename(script) != 'manage.py']
        return migration_scripts
    
    @staticmethod
    def run_migration_script(script_path: str) -> Tuple[bool, str]:
        """Run a single migration script"""
        try:
            script_name = os.path.basename(script_path)
            logger.info(f"Running migration: {script_name}")
            
            # Check if this migration was already applied
            applied_migrations = MigrationService.get_applied_migrations()
            if script_name in applied_migrations:
                logger.info(f"Migration {script_name} already applied, skipping")
                return True, f"Migration {script_name} already applied"
            
            # Load the migration module
            spec = importlib.util.spec_from_file_location("migration", script_path)
            if not spec or not spec.loader:
                return False, f"Failed to load module for {script_name}"
                
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            
            # For simple Alembic-style migrations, we'll use direct SQLAlchemy
            if hasattr(migration_module, 'upgrade'):
                logger.info(f"Running simplified migration: {script_name}")
                
                # Create a simple mock alembic op for basic operations
                class SimpleOp:
                    @staticmethod
                    def add_column(table_name: str, column):
                        """Add a column to a table"""
                        try:
                            with engine.connect() as conn:
                                # Check if column already exists
                                result = conn.execute(text(f"""
                                    SELECT column_name 
                                    FROM information_schema.columns 
                                    WHERE table_name = '{table_name}' AND column_name = '{column.name}'
                                """))
                                
                                if result.fetchone() is None:
                                    # Column doesn't exist, add it
                                    sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {column.type}"
                                    if column.nullable:
                                        sql += " NULL"
                                    else:
                                        sql += " NOT NULL"
                                    
                                    conn.execute(text(sql))
                                    conn.commit()
                                    logger.info(f"Added column {column.name} to {table_name}")
                                else:
                                    logger.info(f"Column {column.name} already exists in {table_name}")
                        except Exception as e:
                            logger.warning(f"Error adding column {column.name} to {table_name}: {e}")
                    
                    @staticmethod
                    def drop_column(table_name: str, column_name: str):
                        """Drop a column from a table"""
                        try:
                            with engine.connect() as conn:
                                # Check if column exists
                                result = conn.execute(text(f"""
                                    SELECT column_name 
                                    FROM information_schema.columns 
                                    WHERE table_name = '{table_name}' AND column_name = '{column_name}'
                                """))
                                
                                if result.fetchone() is not None:
                                    # Column exists, drop it
                                    conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {column_name}"))
                                    conn.commit()
                                    logger.info(f"Dropped column {column_name} from {table_name}")
                                else:
                                    logger.info(f"Column {column_name} doesn't exist in {table_name}")
                        except Exception as e:
                            logger.warning(f"Error dropping column {column_name} from {table_name}: {e}")
                
                # Add the op object to the migration module's namespace
                setattr(migration_module, 'op', SimpleOp())
                
                # Run the upgrade function
                migration_module.upgrade()
                
                logger.info(f"Successfully ran migration: {script_name}")
                return True, f"Successfully ran migration: {script_name}"
            
            # Look for legacy run_migration function
            elif hasattr(migration_module, 'run_migration'):
                migration_module.run_migration()
                logger.info(f"Successfully ran migration: {script_name}")
                return True, f"Successfully ran migration: {script_name}"
            else:
                logger.warning(f"Migration script {script_name} does not have run_migration or upgrade function")
                return False, f"Migration script {script_name} does not have a compatible migration function"
                
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
        from sqlalchemy import Column, String, DateTime, Boolean, MetaData as SQLMetaData, Table
        from sqlalchemy.sql import text
        import datetime
        
        try:
            # Check if migrations table exists
            metadata = SQLMetaData()
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
                # Use INSERT ... ON CONFLICT DO NOTHING to avoid duplicate key errors
                session.execute(
                    text("""
                    INSERT INTO migrations (script_name, applied_at, success) 
                    VALUES (:script_name, NOW(), :success)
                    ON CONFLICT (script_name) DO NOTHING
                    """),
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
                
                # Record the migration (but handle duplicates gracefully)
                cls.record_migration(script_name, success)
            
            return results
        except Exception as e:
            logger.error(f"Error running pending migrations: {str(e)}", exc_info=True)
            return []
