"""
Add offline_image_url (banner) to streamers table

This migration adds support for Twitch streamer banners (offline images)
which are displayed on streamer profile pages and can be used in NFO files
for media server integration.

Twitch provides these banners via the /users endpoint as `offline_image_url`.

Run with: python migrations/20251110_add_streamer_banner.py
Or manually: psql streamvault < migrations/20251110_add_streamer_banner.sql
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streamvault")

def upgrade():
    """Add offline_image_url column to streamers table"""
    logger.info("📦 Adding offline_image_url column to streamers table...")
    
    try:
        with engine.connect() as conn:
            # Add offline_image_url column
            conn.execute(text("""
                ALTER TABLE streamers 
                ADD COLUMN IF NOT EXISTS offline_image_url VARCHAR
            """))
            
            # Add original_offline_image_url for fallback
            conn.execute(text("""
                ALTER TABLE streamers 
                ADD COLUMN IF NOT EXISTS original_offline_image_url VARCHAR
            """))
            
            conn.commit()
            
        logger.info("✅ Successfully added banner columns to streamers table")
        
    except Exception as e:
        logger.error(f"❌ Error adding banner columns: {e}")
        raise

def downgrade():
    """Remove offline_image_url columns from streamers table"""
    logger.info("📦 Removing offline_image_url columns from streamers table...")
    
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE streamers 
                DROP COLUMN IF EXISTS offline_image_url,
                DROP COLUMN IF EXISTS original_offline_image_url
            """))
            
            conn.commit()
            
        logger.info("✅ Successfully removed banner columns from streamers table")
        
    except Exception as e:
        logger.error(f"❌ Error removing banner columns: {e}")
        raise

if __name__ == "__main__":
    upgrade()
