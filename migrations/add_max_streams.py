#!/usr/bin/env python
"""
Migration script to add max_streams fields to the database
"""
import os
import sys
import logging
from sqlalchemy import create_engine, Column, Integer, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add max_streams columns to the database tables"""
    try:
        # Connect to the database
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if the columns already exist
        inspector = inspect(engine)
        recording_columns = [c['name'] for c in inspector.get_columns('recording_settings')]
        streamer_columns = [c['name'] for c in inspector.get_columns('streamer_recording_settings')]
        
        # Add max_streams_per_streamer column to recording_settings if it doesn't exist
        if 'max_streams_per_streamer' not in recording_columns:
            logger.info("Adding max_streams_per_streamer column to recording_settings table")
            session.execute(text("ALTER TABLE recording_settings ADD COLUMN max_streams_per_streamer INTEGER DEFAULT 0"))
            session.commit()
        else:
            logger.info("max_streams_per_streamer column already exists in recording_settings table")
        
        # Add max_streams column to streamer_recording_settings if it doesn't exist
        if 'max_streams' not in streamer_columns:
            logger.info("Adding max_streams column to streamer_recording_settings table")
            session.execute(text("ALTER TABLE streamer_recording_settings ADD COLUMN max_streams INTEGER DEFAULT NULL"))
            session.commit()
        else:
            logger.info("max_streams column already exists in streamer_recording_settings table")
            
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()
