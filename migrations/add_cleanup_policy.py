"""Add cleanup_policy columns to recording tables

Revision ID: add_cleanup_policy
Revises: 
Create Date: 2025-05-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, String, Text


# revision identifiers, used by Alembic.
revision = 'add_cleanup_policy'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add cleanup_policy columns"""
    try:
        # Add cleanup_policy column to recording_settings table
        op.add_column('recording_settings', 
                     sa.Column('cleanup_policy', sa.Text, nullable=True))
        
        # Add cleanup_policy column to streamer_recording_settings table  
        op.add_column('streamer_recording_settings', 
                     sa.Column('cleanup_policy', sa.Text, nullable=True))
                     
    except Exception as e:
        print(f"Error in upgrade: {e}")
        # Continue execution even if columns already exist
        pass


def downgrade():
    """Remove cleanup_policy columns"""
    try:
        # Remove cleanup_policy column from streamer_recording_settings table
        op.drop_column('streamer_recording_settings', 'cleanup_policy')
        
        # Remove cleanup_policy column from recording_settings table
        op.drop_column('recording_settings', 'cleanup_policy')
        
    except Exception as e:
        print(f"Error in downgrade: {e}")
        # Continue execution even if columns don't exist
        pass
