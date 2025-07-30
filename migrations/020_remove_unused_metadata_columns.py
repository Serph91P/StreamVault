#!/usr/bin/env python
"""
Migration 020: Remove unused metadata columns
Removes chat_path, chat_srt_path, and chapters_path columns as they are never used
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
    """Remove unused metadata columns from stream_metadata"""
    session = None
    try:
        # Validate DATABASE_URL
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")
        
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Removing unused metadata columns from stream_metadata...")
        
        # Use SQLAlchemy's introspection for database-agnostic column checking
        inspector = inspect(engine)
        columns = inspector.get_columns('stream_metadata')
        column_names = [col['name'] for col in columns]
        
        # List of unused columns to remove (hardcoded whitelist for security)
        unused_columns = ['chat_path', 'chat_srt_path', 'chapters_path']
        
        # Security: Validate column names against whitelist before SQL execution
        allowed_columns = {'chat_path', 'chat_srt_path', 'chapters_path'}
        
        columns_removed = 0
        for column_name in unused_columns:
            # Security check: only allow whitelisted column names
            if column_name not in allowed_columns:
                logger.error(f"❌ Column {column_name} not in allowed whitelist - skipping for security")
                continue
                
            if column_name in column_names:
                logger.info(f"🔄 Removing unused column {column_name}...")
                # Use whitelisted column name directly (no user input)
                if column_name == 'chat_path':
                    session.execute(text("ALTER TABLE stream_metadata DROP COLUMN IF EXISTS chat_path"))
                elif column_name == 'chat_srt_path':
                    session.execute(text("ALTER TABLE stream_metadata DROP COLUMN IF EXISTS chat_srt_path"))
                elif column_name == 'chapters_path':
                    session.execute(text("ALTER TABLE stream_metadata DROP COLUMN IF EXISTS chapters_path"))
                
                columns_removed += 1
                logger.info(f"✅ Removed unused column {column_name} from stream_metadata")
            else:
                logger.info(f"✅ Column {column_name} already doesn't exist, skipping")
        
        if columns_removed > 0:
            session.commit()
            logger.info(f"✅ Removed {columns_removed} unused metadata columns")
        else:
            logger.info("✅ All unused columns already removed")
            
        logger.info("✅ Migration 020 completed successfully")
        return True
        
    except (DatabaseError, OperationalError) as e:
        if session:
            session.rollback()
        logger.error(f"❌ Database operation failed: {e}")
        raise
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"❌ Migration 020 failed: {e}")
        raise
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    run_migration()
