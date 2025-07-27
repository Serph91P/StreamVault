#!/usr/bin/env python
"""
Migration 005: Add max_streams columns
Adds max_streams_per_streamer to recording_settings and max_streams to streamer_recording_settings
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
    """Add max_streams columns to recording settings tables"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Adding max_streams columns...")
        
        # Add max_streams_per_streamer to recording_settings
        session.execute(text("""
            ALTER TABLE recording_settings 
            ADD COLUMN IF NOT EXISTS max_streams_per_streamer INTEGER DEFAULT 0
        """))
        logger.info("✅ Added max_streams_per_streamer to recording_settings")
        
        # Add max_streams to streamer_recording_settings
        session.execute(text("""
            ALTER TABLE streamer_recording_settings 
            ADD COLUMN IF NOT EXISTS max_streams INTEGER DEFAULT NULL
        """))
        logger.info("✅ Added max_streams to streamer_recording_settings")
        
        session.commit()
        logger.info("🎉 Migration 005 completed successfully")
        
    except Exception as e:
        logger.error(f"Migration 005 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()

if __name__ == "__main__":
    run_migration()