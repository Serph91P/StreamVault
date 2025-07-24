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
        
        # 1. Streamers table (no foreign keys)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS streamers (
                id SERIAL PRIMARY KEY,
                twitch_id VARCHAR(100) UNIQUE NOT NULL,
                username VARCHAR(100) NOT NULL,
                is_live BOOLEAN DEFAULT FALSE,
                title VARCHAR(500),
                category_name VARCHAR(100),
                language VARCHAR(10),
                last_updated TIMESTAMP WITH TIME ZONE,
                profile_image_url VARCHAR(500),
                original_profile_image_url VARCHAR(500),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created streamers table")
        
        # 2. Streams table (depends on streamers)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS streams (
                id SERIAL PRIMARY KEY,
                streamer_id INTEGER NOT NULL REFERENCES streamers(id) ON DELETE CASCADE,
                title VARCHAR(500),
                category_name VARCHAR(100),
                language VARCHAR(10),
                started_at TIMESTAMP WITH TIME ZONE,
                ended_at TIMESTAMP WITH TIME ZONE,
                twitch_stream_id VARCHAR(100),
                recording_path VARCHAR(1024),
                episode_number INTEGER
            )
        """))
        logger.info("✅ Created streams table")
        
        # 3. Sessions table (depends on users)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_token VARCHAR(500) UNIQUE NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created sessions table")
        
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
