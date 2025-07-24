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
                password_hash VARCHAR(500) NOT NULL,
                email VARCHAR(254),
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created users table")
        
        # 2. Categories table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                box_art_url VARCHAR(500),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created categories table")
        
        # 3. Global settings table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS global_settings (
                id SERIAL PRIMARY KEY,
                twitch_client_id VARCHAR(100),
                twitch_client_secret VARCHAR(100),
                webhook_secret VARCHAR(255),
                max_concurrent_recordings INTEGER DEFAULT 3,
                base_output_path VARCHAR(500) DEFAULT '/recordings',
                recording_quality VARCHAR(50) DEFAULT 'best',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created global_settings table")
        
        # 4. Recording settings table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS recording_settings (
                id SERIAL PRIMARY KEY,
                max_concurrent_recordings INTEGER DEFAULT 3,
                default_quality VARCHAR(50) DEFAULT 'best',
                base_output_path VARCHAR(500) DEFAULT '/recordings',
                auto_record_enabled BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created recording_settings table")
        
        # 5. System config table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS system_config (
                id SERIAL PRIMARY KEY,
                key VARCHAR(100) UNIQUE NOT NULL,
                value TEXT,
                description TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """))
        logger.info("✅ Created system_config table")
        
        # 6. Push subscriptions table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                endpoint VARCHAR(500) NOT NULL,
                p256dh VARCHAR(500) NOT NULL,
                auth VARCHAR(500) NOT NULL,
                user_agent VARCHAR(500),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(endpoint, p256dh, auth)
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
