"""
Add active_recordings_state table for persistent recording state

This migration creates the active_recordings_state table for persistent recording state.
"""

from app.database import engine
from sqlalchemy import text
import logging

logger = logging.getLogger("streamvault")

def upgrade():
    """Create active_recordings_state table for persistent recording state"""
    with engine.connect() as connection:
        logger.info("🔄 Creating active_recordings_state table...")
        
        # Create table with IF NOT EXISTS
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS active_recordings_state (
                id SERIAL PRIMARY KEY,
                stream_id INTEGER NOT NULL,
                recording_id INTEGER NOT NULL,
                process_id INTEGER NOT NULL,
                process_identifier VARCHAR(100) NOT NULL,
                streamer_name VARCHAR(100) NOT NULL,
                started_at TIMESTAMP WITH TIME ZONE NOT NULL,
                ts_output_path VARCHAR(500) NOT NULL,
                force_mode BOOLEAN DEFAULT FALSE,
                quality VARCHAR(50) DEFAULT 'best',
                status VARCHAR(50) DEFAULT 'active',
                last_heartbeat TIMESTAMP WITH TIME ZONE NOT NULL,
                config_json TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create unique constraint on stream_id (with proper error handling)
        try:
            connection.execute(text("""
                ALTER TABLE active_recordings_state 
                ADD CONSTRAINT active_recordings_state_stream_id_key UNIQUE (stream_id)
            """))
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                logger.info("Constraint active_recordings_state_stream_id_key already exists")
            else:
                raise
        
        # Create foreign key constraints if tables exist
        try:
            # Check if streams table exists
            result = connection.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = 'streams'"))
            if result.fetchone():
                connection.execute(text("""
                    ALTER TABLE active_recordings_state 
                    ADD CONSTRAINT fk_active_recordings_stream 
                    FOREIGN KEY (stream_id) REFERENCES streams(id) ON DELETE CASCADE
                """))
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                logger.info("Foreign key constraint fk_active_recordings_stream already exists")
            else:
                logger.debug(f"Could not create foreign key constraint fk_active_recordings_stream: {e}")
        
        try:
            # Check if recordings table exists
            result = connection.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = 'recordings'"))
            if result.fetchone():
                connection.execute(text("""
                    ALTER TABLE active_recordings_state 
                    ADD CONSTRAINT fk_active_recordings_recording 
                    FOREIGN KEY (recording_id) REFERENCES recordings(id) ON DELETE CASCADE
                """))
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                logger.info("Foreign key constraint fk_active_recordings_recording already exists")
            else:
                logger.debug(f"Could not create foreign key constraint fk_active_recordings_recording: {e}")
        
        # Create indices for better performance
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_active_recordings_stream_id 
            ON active_recordings_state (stream_id)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_active_recordings_status 
            ON active_recordings_state (status)
        """))
        
        connection.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_active_recordings_heartbeat 
            ON active_recordings_state (last_heartbeat)
        """))
        
        connection.commit()
        logger.info("✅ Active recordings state table and indices created successfully")
        logger.info("🎯 Features enabled:")
        logger.info("   • Persistent recording state across restarts")
        logger.info("   • Automatic recovery of interrupted recordings")
        logger.info("   • Heartbeat monitoring for stale process detection")
        logger.info("   • Production-ready container deployment support")

def downgrade():
    """Remove active_recordings_state table"""
    with engine.connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS active_recordings_state"))
        connection.commit()
        logger.info("Removed active_recordings_state table")

if __name__ == "__main__":
    upgrade()
