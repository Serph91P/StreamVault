#!/usr/bin/env python
"""
Migration 016: Add use_global_cleanup_policy flag to streamer settings
Adds a flag to control whether streamers use global cleanup policy or custom settings
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DatabaseError, OperationalError

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from app.config.settings import settings
from sqlalchemy.engine import Engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration(target_engine: Engine | None = None):
    """Add use_global_cleanup_policy flag to streamer_recording_settings"""
    session = None
    try:
        # Validate DATABASE_URL
        if target_engine is None and not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")

        # Connect to the database
        engine = (
            target_engine
            if target_engine is not None
            else create_engine(settings.DATABASE_URL)
        )
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info(
            "🔄 Adding use_global_cleanup_policy column to streamer_recording_settings..."
        )

        # Use SQLAlchemy's introspection for database-agnostic column checking
        inspector = inspect(engine)
        columns = inspector.get_columns("streamer_recording_settings")
        column_names = [col["name"] for col in columns]

        if "use_global_cleanup_policy" in column_names:
            logger.info("✅ Column use_global_cleanup_policy already exists, skipping")
            return True

        logger.info("🔄 Adding use_global_cleanup_policy column...")

        # Use database-agnostic approach
        database_url = engine.dialect.name

        if "postgresql" in database_url:
            # PostgreSQL syntax
            session.execute(
                text(
                    """
                ALTER TABLE streamer_recording_settings
                ADD COLUMN use_global_cleanup_policy BOOLEAN NOT NULL DEFAULT TRUE
            """
                )
            )
        elif "sqlite" in database_url:
            # SQLite syntax (SQLite uses INTEGER for boolean, 1 for TRUE)
            session.execute(
                text(
                    """
                ALTER TABLE streamer_recording_settings
                ADD COLUMN use_global_cleanup_policy INTEGER NOT NULL DEFAULT 1
            """
                )
            )
        else:
            # Generic fallback
            session.execute(
                text(
                    """
                ALTER TABLE streamer_recording_settings
                ADD COLUMN use_global_cleanup_policy BOOLEAN NOT NULL DEFAULT TRUE
            """
                )
            )

        session.commit()

        logger.info(
            "✅ Added use_global_cleanup_policy column to streamer_recording_settings"
        )
        logger.info("✅ Migration 016 completed successfully")
        return True

    except (DatabaseError, OperationalError) as e:
        if session:
            session.rollback()
        logger.error(f"❌ Database operation failed: {e}")
        raise
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"❌ Migration 016 failed: {e}")
        raise
    finally:
        if session:
            session.close()


if __name__ == "__main__":
    run_migration()
