"""
Migration 014: Add streamer preference fields
Adds is_favorite and auto_record columns to streamers table
"""

import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("migration")

def upgrade(session: Session):
    """Add preference fields to streamers table"""
    logger.info("🔄 Adding preference fields to streamers table...")
    
    try:
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
        session.rollback()
        raise

def downgrade(session: Session):
    """Remove preference fields from streamers table"""
    logger.info("🔄 Removing preference fields from streamers table...")
    
    try:
        # Remove indexes
        session.execute(text("DROP INDEX IF EXISTS idx_streamers_is_favorite"))
        session.execute(text("DROP INDEX IF EXISTS idx_streamers_auto_record"))
        
        # Remove columns
        session.execute(text("ALTER TABLE streamers DROP COLUMN IF EXISTS is_favorite"))
        session.execute(text("ALTER TABLE streamers DROP COLUMN IF EXISTS auto_record"))
        
        session.commit()
        logger.info("🎉 Migration 014 downgrade completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration 014 downgrade failed: {e}")
        session.rollback()
        raise
