"""Add cleanup policy columns

Migration to add cleanup_policy columns to recording_settings and streamer_recording_settings tables.

Revision ID: add_cleanup_policy
Created: 2025-05-22
"""

from sqlalchemy import Column, String, Integer
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_cleanup_policy'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add cleanup_policy column to recording_settings table
    op.add_column('recording_settings', Column('cleanup_policy', String, nullable=True))
    
    # Add cleanup_policy column to streamer_recording_settings table
    op.add_column('streamer_recording_settings', Column('cleanup_policy', String, nullable=True))


def downgrade():
    # Remove cleanup_policy column from streamer_recording_settings table
    op.drop_column('streamer_recording_settings', 'cleanup_policy')
    
    # Remove cleanup_policy column from recording_settings table  
    op.drop_column('recording_settings', 'cleanup_policy')
