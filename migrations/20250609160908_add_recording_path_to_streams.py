#!/usr/bin/env python
"""
Migration to add recording_path to streams
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
    """
    Adds the recording_path column to the streams table.
    """
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()        # Check if the column already exists (PostgreSQL)
        result = session.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'streams' 
            AND column_name = 'recording_path'
        """))
        column_exists = result.scalar() > 0

        if column_exists:
            logger.info("Column recording_path already exists in streams table. Skipping migration.")
            return

        # Add the recording_path column to the streams table
        # Making it nullable, VARCHAR with a reasonable length
        session.execute(text("ALTER TABLE streams ADD COLUMN recording_path VARCHAR(1024) NULL"))
        session.commit()

        logger.info("Migration to add recording_path to streams completed successfully")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if session:
            session.rollback() # Rollback in case of error
        raise
    finally:
        if session and session.is_active:
            session.close()

# Example of how a downgrade might look, though the current runner might not support it.
# def downgrade_migration():
#     """
#     Removes the recording_path column from the streams table.
#     """
#     try:
#         engine = create_engine(settings.DATABASE_URL)
#         Session = sessionmaker(bind=engine)
#         session = Session()
#         session.execute(text("ALTER TABLE streams DROP COLUMN recording_path"))
#         session.commit()
#         logger.info("Migration to remove recording_path from streams completed successfully")
#     except Exception as e:
#         logger.error(f"Downgrade migration failed: {e}")
#         session.rollback()
#         raise
#     finally:
#         if 'session' in locals() and session.is_active:
#             session.close()

if __name__ == "__main__":
    # This script would typically be run by a migration runner,
    # but can be executed directly for testing if DATABASE_URL is set.
    # For example:
    # DATABASE_URL="postgresql://user:pass@host/db" python migrations/your_migration_file.py
    if os.getenv("DATABASE_URL"):
        logger.info("Running migration directly for testing purposes...")
        run_migration()
    else:
        logger.info("DATABASE_URL not set. Skipping direct execution."
                    " This script is intended to be run by a migration management tool.")
