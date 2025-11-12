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

from alembic import op
import sqlalchemy as sa


def upgrade():
    """Add codec preference columns to global_settings"""
    
    # Add supported_codecs column (default: h264,h265 for best compatibility/quality balance)
    op.add_column(
        'global_settings',
        sa.Column(
            'supported_codecs',
            sa.String(),
            nullable=False,
            server_default='h264,h265',
            comment='Comma-separated list of supported codecs for Streamlink (h264, h265, av1)'
        )
    )
    
    # Add prefer_higher_quality column (default: True to auto-select best available quality)
    op.add_column(
        'global_settings',
        sa.Column(
            'prefer_higher_quality',
            sa.Boolean(),
            nullable=False,
            server_default='true',
            comment='Automatically select highest available quality when using h265/av1'
        )
    )
    
    print("✅ Migration 024: Added codec preference columns (supported_codecs, prefer_higher_quality)")
    print("   Default: h264,h265 (H.264 with H.265 fallback)")
    print("   Note: Requires Streamlink 8.0.0+ for --twitch-supported-codecs support")


def downgrade():
    """Remove codec preference columns from global_settings"""
    
    op.drop_column('global_settings', 'prefer_higher_quality')
    op.drop_column('global_settings', 'supported_codecs')
    
    print("✅ Migration 024 (downgrade): Removed codec preference columns")
