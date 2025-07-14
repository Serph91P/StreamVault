"""
Add active recordings state table for persistence

This migration adds a table to track active recordings
that survive application restarts.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_active_recordings_state'
down_revision = None  # Set to the previous migration
branch_labels = None
depends_on = None

def upgrade():
    # Create active_recordings_state table
    op.create_table(
        'active_recordings_state',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('stream_id', sa.Integer, sa.ForeignKey('streams.id'), nullable=False, unique=True),
        sa.Column('recording_id', sa.Integer, sa.ForeignKey('recordings.id'), nullable=False),
        sa.Column('process_id', sa.Integer, nullable=False),  # OS process ID
        sa.Column('process_identifier', sa.String(100), nullable=False),  # Internal process identifier
        sa.Column('streamer_name', sa.String(100), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ts_output_path', sa.String(500), nullable=False),
        sa.Column('force_mode', sa.Boolean, default=False),
        sa.Column('quality', sa.String(50), default='best'),
        sa.Column('status', sa.String(50), default='active'),  # active, stopping, error
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=False),
        sa.Column('config_json', sa.Text, nullable=True),  # Serialized config
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'))
    )
    
    # Create indices for better performance
    op.create_index('ix_active_recordings_stream_id', 'active_recordings_state', ['stream_id'])
    op.create_index('ix_active_recordings_status', 'active_recordings_state', ['status'])
    op.create_index('ix_active_recordings_heartbeat', 'active_recordings_state', ['last_heartbeat'])

def downgrade():
    op.drop_table('active_recordings_state')
