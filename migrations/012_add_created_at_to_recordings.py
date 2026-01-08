#!/usr/bin/env python
"""
Migration 012: Add created_at field to recordings table
Adds created_at timestamp for tracking when recordings were created
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
    """Add created_at field to recordings table"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("🔄 Adding created_at to recordings table...")

        # Check if the column already exists
        check_column_sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'recordings' AND column_name = 'created_at'
        """

        result = session.execute(text(check_column_sql)).fetchone()

        if result:
            logger.info("Column 'created_at' already exists in recordings table")
            return

        # Add the created_at column with a default value
        session.execute(
            text(
                """
            ALTER TABLE recordings
            ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        """
            )
        )

        # Update existing records to have created_at = start_time
        session.execute(
            text(
                """
            UPDATE recordings
            SET created_at = start_time
            WHERE created_at IS NULL
        """
            )
        )

        session.commit()
        logger.info("🎉 Migration 012 completed successfully")

    except Exception as e:
        logger.error(f"Migration 012 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()


if __name__ == "__main__":
    run_migration()
