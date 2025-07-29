"""Add use_global_cleanup_policy flag to streamer settings

Revision ID: 016_add_use_global_cleanup_policy
Revises: 015_add_default_settings
Create Date: 2025-07-29

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '016_add_use_global_cleanup_policy'
down_revision = '015_add_default_settings'
branch_labels = None
depends_on = None

def upgrade():
    """Add use_global_cleanup_policy flag to streamer_recording_settings"""
    
    # Add the new column with default True (use global settings by default)
    op.add_column('streamer_recording_settings', 
                  sa.Column('use_global_cleanup_policy', sa.Boolean(), 
                           nullable=False, server_default=sa.true()))
    
    print("✅ Added use_global_cleanup_policy column to streamer_recording_settings")

def downgrade():
    """Remove use_global_cleanup_policy flag"""
    op.drop_column('streamer_recording_settings', 'use_global_cleanup_policy')
    print("❌ Removed use_global_cleanup_policy column from streamer_recording_settings")
