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
                notify_on_live BOOLEAN DEFAULT TRUE,
                notify_on_title_change BOOLEAN DEFAULT FALSE,
                notify_on_category_change BOOLEAN DEFAULT FALSE,
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
                category_name VARCHAR(100) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, category_name)
            )
        """))
        logger.info("✅ Created favorite_categories table")
        
        # 5. Streamer recording settings (depends on streamers)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS streamer_recording_settings (
                id SERIAL PRIMARY KEY,
                streamer_id INTEGER NOT NULL REFERENCES streamers(id) ON DELETE CASCADE,
                auto_record BOOLEAN DEFAULT FALSE,
                quality VARCHAR(50) DEFAULT 'best',
                output_path VARCHAR(500),
                enabled BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(streamer_id)
            )
        """))
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
