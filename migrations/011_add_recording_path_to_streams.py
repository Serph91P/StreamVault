#!/usr/bin/env python
"""
Migration 011: Add recording_path to streams table
Adds recording_path column for storing the path to stream recordings
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
    """Add recording_path column to streams table"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("🔄 Adding recording_path to streams table...")

        # Check if the column already exists
        result = session.execute(
            text(
                """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name = 'streams'
            AND column_name = 'recording_path'
        """
            )
        )
        column_exists = result.scalar() > 0

        if column_exists:
            logger.info("Column recording_path already exists in streams table")
            return

        # Add the recording_path column
        session.execute(
            text(
                """
            ALTER TABLE streams
            ADD COLUMN recording_path VARCHAR(1024) NULL
        """
            )
        )

        session.commit()
        logger.info("🎉 Migration 011 completed successfully")

    except Exception as e:
        logger.error(f"Migration 011 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()


if __name__ == "__main__":
    run_migration()
