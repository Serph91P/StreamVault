"""
Migration: 022_add_recording_processing_state
Creates table recording_processing_state to persist per-recording post-processing step status.
"""

from sqlalchemy import text
from app.database import engine

SCRIPT_NAME = __name__.split('.')[-1] + '.py'

SQL_CREATE = """
CREATE TABLE IF NOT EXISTS recording_processing_state (
    id SERIAL PRIMARY KEY,
    recording_id INTEGER NOT NULL,
    stream_id INTEGER NOT NULL,
    streamer_id INTEGER NOT NULL,
    metadata_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    chapters_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    mp4_remux_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    mp4_validation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    thumbnail_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    cleanup_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    last_error TEXT,
    task_ids_json TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Align with model index naming; keep unique index on recording_id
CREATE UNIQUE INDEX IF NOT EXISTS ix_rps_recording_id ON recording_processing_state(recording_id);
CREATE INDEX IF NOT EXISTS ix_rps_stream_id ON recording_processing_state(stream_id);
CREATE INDEX IF NOT EXISTS ix_rps_updated_at ON recording_processing_state(updated_at);

-- Ensure updated_at is maintained at DB level
DROP TRIGGER IF EXISTS update_recording_processing_state_updated_at ON recording_processing_state;
CREATE TRIGGER update_recording_processing_state_updated_at
    BEFORE UPDATE ON recording_processing_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""

SQL_DROP = """
DROP TABLE IF EXISTS recording_processing_state;
"""


def upgrade():
    with engine.begin() as conn:
        conn.execute(text(SQL_CREATE))


def downgrade():
    with engine.begin() as conn:
        conn.execute(text(SQL_DROP))
