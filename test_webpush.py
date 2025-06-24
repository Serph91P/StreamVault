"""
Test script for the new webpush service
"""
from app.services.webpush_service import ModernWebPushService
from app.config.settings import settings
import argparse
import sys
import json
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_web_push():
    """Test the web push service with a simple notification"""
    parser = argparse.ArgumentParser(description='Test the modern web push service')
    parser.add_argument('--subscription', required=True, help='Subscription JSON string or file path')
    
    args = parser.parse_args()
    
    # Get the subscription info
    try:
        # Try to parse as JSON string first
        try:
            subscription = json.loads(args.subscription)
        except json.JSONDecodeError:
            # If not valid JSON, try to load from file
            with open(args.subscription, 'r') as f:
                subscription = json.load(f)
                
        logger.info(f"Using subscription: {json.dumps(subscription)[:100]}...")
        
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Failed to parse subscription: {e}")
        sys.exit(1)
    
    # Get VAPID keys from settings
    vapid_private_key = getattr(settings, 'VAPID_PRIVATE_KEY', None)
    vapid_claims_sub = getattr(settings, 'VAPID_CLAIMS_SUB', "mailto:admin@streamvault.local")
    
    if not vapid_private_key:
        logger.error("VAPID_PRIVATE_KEY not configured")
        sys.exit(1)
    
    # Initialize the web push service
    service = ModernWebPushService(
        vapid_private_key=vapid_private_key,
        vapid_claims={"sub": vapid_claims_sub}
    )
    
    # Create a test notification
    notification = {
        "title": "Test Notification",
        "body": "This is a test notification from the modern web push service",
        "icon": "/android-icon-192x192.png"
    }
    
    # Send the notification
    logger.info("Sending test notification...")
    success = service.send_notification(
        subscription_info=subscription,
        data=notification,
        ttl=30
    )
    
    if success:
        logger.info("Test notification sent successfully!")
    else:
        logger.error("Failed to send test notification")
        sys.exit(1)

if __name__ == "__main__":
    test_web_push()
