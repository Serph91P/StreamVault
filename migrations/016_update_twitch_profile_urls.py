#!/usr/bin/env python
"""
Migration 016: Update Twitch Profile URLs
Updates outdated numeric Twitch profile URLs to use current UUID-based format
and clears invalid cached profile images to force re-download
"""
import os
import sys
import logging
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DatabaseError, OperationalError

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Update Twitch profile URLs to force refresh from API"""
    session = None
    try:
        # Validate DATABASE_URL
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")
        
        # Create database connection
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("Starting migration 016: Update Twitch Profile URLs")
        
        # Find streamers with old numeric Twitch profile URLs
        old_url_pattern = r'https://static-cdn\.jtvnw\.net/jtv_user_pictures/\d+-profile_image'
        
        # Query streamers with old format URLs
        result = session.execute(text("""
            SELECT id, username, twitch_id, profile_image_url, original_profile_image_url 
            FROM streamers 
            WHERE profile_image_url ~ :pattern 
               OR original_profile_image_url ~ :pattern
        """), {"pattern": old_url_pattern})
        
        streamers_to_update = result.fetchall()
        logger.info(f"Found {len(streamers_to_update)} streamers with old profile URLs")
        
        updated_count = 0
        
        for streamer in streamers_to_update:
            streamer_id, username, twitch_id, profile_url, original_url = streamer
            
            logger.info(f"Updating streamer {username} (ID: {streamer_id}, Twitch ID: {twitch_id})")
            
            # Generate new profile URL using Twitch ID
            new_profile_url = f"https://static-cdn.jtvnw.net/jtv_user_pictures/{twitch_id}-profile_image-300x300.png"
            
            # Clear the cached profile_image_url to force re-download
            # Set it to the new URL so the image service will download it
            session.execute(text("""
                UPDATE streamers 
                SET profile_image_url = :new_url,
                    original_profile_image_url = :new_url
                WHERE id = :streamer_id
            """), {
                "new_url": new_profile_url,
                "streamer_id": streamer_id
            })
            
            logger.info(f"  Updated {username}: {new_profile_url}")
            updated_count += 1
        
        # Also clear any local cached paths that might be invalid
        # This forces the image service to re-download from the new URLs
        result = session.execute(text("""
            SELECT id, username, profile_image_url 
            FROM streamers 
            WHERE profile_image_url LIKE '/data/images/profiles/profile_avatar_%'
        """))
        
        cached_streamers = result.fetchall()
        logger.info(f"Found {len(cached_streamers)} streamers with local cached images")
        
        for streamer in cached_streamers:
            streamer_id, username, cached_path = streamer
            
            # Check if the cached path uses old numeric ID format
            if re.search(r'profile_avatar_\d+\.jpg', cached_path):
                # Get the current original_profile_image_url to restore
                result = session.execute(text("""
                    SELECT original_profile_image_url, twitch_id 
                    FROM streamers 
                    WHERE id = :streamer_id
                """), {"streamer_id": streamer_id})
                
                streamer_data = result.fetchone()
                if streamer_data:
                    original_url, twitch_id = streamer_data
                    
                    # If original URL is also old format, update it
                    if not original_url or re.search(r'jtv_user_pictures/\d+-profile_image', original_url):
                        new_original_url = f"https://static-cdn.jtvnw.net/jtv_user_pictures/{twitch_id}-profile_image-300x300.png"
                    else:
                        new_original_url = original_url
                    
                    # Clear cached path and set to original URL for re-download
                    session.execute(text("""
                        UPDATE streamers 
                        SET profile_image_url = :original_url,
                            original_profile_image_url = :original_url
                        WHERE id = :streamer_id
                    """), {
                        "original_url": new_original_url,
                        "streamer_id": streamer_id
                    })
                    
                    logger.info(f"  Cleared cached image for {username}, will re-download from: {new_original_url}")
                    updated_count += 1
        
        # Commit the changes
        session.commit()
        
        logger.info(f"Migration completed successfully!")
        logger.info(f"Updated {updated_count} streamers")
        logger.info("Note: Profile images will be automatically re-downloaded by the image sync service")
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session:
            session.close()

def rollback_migration():
    """Rollback migration 016 - Note: This cannot restore original URLs if they were invalid"""
    logger.warning("Rollback for migration 016 is not recommended as it cannot restore the original invalid URLs")
    logger.warning("The updated URLs are correct and should remain in place")
    return True

if __name__ == "__main__":
    try:
        run_migration()
        logger.info("Migration 016 completed successfully")
    except Exception as e:
        logger.error(f"Migration 016 failed: {e}")
        sys.exit(1)
