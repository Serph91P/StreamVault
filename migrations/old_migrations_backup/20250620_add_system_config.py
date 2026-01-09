"""
Migration to create system_config table for persistent configuration storage.
Used for storing VAPID keys and other system-wide settings.
"""

import logging
from sqlalchemy import create_engine, text
from sqlalchemy.engine import reflection
import os

logger = logging.getLogger("streamvault")


def apply_migration():
    """Apply the system_config table migration"""
    try:
        logger.info("Starting system_config table migration...")

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL not found in environment")
            return False

        # Ensure the URL uses the correct psycopg3 driver
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://")

        engine = create_engine(database_url)

        with engine.connect() as connection:
            # Check if table already exists
            inspector = reflection.Inspector.from_engine(engine)
            if "system_config" in inspector.get_table_names():
                logger.info("system_config table already exists, skipping migration")
                return True

            # Create system_config table
            logger.info("Creating system_config table...")

            create_table_sql = """
            CREATE TABLE system_config (
                id SERIAL PRIMARY KEY,
                key VARCHAR UNIQUE NOT NULL,
                value TEXT NOT NULL,
                description VARCHAR,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE INDEX idx_system_config_key ON system_config(key);
            """

            connection.execute(text(create_table_sql))
            connection.commit()

            logger.info("✅ system_config table created successfully")
            return True

    except Exception as e:
        logger.error(f"❌ Failed to create system_config table: {e}")
        return False


def rollback_migration():
    """Rollback the system_config table migration"""
    try:
        logger.info("Rolling back system_config table migration...")

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL not found in environment")
            return False

        # Ensure the URL uses the correct psycopg3 driver
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://")

        engine = create_engine(database_url)

        with engine.connect() as connection:
            connection.execute(text("DROP TABLE IF EXISTS system_config CASCADE;"))
            connection.commit()

        logger.info("✅ system_config table rollback completed")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to rollback system_config table: {e}")
        return False


def run_migration():
    """Main migration function called by migration runner"""
    return apply_migration()


def upgrade():
    """Alembic-style upgrade function"""
    return apply_migration()


if __name__ == "__main__":
    apply_migration()
