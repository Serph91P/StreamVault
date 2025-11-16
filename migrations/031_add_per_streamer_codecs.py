"""
Migration 031: Add per-streamer codec preferences

Adds 'supported_codecs' column to streamer_recording_settings table
to allow each streamer to have custom codec preferences.

Without OAuth: Only H.264 available
With OAuth: H.265/HEVC and AV1 available (if streamer broadcasts in those codecs)

Default: NULL (uses global setting from GlobalSettings.supported_codecs)
"""

from sqlalchemy import text
from app.database import engine
import logging

logger = logging.getLogger(__name__)

def upgrade():
    """Add supported_codecs column to streamer_recording_settings"""
    
    logger.info("🔄 Migration 031: Adding per-streamer codec preferences...")
    
    with engine.begin() as connection:
        # Check if column already exists
        result = connection.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'streamer_recording_settings' 
            AND column_name = 'supported_codecs'
        """))
        
        if result.fetchone() is None:
            # Add supported_codecs column (nullable - NULL means use global default)
            connection.execute(text("""
                ALTER TABLE streamer_recording_settings 
                ADD COLUMN supported_codecs VARCHAR(255) DEFAULT NULL
            """))
            logger.info("✅ Added supported_codecs column to streamer_recording_settings")
        else:
            logger.info("ℹ️ Column supported_codecs already exists, skipping")
    
    # No default value - NULL means "use global setting from GlobalSettings.supported_codecs"
    # This allows:
    # - NULL: Use global default (most streamers)
    # - "h264": Force H.264 only for specific streamer
    # - "h265,h264": Use H.265 with H.264 fallback
    # - "av1,h265,h264": Try AV1 first, then H.265, then H.264
    
    logger.info("✅ Migration 031 completed successfully")
    logger.info("💡 Per-streamer codec preferences now available")
    logger.info("   - NULL = use global setting (default)")
    logger.info("   - Custom = override for specific streamer")


def downgrade():
    """Remove supported_codecs column from streamer_recording_settings"""
    
    logger.info("🔄 Rolling back Migration 031...")
    
    with engine.begin() as connection:
        # Check if column exists before trying to drop it
        result = connection.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'streamer_recording_settings' 
            AND column_name = 'supported_codecs'
        """))
        
        if result.fetchone() is not None:
            connection.execute(text("""
                ALTER TABLE streamer_recording_settings 
                DROP COLUMN IF EXISTS supported_codecs
            """))
            logger.info("✅ Removed supported_codecs column from streamer_recording_settings")
        else:
            logger.info("ℹ️ Column supported_codecs does not exist, skipping")
    
    logger.info("✅ Migration 031 rollback completed")


if __name__ == "__main__":
    upgrade()
