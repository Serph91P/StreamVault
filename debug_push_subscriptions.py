#!/usr/bin/env python3
"""
Debug script to check push subscriptions and notification settings
"""
import os
import sys
import logging
from sqlalchemy import text

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import SessionLocal
from app.models import PushSubscription, NotificationSettings, Streamer, GlobalSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_push_subscriptions():
    """Check push subscriptions in the database"""
    try:
        with SessionLocal() as db:
            # Check push subscriptions
            subscriptions = db.query(PushSubscription).all()
            logger.info(f"Total push subscriptions: {len(subscriptions)}")
            
            active_subscriptions = db.query(PushSubscription).filter(
                PushSubscription.is_active == True
            ).all()
            logger.info(f"Active push subscriptions: {len(active_subscriptions)}")
            
            for sub in active_subscriptions:
                logger.info(f"  - ID: {sub.id}, Endpoint: {sub.endpoint[:50]}..., Created: {sub.created_at}")
            
            # Check global settings
            global_settings = db.query(GlobalSettings).first()
            if global_settings:
                logger.info(f"Global notifications enabled: {global_settings.notifications_enabled}")
                logger.info(f"Notification URL configured: {bool(global_settings.notification_url)}")
            else:
                logger.warning("No global settings found")
            
            # Check streamers and their notification settings
            streamers = db.query(Streamer).all()
            logger.info(f"Total streamers: {len(streamers)}")
            
            for streamer in streamers:
                notification_settings = db.query(NotificationSettings).filter(
                    NotificationSettings.streamer_id == streamer.id
                ).first()
                
                if notification_settings:
                    logger.info(f"Streamer {streamer.username} (ID: {streamer.id}):")
                    logger.info(f"  - notify_online: {notification_settings.notify_online}")
                    logger.info(f"  - notify_offline: {notification_settings.notify_offline}")
                    logger.info(f"  - notify_update: {notification_settings.notify_update}")
                else:
                    logger.info(f"Streamer {streamer.username} (ID: {streamer.id}): No notification settings")
                    
    except Exception as e:
        logger.error(f"Error checking database: {e}", exc_info=True)

def check_vapid_configuration():
    """Check VAPID configuration"""
    try:
        from app.config.settings import settings
        
        vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
        vapid_public_key = getattr(settings, 'VAPID_PUBLIC_KEY', None)
        
        logger.info(f"VAPID Private Key configured: {bool(vapid_private_key)}")
        logger.info(f"VAPID Public Key configured: {bool(vapid_public_key)}")
        
        if vapid_public_key:
            logger.info(f"VAPID Public Key: {vapid_public_key[:50]}...")
            
    except Exception as e:
        logger.error(f"Error checking VAPID configuration: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("🔍 DEBUG: Checking push notification configuration...")
    check_vapid_configuration()
    check_push_subscriptions()
    logger.info("🔍 DEBUG: Check complete!")
