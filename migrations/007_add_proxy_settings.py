#!/usr/bin/env python
"""
Migration 007: Add proxy settings
Adds http_proxy and https_proxy columns to global_settings table
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
    """Add proxy settings columns to global_settings table"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Adding proxy settings columns...")
        
        # Add http_proxy column
        session.execute(text("""
            ALTER TABLE global_settings 
            ADD COLUMN IF NOT EXISTS http_proxy VARCHAR(255)
        """))
        logger.info("✅ Added http_proxy to global_settings")
        
        # Add https_proxy column
        session.execute(text("""
            ALTER TABLE global_settings 
            ADD COLUMN IF NOT EXISTS https_proxy VARCHAR(255)
        """))
        logger.info("✅ Added https_proxy to global_settings")
        
        session.commit()
        logger.info("🎉 Migration 007 completed successfully")
        
    except Exception as e:
        logger.error(f"Migration 007 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()

if __name__ == "__main__":
    run_migration()