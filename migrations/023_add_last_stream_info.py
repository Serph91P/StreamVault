#!/usr/bin/env python
"""
Migration 023: Add last stream info columns to streamers table

Adds fields to store information about the last stream when a streamer goes offline:
- last_stream_title: Title of the last stream
- last_stream_category_name: Category/game of the last stream
- last_stream_viewer_count: Peak viewer count of the last stream
- last_stream_ended_at: When the last stream ended

This allows the UI to display "Last streamed: X hours ago - Title - Category"
when a streamer is offline, providing better context to users.

Backfills data from the most recent ended stream for each streamer.
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add last stream info columns to streamers table and backfill from most recent streams"""
    session = None
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Adding last stream info columns to streamers table...")
        
        # Check if columns already exist
        result = session.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'streamers' 
            AND column_name IN ('last_stream_title', 'last_stream_category_name', 
                                'last_stream_viewer_count', 'last_stream_ended_at')
        """))
        
        existing_columns = [row[0] for row in result.fetchall()]
        
        if len(existing_columns) == 4:
            logger.info("✅ All last stream info columns already exist in streamers table")
            return
        
        # Add the columns (nullable since we'll backfill)
        if 'last_stream_title' not in existing_columns:
            session.execute(text("ALTER TABLE streamers ADD COLUMN last_stream_title VARCHAR"))
            logger.info("✅ Added last_stream_title column")
        
        if 'last_stream_category_name' not in existing_columns:
            session.execute(text("ALTER TABLE streamers ADD COLUMN last_stream_category_name VARCHAR"))
            logger.info("✅ Added last_stream_category_name column")
        
        if 'last_stream_viewer_count' not in existing_columns:
            session.execute(text("ALTER TABLE streamers ADD COLUMN last_stream_viewer_count INTEGER"))
            logger.info("✅ Added last_stream_viewer_count column")
        
        if 'last_stream_ended_at' not in existing_columns:
            session.execute(text("ALTER TABLE streamers ADD COLUMN last_stream_ended_at TIMESTAMP WITH TIME ZONE"))
            logger.info("✅ Added last_stream_ended_at column")
        
        session.commit()
        
        # Backfill from most recent ended streams
        logger.info("🔄 Backfilling last stream info from most recent streams...")
        
        # Get all streamers with at least one ended stream
        result = session.execute(text("""
            SELECT DISTINCT s.id, s.username
            FROM streamers s
            INNER JOIN streams st ON st.streamer_id = s.id
            WHERE st.ended_at IS NOT NULL
        """))
        
        streamers_to_update = result.fetchall()
        logger.info(f"Found {len(streamers_to_update)} streamers with ended streams")
        
        updated_count = 0
        for streamer_id, username in streamers_to_update:
            # Get the most recent ended stream for this streamer
            result = session.execute(text("""
                SELECT title, category_name, ended_at
                FROM streams
                WHERE streamer_id = :streamer_id
                AND ended_at IS NOT NULL
                ORDER BY ended_at DESC
                LIMIT 1
            """), {"streamer_id": streamer_id})
            
            last_stream = result.fetchone()
            
            if last_stream:
                title, category_name, ended_at = last_stream
                
                # Update streamer with last stream info
                session.execute(text("""
                    UPDATE streamers
                    SET last_stream_title = :title,
                        last_stream_category_name = :category_name,
                        last_stream_ended_at = :ended_at
                    WHERE id = :streamer_id
                """), {
                    "title": title,
                    "category_name": category_name,
                    "ended_at": ended_at,
                    "streamer_id": streamer_id
                })
                
                updated_count += 1
                
                if updated_count % 10 == 0:
                    logger.info(f"Backfilled {updated_count}/{len(streamers_to_update)} streamers...")
        
        session.commit()
        logger.info(f"✅ Backfilled last stream info for {updated_count} streamers")
        
        logger.info("🎉 Migration 023 completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration 023 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()

if __name__ == "__main__":
    run_migration()
