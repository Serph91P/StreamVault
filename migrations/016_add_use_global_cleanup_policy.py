#!/usr/bin/env python
"""
Migration 016: Add use_global_cleanup_policy flag to streamer settings
Adds a flag to control whether streamers use global cleanup policy or custom settings
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text, MetaData, Table, Column, Boolean, inspect
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
        # Validate DATABASE_URL more thoroughly
        if not settings.DATABASE_URL or not settings.DATABASE_URL.strip():
            raise ValueError("DATABASE_URL is not configured or is empty/whitespace-only")
            
        logger.info("Creating database engine...")
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("Checking if use_global_cleanup_policy column exists...")
        
        # Use SQLAlchemy's introspection for database-agnostic column checking
        inspector = inspect(engine)
        columns = inspector.get_columns('streamer_recording_settings')
        column_names = [col['name'] for col in columns]
        
        if 'use_global_cleanup_policy' in column_names:
            logger.info("✅ Column use_global_cleanup_policy already exists, skipping")
            return True
        
        logger.info("Adding use_global_cleanup_policy column...")
        
        # Use SQLAlchemy's DDL operations for database-agnostic column addition
        metadata = MetaData()
        streamer_table = Table('streamer_recording_settings', metadata, autoload_with=engine)
        
        new_column = Column('use_global_cleanup_policy', Boolean, nullable=False, server_default='true')
        
        # Use DDL to add the column
        from sqlalchemy.schema import AddColumn
        add_column_ddl = AddColumn(streamer_table, new_column)
        engine.execute(add_column_ddl)
        
        logger.info("✅ Added use_global_cleanup_policy column to streamer_recording_settings")
        return True
        
    except (DatabaseError, OperationalError) as e:
        if session:
            session.rollback()
        logger.error(f"❌ Database operation failed: {e}")
        raise
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"❌ Unexpected error during migration: {e}")
        raise
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    run_migration()
