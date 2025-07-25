#!/usr/bin/env python
"""
Migration 003: Create dependent tables
Creates: recordings, stream_events, notification_settings, favorite_categories, 
         streamer_recording_settings, stream_metadata, active_recording_state
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
    """Create tables that depend on main entities"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Creating dependent tables...")
        
        # 1. Recordings table (depends on streams)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS recordings (
                id SERIAL PRIMARY KEY,
                stream_id INTEGER NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
                start_time TIMESTAMP WITH TIME ZONE NOT NULL,
                end_time TIMESTAMP WITH TIME ZONE,
                status VARCHAR(50) NOT NULL,
                duration INTEGER,
                path VARCHAR(1024),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created recordings table")
        
        # 2. Stream events table (depends on streams)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS stream_events (
                id SERIAL PRIMARY KEY,
                stream_id INTEGER REFERENCES streams(id) ON DELETE CASCADE,
                event_type VARCHAR(100) NOT NULL,
                title VARCHAR(500),
                category_name VARCHAR(100),
                language VARCHAR(10),
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created stream_events table")
        
        # 3. Notification settings (depends on streamers)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS notification_settings (
                id SERIAL PRIMARY KEY,
                streamer_id INTEGER NOT NULL REFERENCES streamers(id) ON DELETE CASCADE,
                notify_online BOOLEAN DEFAULT TRUE,
                notify_offline BOOLEAN DEFAULT TRUE,
                notify_update BOOLEAN DEFAULT TRUE,
                notify_favorite_category BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(streamer_id)
            )
        """))
        logger.info("✅ Created notification_settings table")
        
        # 4. Favorite categories (depends on users and categories)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS favorite_categories (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, category_id)
            )
        """))
        logger.info("✅ Created favorite_categories table")
        
        # 5. Streamer recording settings (depends on streamers)
        # First, check if table exists and handle auto_record field migration
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS streamer_recording_settings (
                id SERIAL PRIMARY KEY,
                streamer_id INTEGER NOT NULL REFERENCES streamers(id) ON DELETE CASCADE,
                enabled BOOLEAN DEFAULT TRUE,
                quality VARCHAR(50) DEFAULT 'best',
                custom_filename VARCHAR(1024),
                max_streams INTEGER,
                cleanup_policy TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(streamer_id)
            )
        """))
        
        # Handle legacy auto_record field migration if it exists
        try:
            # Check if auto_record column exists
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'streamer_recording_settings' 
                AND column_name = 'auto_record'
            """))
            
            if result.fetchone():
                logger.info("🔄 Migrating legacy auto_record field...")
                # Migrate auto_record values to enabled field
                session.execute(text("""
                    UPDATE streamer_recording_settings 
                    SET enabled = auto_record 
                    WHERE auto_record IS NOT NULL
                """))
                
                # Remove auto_record column after migration
                session.execute(text("""
                    ALTER TABLE streamer_recording_settings 
                    DROP COLUMN IF EXISTS auto_record
                """))
                logger.info("✅ Migrated auto_record to enabled field")
            
            # Same for output_path - remove if exists
            result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'streamer_recording_settings' 
                AND column_name = 'output_path'
            """))
            
            if result.fetchone():
                logger.info("🔄 Removing legacy output_path field...")
                session.execute(text("""
                    ALTER TABLE streamer_recording_settings 
                    DROP COLUMN IF EXISTS output_path
                """))
                logger.info("✅ Removed legacy output_path field")
                
        except Exception as legacy_error:
            logger.warning(f"Non-critical legacy field migration warning: {legacy_error}")
            # Continue with migration even if legacy field handling fails
        
        logger.info("✅ Created streamer_recording_settings table")
        
        # 6. Stream metadata (depends on streams)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS stream_metadata (
                id SERIAL PRIMARY KEY,
                stream_id INTEGER NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
                thumbnail_url VARCHAR(500),
                viewer_count INTEGER,
                max_viewer_count INTEGER,
                tags TEXT,
                mature BOOLEAN DEFAULT FALSE,
                original_language VARCHAR(10),
                original_title VARCHAR(500),
                original_category VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stream_id)
            )
        """))
        logger.info("✅ Created stream_metadata table")
        
        # 7. Active recording state (depends on streams and recordings)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS active_recordings_state (
                id SERIAL PRIMARY KEY,
                stream_id INTEGER NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
                recording_id INTEGER NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
                process_id INTEGER NOT NULL,
                process_identifier VARCHAR(100) NOT NULL,
                streamer_name VARCHAR(100) NOT NULL,
                started_at TIMESTAMP WITH TIME ZONE NOT NULL,
                ts_output_path VARCHAR(500) NOT NULL,
                force_mode BOOLEAN DEFAULT FALSE,
                quality VARCHAR(50) DEFAULT 'best',
                status VARCHAR(50) DEFAULT 'recording',
                UNIQUE(stream_id)
            )
        """))
        logger.info("✅ Created active_recordings_state table")
        
        session.commit()
        logger.info("🎉 Migration 003 completed successfully")
        
    except Exception as e:
        logger.error(f"Migration 003 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()

if __name__ == "__main__":
    run_migration()
