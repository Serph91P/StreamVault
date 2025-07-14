"""
Add database indexes for performance optimization
Created: 2025-07-14

This migration adds indexes to frequently queried columns and composite indexes
for common query patterns to improve database performance.
"""
import logging
from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger("streamvault")

def upgrade():
    """Add database indexes for performance optimization"""
    db = SessionLocal()
    
    try:
        logger.info("Starting database index creation...")
        
        # Single column indexes
        indexes = [
            # Recordings table
            "CREATE INDEX IF NOT EXISTS idx_recordings_stream_id ON recordings(stream_id)",
            "CREATE INDEX IF NOT EXISTS idx_recordings_start_time ON recordings(start_time)",
            "CREATE INDEX IF NOT EXISTS idx_recordings_status ON recordings(status)",
            
            # Streamers table  
            "CREATE INDEX IF NOT EXISTS idx_streamers_twitch_id ON streamers(twitch_id)",
            "CREATE INDEX IF NOT EXISTS idx_streamers_username ON streamers(username)",
            "CREATE INDEX IF NOT EXISTS idx_streamers_is_live ON streamers(is_live)",
            "CREATE INDEX IF NOT EXISTS idx_streamers_category_name ON streamers(category_name)",
            
            # Streams table
            "CREATE INDEX IF NOT EXISTS idx_streams_streamer_id ON streams(streamer_id)",
            "CREATE INDEX IF NOT EXISTS idx_streams_category_name ON streams(category_name)",
            "CREATE INDEX IF NOT EXISTS idx_streams_started_at ON streams(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_streams_ended_at ON streams(ended_at)",
            "CREATE INDEX IF NOT EXISTS idx_streams_twitch_stream_id ON streams(twitch_stream_id)",
            
            # Stream Events table
            "CREATE INDEX IF NOT EXISTS idx_stream_events_stream_id ON stream_events(stream_id)",
            "CREATE INDEX IF NOT EXISTS idx_stream_events_event_type ON stream_events(event_type)",
            "CREATE INDEX IF NOT EXISTS idx_stream_events_timestamp ON stream_events(timestamp)",
            
            # Notification Settings table
            "CREATE INDEX IF NOT EXISTS idx_notification_settings_streamer_id ON notification_settings(streamer_id)",
            
            # Streamer Recording Settings table
            "CREATE INDEX IF NOT EXISTS idx_streamer_recording_settings_streamer_id ON streamer_recording_settings(streamer_id)",
            
            # Stream Metadata table
            "CREATE INDEX IF NOT EXISTS idx_stream_metadata_stream_id ON stream_metadata(stream_id)",
        ]
        
        # Composite indexes for common query patterns
        composite_indexes = [
            # Recordings
            "CREATE INDEX IF NOT EXISTS idx_recordings_stream_status ON recordings(stream_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_recordings_status_time ON recordings(status, start_time)",
            
            # Streams - for finding active streams (ended_at IS NULL)
            "CREATE INDEX IF NOT EXISTS idx_streams_streamer_active ON streams(streamer_id, ended_at)",
            # Streams - for recent streams by streamer (ORDER BY started_at DESC)
            "CREATE INDEX IF NOT EXISTS idx_streams_streamer_recent ON streams(streamer_id, started_at)",
            # Streams - for recent streams by category
            "CREATE INDEX IF NOT EXISTS idx_streams_category_recent ON streams(category_name, started_at)",
            # Streams - for time-based queries
            "CREATE INDEX IF NOT EXISTS idx_streams_time_range ON streams(started_at, ended_at)",
            
            # Stream Events
            "CREATE INDEX IF NOT EXISTS idx_stream_events_stream_type ON stream_events(stream_id, event_type)",
            "CREATE INDEX IF NOT EXISTS idx_stream_events_stream_time ON stream_events(stream_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_stream_events_type_time ON stream_events(event_type, timestamp)",
        ]
        
        # Execute single column indexes
        for idx_sql in indexes:
            try:
                logger.info(f"Creating index: {idx_sql}")
                db.execute(text(idx_sql))
                db.commit()
            except Exception as e:
                logger.warning(f"Index creation failed (may already exist): {idx_sql} - {e}")
                db.rollback()
        
        # Execute composite indexes
        for idx_sql in composite_indexes:
            try:
                logger.info(f"Creating composite index: {idx_sql}")
                db.execute(text(idx_sql))
                db.commit()
            except Exception as e:
                logger.warning(f"Composite index creation failed (may already exist): {idx_sql} - {e}")
                db.rollback()
        
        logger.info("Database index creation completed successfully")
        
    except Exception as e:
        logger.error(f"Error during index creation: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

def downgrade():
    """Remove database indexes"""
    db = SessionLocal()
    
    try:
        logger.info("Starting database index removal...")
        
        # List of all indexes to remove (excluding primary keys and unique constraints)
        indexes_to_drop = [
            # Single column indexes
            "DROP INDEX IF EXISTS idx_recordings_stream_id",
            "DROP INDEX IF EXISTS idx_recordings_start_time", 
            "DROP INDEX IF EXISTS idx_recordings_status",
            "DROP INDEX IF EXISTS idx_streamers_twitch_id",
            "DROP INDEX IF EXISTS idx_streamers_username",
            "DROP INDEX IF EXISTS idx_streamers_is_live",
            "DROP INDEX IF EXISTS idx_streamers_category_name",
            "DROP INDEX IF EXISTS idx_streams_streamer_id",
            "DROP INDEX IF EXISTS idx_streams_category_name",
            "DROP INDEX IF EXISTS idx_streams_started_at",
            "DROP INDEX IF EXISTS idx_streams_ended_at",
            "DROP INDEX IF EXISTS idx_streams_twitch_stream_id",
            "DROP INDEX IF EXISTS idx_stream_events_stream_id",
            "DROP INDEX IF EXISTS idx_stream_events_event_type",
            "DROP INDEX IF EXISTS idx_stream_events_timestamp",
            "DROP INDEX IF EXISTS idx_notification_settings_streamer_id",
            "DROP INDEX IF EXISTS idx_streamer_recording_settings_streamer_id",
            "DROP INDEX IF EXISTS idx_stream_metadata_stream_id",
            
            # Composite indexes
            "DROP INDEX IF EXISTS idx_recordings_stream_status",
            "DROP INDEX IF EXISTS idx_recordings_status_time",
            "DROP INDEX IF EXISTS idx_streams_streamer_active",
            "DROP INDEX IF EXISTS idx_streams_streamer_recent",
            "DROP INDEX IF EXISTS idx_streams_category_recent",
            "DROP INDEX IF EXISTS idx_streams_time_range",
            "DROP INDEX IF EXISTS idx_stream_events_stream_type",
            "DROP INDEX IF EXISTS idx_stream_events_stream_time",
            "DROP INDEX IF EXISTS idx_stream_events_type_time",
        ]
        
        for drop_sql in indexes_to_drop:
            try:
                logger.info(f"Dropping index: {drop_sql}")
                db.execute(text(drop_sql))
                db.commit()
            except Exception as e:
                logger.warning(f"Index drop failed (may not exist): {drop_sql} - {e}")
                db.rollback()
        
        logger.info("Database index removal completed successfully")
        
    except Exception as e:
        logger.error(f"Error during index removal: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    upgrade()
