#!/usr/bin/env python3
"""
Test script to manually trigger stream notifications for debugging
"""
import os
import sys
import asyncio
import logging

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import SessionLocal
from app.models import Streamer
from app.services.notification_service import NotificationService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_stream_notification():
    """Test sending a stream notification"""
    try:
        notification_service = NotificationService()
        
        # Find a streamer to test with
        with SessionLocal() as db:
            streamer = db.query(Streamer).first()
            if not streamer:
                logger.error("No streamers found in database")
                return
            
            logger.info(f"Testing notification for streamer: {streamer.username} (ID: {streamer.id})")
            
            # Test online notification
            await notification_service.send_stream_notification(
                streamer_name=streamer.username,
                event_type="online", 
                details={
                    "streamer_id": streamer.id,
                    "stream_id": 999,  # Test stream ID
                    "title": "TEST: Manual notification test stream",
                    "category_name": "Test Category",
                    "language": "en",
                    "url": f"https://twitch.tv/{streamer.username}",
                    "profile_image_url": streamer.profile_image_url,
                    "started_at": "2025-06-30T12:00:00Z",
                    "is_live": True
                }
            )
            
            logger.info("Test notification sent successfully")
            
    except Exception as e:
        logger.error(f"Error testing notification: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("🧪 TEST: Sending test stream notification...")
    asyncio.run(test_stream_notification())
    logger.info("🧪 TEST: Complete!")
