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
        session = Session()
        
        # First check if streams table exists
        table_exists = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'streams'
            );
        """)).scalar()
        
        if not table_exists:
            logger.info("Table 'streams' does not exist yet, skipping recording_path column addition...")
            if session:
                session.close()
            return
        
        # Check if the column already exists (PostgreSQL)
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

if __name__ == "__main__":
    run_migration()
