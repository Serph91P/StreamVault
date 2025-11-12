"""
Migration 024: Add Codec Preferences for H.265/AV1 Support

Adds codec preference settings to enable H.265/AV1 recording via Streamlink 8.0.0+
Requires --twitch-supported-codecs argument support in Streamlink.

Changes:
- Add supported_codecs column to global_settings (default: "h264,h265")
- Add prefer_higher_quality column to global_settings (default: True)

Background:
With Streamlink 8.0.0+, Twitch streams can be recorded in higher quality:
- H.264: Max 1080p60 (legacy, highest compatibility)
- H.265/HEVC: Up to 1440p60 (modern hardware required)
- AV1: Up to 1440p60 (experimental, newest hardware)

Author: StreamVault
Date: 2025-11-12
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal


def upgrade():
    """Add codec preference columns to global_settings"""
    with SessionLocal() as db:
        try:
            # Add supported_codecs column (default: h264,h265 for best compatibility/quality balance)
            db.execute(text("""
                ALTER TABLE global_settings
                ADD COLUMN IF NOT EXISTS supported_codecs VARCHAR NOT NULL DEFAULT 'h264,h265';
            """))
            
            db.execute(text("""
                COMMENT ON COLUMN global_settings.supported_codecs IS 
                'Comma-separated list of supported codecs for Streamlink (h264, h265, av1)';
            """))
            
            # Add prefer_higher_quality column (default: True to auto-select best available quality)
            db.execute(text("""
                ALTER TABLE global_settings
                ADD COLUMN IF NOT EXISTS prefer_higher_quality BOOLEAN NOT NULL DEFAULT true;
            """))
            
            db.execute(text("""
                COMMENT ON COLUMN global_settings.prefer_higher_quality IS 
                'Automatically select highest available quality when using h265/av1';
            """))
            
            db.commit()
            print("✅ Migration 024: Added codec preference columns (supported_codecs, prefer_higher_quality)")
            print("   Default: h264,h265 (H.264 with H.265 fallback)")
            print("   Note: Requires Streamlink 8.0.0+ for --twitch-supported-codecs support")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Migration 024 failed: {e}")
            raise


def downgrade():
    """Remove codec preference columns from global_settings"""
    with SessionLocal() as db:
        try:
            db.execute(text("ALTER TABLE global_settings DROP COLUMN IF EXISTS prefer_higher_quality;"))
            db.execute(text("ALTER TABLE global_settings DROP COLUMN IF EXISTS supported_codecs;"))
            
            db.commit()
            print("✅ Migration 024 (downgrade): Removed codec preference columns")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Migration 024 downgrade failed: {e}")
            raise


if __name__ == "__main__":
    print("Running migration 024: Add codec preferences for H.265/AV1 support...")
    upgrade()
    print("Migration 024 completed successfully!")


