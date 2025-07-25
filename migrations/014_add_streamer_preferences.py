#!/usr/bin/env python
"""
Migration 014: Add streamer preference fields
Adds is_favorite and auto_record columns to streamers table
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add preference fields to streamers table"""
    session = None
    try:
        # Validate DATABASE_URL
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")
        
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL, echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Adding preference fields to streamers table...")
        
        # Add is_favorite column
        session.execute(text("""
            ALTER TABLE streamers 
            ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE
        """))
        logger.info("✅ Added is_favorite column to streamers table")
        
        # Add auto_record column
        session.execute(text("""
            ALTER TABLE streamers 
            ADD COLUMN IF NOT EXISTS auto_record BOOLEAN DEFAULT FALSE
        """))
        logger.info("✅ Added auto_record column to streamers table")
        
        # Add indexes for performance
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_streamers_is_favorite 
            ON streamers(is_favorite)
        """))
        logger.info("✅ Added index for is_favorite")
        
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_streamers_auto_record 
            ON streamers(auto_record)
        """))
        logger.info("✅ Added index for auto_record")
        
        session.commit()
        logger.info("🎉 Migration 014 completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration 014 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    run_migration()
