#!/usr/bin/env python
"""
Migration to index streams table for better performance
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
    Add indices to the streams table to improve query performance
    """
    try:
        # Connect to the database
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if indices exist before creating them
        inspector = engine.dialect.get_inspector(engine)
        existing_indices = inspector.get_indexes('streams')
        existing_index_names = [index['name'] for index in existing_indices]
        
        # Create streamer_id index if it doesn't exist
        if 'idx_streams_streamer_id' not in existing_index_names:
            logger.info("Creating index on streams.streamer_id")
            session.execute(text("CREATE INDEX idx_streams_streamer_id ON streams (streamer_id)"))
        else:
            logger.info("Index on streams.streamer_id already exists")
            
        # Create started_at index if it doesn't exist
        if 'idx_streams_started_at' not in existing_index_names:
            logger.info("Creating index on streams.started_at")
            session.execute(text("CREATE INDEX idx_streams_started_at ON streams (started_at)"))
        else:
            logger.info("Index on streams.started_at already exists")
            
        # Create title index if it doesn't exist (for search functionality)
        if 'idx_streams_title' not in existing_index_names:
            logger.info("Creating index on streams.title")
            session.execute(text("CREATE INDEX idx_streams_title ON streams (title)"))
        else:
            logger.info("Index on streams.title already exists")
        
        # Commit the changes
        session.commit()
        
        logger.info("Stream indices migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
