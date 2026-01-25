#!/usr/bin/env python
"""
Migration 013: Add episode_number column to streams table
Tracks episode numbers persistently in the database
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Add episode_number column to streams table"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("🔄 Adding episode_number to streams table...")

        # Check if column already exists
        result = session.execute(
            text(
                """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'streams'
            AND column_name = 'episode_number'
        """
            )
        )

        if result.scalar() > 0:
            logger.info("Column episode_number already exists in streams table")
            return

        # Add the episode_number column
        session.execute(text("ALTER TABLE streams ADD COLUMN episode_number INTEGER"))

        session.commit()
        logger.info("🎉 Migration 013 completed successfully")

    except Exception as e:
        logger.error(f"Migration 013 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()


if __name__ == "__main__":
    run_migration()
