#!/usr/bin/env python
"""
Migration 006: Add cleanup_policy columns
Adds cleanup_policy to recording_settings and streamer_recording_settings tables
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
    """Add cleanup_policy columns to recording settings tables"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Adding cleanup_policy columns...")
        
        # Add cleanup_policy to recording_settings
        session.execute(text("""
            ALTER TABLE recording_settings 
            ADD COLUMN IF NOT EXISTS cleanup_policy TEXT
        """))
        logger.info("✅ Added cleanup_policy to recording_settings")
        
        # Add cleanup_policy to streamer_recording_settings
        session.execute(text("""
            ALTER TABLE streamer_recording_settings 
            ADD COLUMN IF NOT EXISTS cleanup_policy TEXT
        """))
        logger.info("✅ Added cleanup_policy to streamer_recording_settings")
        
        session.commit()
        logger.info("🎉 Migration 006 completed successfully")
        
    except Exception as e:
        logger.error(f"Migration 006 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()

if __name__ == "__main__":
    run_migration()