#!/usr/bin/env python
"""
Migration 017: Add chapters_xml_path column to stream_metadata
Adds a column to store XML chapter file paths for Emby/Jellyfin compatibility
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
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
    """Add chapters_xml_path column to stream_metadata"""
    session = None
    try:
        # Validate DATABASE_URL
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")
        
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Adding chapters_xml_path column to stream_metadata...")
        
        # Use SQLAlchemy's introspection for database-agnostic column checking
        inspector = inspect(engine)
        columns = inspector.get_columns('stream_metadata')
        column_names = [col['name'] for col in columns]
        
        if 'chapters_xml_path' in column_names and 'tvshow_nfo_path' in column_names and 'season_nfo_path' in column_names:
            logger.info("✅ All required metadata path columns already exist, skipping")
            return True
        
        logger.info("🔄 Adding missing metadata path columns to stream_metadata...")
        
        # List of all metadata path columns that should exist and are actually used
        required_columns = {
            'chapters_xml_path': 'TEXT',  # XML chapters for Emby/Jellyfin - actually generated
            'tvshow_nfo_path': 'TEXT',    # TVShow NFO file path - actually generated
            'season_nfo_path': 'TEXT',    # Season NFO file path - actually generated
        }
        
        columns_added = 0
        for column_name, column_type in required_columns.items():
            if column_name not in column_names:
                logger.info(f"🔄 Adding {column_name} column...")
                session.execute(text(f"""
                    ALTER TABLE stream_metadata 
                    ADD COLUMN {column_name} {column_type}
                """))
                columns_added += 1
                logger.info(f"✅ Added {column_name} column to stream_metadata")
            else:
                logger.info(f"✅ Column {column_name} already exists, skipping")
        
        if columns_added > 0:
            session.commit()
            logger.info(f"✅ Added {columns_added} missing metadata path columns")
        else:
            logger.info("✅ All metadata path columns already exist")
            
        logger.info("✅ Migration 017 completed successfully")
        return True
        
    except (DatabaseError, OperationalError) as e:
        if session:
            session.rollback()
        logger.error(f"❌ Database operation failed: {e}")
        raise
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"❌ Migration 017 failed: {e}")
        raise
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    run_migration()
