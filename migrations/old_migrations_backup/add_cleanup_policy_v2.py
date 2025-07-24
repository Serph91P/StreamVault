"""Add cleanup policy columns v2

Migration to add cleanup_policy columns to recording_settings and streamer_recording_settings tables.

Revision ID: add_cleanup_policy_v2
Created: 2025-05-25
"""

from sqlalchemy import Column, Text
from alembic import op


# revision identifiers, used by Alembic.
revision = 'add_cleanup_policy_v2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add cleanup_policy columns"""
    print("Running cleanup policy migration v2...")
    
    # Add cleanup_policy column to recording_settings table
    op.add_column('recording_settings', 
                 Column('cleanup_policy', Text, nullable=True))
    
    # Add cleanup_policy column to streamer_recording_settings table  
    op.add_column('streamer_recording_settings', 
                 Column('cleanup_policy', Text, nullable=True))
                 
    print("Successfully added cleanup_policy columns")


def downgrade():
    """Remove cleanup_policy columns"""
    print("Removing cleanup policy columns...")
    
    # Remove cleanup_policy column from streamer_recording_settings table
    op.drop_column('streamer_recording_settings', 'cleanup_policy')
    
    # Remove cleanup_policy column from recording_settings table
    op.drop_column('recording_settings', 'cleanup_policy')
    
    print("Successfully removed cleanup_policy columns")
