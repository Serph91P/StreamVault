"""
Migration 031: Add per-streamer codec preferences

Adds 'supported_codecs' column to streamer_recording_settings table
to allow each streamer to have custom codec preferences.

Without OAuth: Only H.264 available
With OAuth: H.265/HEVC and AV1 available (if streamer broadcasts in those codecs)

Default: NULL (uses global setting from GlobalSettings.supported_codecs)
"""

from sqlalchemy import text

def upgrade(session):
    """Add supported_codecs column to streamer_recording_settings
    
    Args:
        session: SQLAlchemy session (provided by migration service)
    """
    
    print("🔄 Migration 031: Adding per-streamer codec preferences...")
    
    try:
        # Check if column already exists
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'streamer_recording_settings' 
            AND column_name = 'supported_codecs'
        """))
        
        if result.fetchone() is None:
            # Add supported_codecs column (nullable - NULL means use global default)
            session.execute(text("""
                ALTER TABLE streamer_recording_settings 
                ADD COLUMN supported_codecs VARCHAR(255) DEFAULT NULL
            """))
            session.commit()
            print("✅ Added supported_codecs column to streamer_recording_settings")
        else:
            print("ℹ️ Column supported_codecs already exists, skipping")
        
        # No default value - NULL means "use global setting from GlobalSettings.supported_codecs"
        # This allows:
        # - NULL: Use global default (most streamers)
        # - "h264": Force H.264 only for specific streamer
        # - "h265,h264": Use H.265 with H.264 fallback
        # - "av1,h265,h264": Try AV1 first, then H.265, then H.264
        
        print("✅ Migration 031 completed successfully")
        print("💡 Per-streamer codec preferences now available")
        print("   - NULL = use global setting (default)")
        print("   - Custom = override for specific streamer")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error in migration 031: {e}")
        raise


def downgrade(session):
    """Remove supported_codecs column from streamer_recording_settings
    
    Args:
        session: SQLAlchemy session (provided by migration service)
    """
    
    print("🔄 Rolling back Migration 031...")
    
    try:
        # Check if column exists before trying to drop it
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'streamer_recording_settings' 
            AND column_name = 'supported_codecs'
        """))
        
        if result.fetchone() is not None:
            session.execute(text("""
                ALTER TABLE streamer_recording_settings 
                DROP COLUMN IF EXISTS supported_codecs
            """))
            session.commit()
            print("✅ Removed supported_codecs column from streamer_recording_settings")
        else:
            print("ℹ️ Column supported_codecs does not exist, skipping")
        
        print("✅ Migration 031 rollback completed")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error in migration 031 rollback: {e}")
        raise
