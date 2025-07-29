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
        
        if 'chapters_xml_path' in column_names:
            logger.info("✅ Column chapters_xml_path already exists, skipping")
            return True
        
        logger.info("🔄 Adding chapters_xml_path column...")
        
        # Use database-agnostic approach
        database_url = settings.DATABASE_URL.lower()
        
        if 'postgresql' in database_url:
            # PostgreSQL syntax
            session.execute(text("""
                ALTER TABLE stream_metadata 
                ADD COLUMN chapters_xml_path VARCHAR
            """))
        elif 'sqlite' in database_url:
            # SQLite syntax
            session.execute(text("""
                ALTER TABLE stream_metadata 
                ADD COLUMN chapters_xml_path TEXT
            """))
        else:
            # Generic fallback
            session.execute(text("""
                ALTER TABLE stream_metadata 
                ADD COLUMN chapters_xml_path VARCHAR
            """))
        
        session.commit()
        
        logger.info("✅ Added chapters_xml_path column to stream_metadata")
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
