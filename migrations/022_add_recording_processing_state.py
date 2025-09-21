"""
Migration: 022_add_recording_processing_state
Creates table recording_processing_state to persist per-recording post-processing step status.
"""

from sqlalchemy import text
from app.database import engine

SCRIPT_NAME = __name__.split('.')[-1] + '.py'

SQL_CREATE = """
CREATE TABLE IF NOT EXISTS recording_processing_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id INTEGER NOT NULL UNIQUE,
    stream_id INTEGER NOT NULL,
    streamer_id INTEGER NOT NULL,
    metadata_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    chapters_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    mp4_remux_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    mp4_validation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    thumbnail_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    cleanup_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    last_error TEXT NULL,
    task_ids_json TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_rps_recording_id ON recording_processing_state(recording_id);
CREATE INDEX IF NOT EXISTS ix_rps_stream_id ON recording_processing_state(stream_id);
CREATE INDEX IF NOT EXISTS ix_rps_updated_at ON recording_processing_state(updated_at);
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
