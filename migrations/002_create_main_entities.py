#!/usr/bin/env python
"""
Migration 002: Create main entities
Creates: streamers, streams, sessions
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
    """Create main entity tables with basic foreign keys"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Creating main entity tables...")

        # 1. Streamers table - match the Models exactly
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS streamers (
                id SERIAL PRIMARY KEY,
                twitch_id VARCHAR(255) UNIQUE NOT NULL,
                username VARCHAR(255) NOT NULL,
                is_live BOOLEAN DEFAULT FALSE,
                title VARCHAR(255),
                category_name VARCHAR(255),
                language VARCHAR(255),
                last_updated TIMESTAMP WITH TIME ZONE,
                profile_image_url VARCHAR(255),
                original_profile_image_url VARCHAR(255),
                is_favorite BOOLEAN DEFAULT FALSE,
                auto_record BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        logger.info("✅ Created streamers table")
        
        # 2. Streams table - match the Models exactly
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS streams (
                id SERIAL PRIMARY KEY,
                streamer_id INTEGER NOT NULL REFERENCES streamers(id) ON DELETE CASCADE,
                title VARCHAR(255),
                category_name VARCHAR(255),
                language VARCHAR(255),
                started_at TIMESTAMP WITH TIME ZONE NOT NULL,
                ended_at TIMESTAMP WITH TIME ZONE,
                twitch_stream_id VARCHAR(255),
                recording_path VARCHAR(1024),
                episode_number INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        logger.info("✅ Created streams table")
        
        # 3. Sessions table - with NOT NULL constraints for security and expires_at
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(255) NOT NULL UNIQUE,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours'),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created sessions table")
        
        # Create indexes for sessions
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
        """))
        logger.info("✅ Created sessions indexes")
        
        session.commit()
        logger.info("🎉 Migration 002 completed successfully")
        
    except Exception as e:
        logger.error(f"Migration 002 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()

if __name__ == "__main__":
    run_migration()
