#!/usr/bin/env python
"""
Migration 016: Add use_global_cleanup_policy flag to streamer settings
Adds a flag to control whether streamers use global cleanup policy or custom settings
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DatabaseError, OperationalError

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add use_global_cleanup_policy flag to streamer_recording_settings"""
    session = None
    try:
        # Validate DATABASE_URL
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")
            
        logger.info("Creating database engine...")
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("Adding use_global_cleanup_policy column to streamer_recording_settings...")
        
        # Check if column already exists
        check_column_sql = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'streamer_recording_settings' 
            AND column_name = 'use_global_cleanup_policy'
        """)
        
        result = session.execute(check_column_sql).fetchone()
        
        if result:
            logger.info("✅ Column use_global_cleanup_policy already exists, skipping")
            return True
        
        # Add the new column with default True (use global settings by default)
        add_column_sql = text("""
            ALTER TABLE streamer_recording_settings 
            ADD COLUMN use_global_cleanup_policy BOOLEAN NOT NULL DEFAULT true
        """)
        
        session.execute(add_column_sql)
        session.commit()
        
        logger.info("✅ Added use_global_cleanup_policy column to streamer_recording_settings")
        return True
        
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"❌ Migration failed: {e}")
        raise
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    run_migration()
