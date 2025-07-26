#!/usr/bin/env python
"""
Migration 004: Add database indexes for performance
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add indexes for better query performance"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Adding database indexes...")
        
        # Streamers indexes - mit korrekten Spaltennamen aus den Models
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streamers_twitch_id ON streamers (twitch_id)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streamers_username ON streamers (username)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streamers_is_live ON streamers (is_live)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streamers_category_name ON streamers (category_name)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streamers_is_favorite ON streamers (is_favorite)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streamers_auto_record ON streamers (auto_record)"))
        logger.info("✅ Added streamers indexes")
        
        # Streams indexes - mit korrekten Spaltennamen
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_streamer_id ON streams (streamer_id)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_started_at ON streams (started_at)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_ended_at ON streams (ended_at)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_category_name ON streams (category_name)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_twitch_stream_id ON streams (twitch_stream_id)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_title ON streams (title)"))
        # Composite indexes für bessere Performance
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_streamer_active ON streams (streamer_id, ended_at)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_streamer_recent ON streams (streamer_id, started_at)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_category_recent ON streams (category_name, started_at)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_streams_time_range ON streams (started_at, ended_at)"))
        logger.info("✅ Added streams indexes")
        
        # Recordings indexes
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_recordings_stream_id ON recordings (stream_id)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_recordings_start_time ON recordings (start_time)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_recordings_status ON recordings (status)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_recordings_stream_status ON recordings (stream_id, status)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_recordings_status_time ON recordings (status, start_time)"))
        logger.info("✅ Added recordings indexes")
        
        # Stream events indexes
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stream_events_stream_id ON stream_events (stream_id)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stream_events_event_type ON stream_events (event_type)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stream_events_timestamp ON stream_events (timestamp)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stream_events_stream_type ON stream_events (stream_id, event_type)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stream_events_stream_time ON stream_events (stream_id, timestamp)"))
        session.execute(text("CREATE INDEX IF NOT EXISTS idx_stream_events_type_time ON stream_events (event_type, timestamp)"))
        logger.info("✅ Added stream_events indexes")
        
        # Commit all indexes in a single transaction for optimal performance
        session.commit()
        logger.info("🎉 Migration 004 completed successfully")
        
    except Exception as e:
        logger.error(f"Migration 004 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()

if __name__ == "__main__":
    run_migration()
