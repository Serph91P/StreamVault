#!/usr/bin/env python
"""
Migration: Add proxy settings to GlobalSettings

This migration adds HTTP and HTTPS proxy configuration fields
to the global_settings table for Streamlink proxy support.
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add proxy settings columns to global_settings table"""
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if columns already exist
        inspector = inspect(engine)
        columns = inspector.get_columns('global_settings')
        existing_columns = [col['name'] for col in columns]
        
        # Add http_proxy column if it doesn't exist
        if 'http_proxy' not in existing_columns:
            session.execute(text("""
                ALTER TABLE global_settings 
                ADD COLUMN http_proxy VARCHAR(255)
            """))
            logger.info("Added http_proxy column to global_settings")
        else:
            logger.info("http_proxy column already exists in global_settings")
        
        # Add https_proxy column if it doesn't exist
        if 'https_proxy' not in existing_columns:
            session.execute(text("""
                ALTER TABLE global_settings 
                ADD COLUMN https_proxy VARCHAR(255)
            """))
            logger.info("Added https_proxy column to global_settings")
        else:
            logger.info("https_proxy column already exists in global_settings")
        
        session.commit()
        session.close()
        logger.info("Successfully added proxy settings to global_settings table")
        
    except Exception as e:
        logger.error(f"Error adding proxy settings columns: {e}")
        if 'session' in locals():
            session.rollback()
            session.close()
        raise

if __name__ == "__main__":
    print("This migration adds HTTP/HTTPS proxy support to StreamVault")
    print("Fields added:")
    print("- global_settings.http_proxy")
    print("- global_settings.https_proxy")
    run_migration()
