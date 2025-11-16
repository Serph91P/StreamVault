"""
Migration 031: Add per-streamer codec preferences

Adds 'supported_codecs' column to streamer_recording_settings table
to allow each streamer to have custom codec preferences.

Without OAuth: Only H.264 available
With OAuth: H.265/HEVC and AV1 available (if streamer broadcasts in those codecs)

Default: NULL (uses global setting from GlobalSettings.supported_codecs)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

def upgrade():
    """Add supported_codecs column to streamer_recording_settings"""
    
    # Get database connection to check dialect
    conn = op.get_bind()
    dialect = conn.dialect.name
    
    print("🔄 Migration 031: Adding per-streamer codec preferences...")
    
    # Add supported_codecs column (nullable - NULL means use global default)
    try:
        op.add_column(
            'streamer_recording_settings',
            sa.Column('supported_codecs', sa.String(), nullable=True)
        )
        print("✅ Added supported_codecs column to streamer_recording_settings")
    except Exception as e:
        print(f"⚠️ Column supported_codecs might already exist: {e}")
    
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


def downgrade():
    """Remove supported_codecs column from streamer_recording_settings"""
    
    print("🔄 Rolling back Migration 031...")
    
    try:
        op.drop_column('streamer_recording_settings', 'supported_codecs')
        print("✅ Removed supported_codecs column from streamer_recording_settings")
    except Exception as e:
        print(f"⚠️ Could not remove supported_codecs column: {e}")
    
    print("✅ Migration 031 rollback completed")
