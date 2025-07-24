#!/usr/bin/env python
"""
Migration 001: Create base tables (no foreign keys)
Creates: users, categories, global_settings, recording_settings, system_config, push_subscriptions
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
    """Create base tables without foreign key dependencies"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Creating base tables...")
        
        # 1. Users table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created users table")
        
        # 2. Categories table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                twitch_id VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                box_art_url TEXT,
                first_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created categories table")
        
        # 3. Global settings table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS global_settings (
                id SERIAL PRIMARY KEY,
                notification_url TEXT,
                notifications_enabled BOOLEAN DEFAULT FALSE,
                notify_online_global BOOLEAN DEFAULT TRUE,
                notify_offline_global BOOLEAN DEFAULT TRUE,
                notify_update_global BOOLEAN DEFAULT TRUE,
                notify_favorite_category_global BOOLEAN DEFAULT TRUE,
                http_proxy VARCHAR(255),
                https_proxy VARCHAR(255)
            )
        """))
        logger.info("✅ Created global_settings table")
        
        # 4. Recording settings table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS recording_settings (
                id SERIAL PRIMARY KEY,
                enabled BOOLEAN DEFAULT TRUE,
                output_directory VARCHAR(500) DEFAULT '/recordings',
                filename_template VARCHAR(500),
                default_quality VARCHAR(50) DEFAULT 'best',
                use_chapters BOOLEAN DEFAULT TRUE,
                filename_preset VARCHAR(50) DEFAULT 'default',
                use_category_as_chapter_title BOOLEAN DEFAULT FALSE,
                max_streams_per_streamer INTEGER DEFAULT 0,
                cleanup_policy TEXT
            )
        """))
        logger.info("✅ Created recording_settings table")
        
        # 5. System config table (for VAPID keys etc)
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS system_config (
                id SERIAL PRIMARY KEY,
                key VARCHAR(255) UNIQUE NOT NULL,
                value TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created system_config table")
        
        # 6. Push subscriptions table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh_key TEXT NOT NULL,
                auth_key TEXT NOT NULL,
                user_agent TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created push_subscriptions table")
        
        session.commit()
        logger.info("🎉 Migration 001 completed successfully")
        
    except Exception as e:
        logger.error(f"Migration 001 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()

if __name__ == "__main__":
    run_migration()
