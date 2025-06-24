from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PushSubscription
from app.config.settings import get_settings
import json
import logging
from typing import Dict, Any
import time

logger = logging.getLogger("streamvault")
router = APIRouter(prefix="/api/push", tags=["push"])

settings = get_settings()

@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Get VAPID public key for push subscription"""
    if not settings.has_push_notifications_configured:
        logger.warning("🔑 Push notifications requested but VAPID keys not configured")
        raise HTTPException(
            status_code=503, 
            detail={
                "error": "Push notifications not configured",
                "message": "VAPID keys are missing. They should be auto-generated on startup.",
                "suggestion": "Check server logs for VAPID key generation or restart the application"
            }
        )
    
    logger.debug("🔑 Serving VAPID public key for push subscription")
    return {
        "publicKey": settings.VAPID_PUBLIC_KEY,  # This is already base64 encoded
        "configured": True
    }

@router.post("/subscribe")
async def subscribe_to_push(
    subscription_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Subscribe a client to push notifications"""
    try:
        subscription = subscription_data.get('subscription', {})
        user_agent = subscription_data.get('userAgent', '')
        
        if not subscription or 'endpoint' not in subscription:
            raise HTTPException(status_code=400, detail="Invalid subscription data")
        
        endpoint = subscription['endpoint']
        
        # Check if subscription already exists
        existing = db.query(PushSubscription).filter(
            PushSubscription.endpoint == endpoint
        ).first()
        
        if existing:
            # Update existing subscription
            existing.subscription_data = json.dumps(subscription)
            existing.user_agent = user_agent
            existing.is_active = True
        else:
            # Create new subscription
            new_subscription = PushSubscription(
                endpoint=endpoint,
                subscription_data=json.dumps(subscription),
                user_agent=user_agent,
                is_active=True
            )
            db.add(new_subscription)
        
        db.commit()
        
        logger.info(f"Push subscription added/updated: {endpoint[:50]}...")
        
        return {
            "success": True,
            "message": "Push subscription successful"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error subscribing to push: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unsubscribe")
async def unsubscribe_from_push(
    unsubscribe_data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """Unsubscribe a client from push notifications"""
    try:
        endpoint = unsubscribe_data.get('endpoint')
        
        if not endpoint:
            raise HTTPException(status_code=400, detail="Endpoint required")
        
        # Find and deactivate subscription
        subscription = db.query(PushSubscription).filter(
            PushSubscription.endpoint == endpoint
        ).first()
        
        if subscription:
            subscription.is_active = False
            db.commit()
            logger.info(f"Push subscription deactivated: {endpoint[:50]}...")
        
        return {
            "success": True,
            "message": "Push unsubscription successful"
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error unsubscribing from push: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test")
async def send_test_notification(db: Session = Depends(get_db)):
    """Send a test push notification to all active subscriptions"""
    try:
        from app.services.enhanced_push_service import EnhancedPushService, enhanced_push_service
        
        push_service = enhanced_push_service
        
        notification_data = {
            "title": "StreamVault Test",
            "body": "This is a test notification from StreamVault",
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "test",
            "url": "/"
        }
        
        active_subscriptions = db.query(PushSubscription).filter(
            PushSubscription.is_active == True
        ).all()
        
        if not active_subscriptions:
            return {
                "success": False,
                "message": "No active push subscriptions found",
                "sent_count": 0
            }
        
        sent_count = 0
        failed_count = 0
        
        for subscription in active_subscriptions:
            try:
                subscription_data = json.loads(subscription.subscription_data)
                success = await push_service.send_notification(subscription_data, notification_data)
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to send test notification to {subscription.endpoint[:50]}: {e}")
        
        if sent_count > 0:
            return {
                "success": True,
                "message": f"Test notifications sent to {sent_count} subscribers" + 
                          (f" ({failed_count} failed)" if failed_count > 0 else ""),
                "sent_count": sent_count,
                "failed_count": failed_count
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send notifications to all {len(active_subscriptions)} subscribers. Check VAPID key configuration.",
                "sent_count": 0,
                "failed_count": failed_count,
                "suggestion": "Try restarting the server or resetting VAPID keys"            }
        
    except Exception as e:
        logger.error(f"Error sending test notification: {e}", exc_info=True)
        return {
            "success": False,
            "message": "Server error while sending test notification. Please contact support if the issue persists."
        }

@router.post("/test-local")
async def send_test_local_notification():
    """Send a test notification via Service Worker without push"""
    try:
        return {
            "success": True,
            "message": "Local test notification data prepared - use this data to trigger a notification via Service Worker",
            "notification": {
                "title": "🧪 StreamVault Test (Local)",
                "body": "If you see this, local PWA notifications are working perfectly! This is a fallback test.",
                "icon": "/android-icon-192x192.png",
                "badge": "/android-icon-96x96.png",
                "type": "test_local",
                "requireInteraction": True,
                "timestamp": int(time.time() * 1000),
                "tag": "test-local-notification",
                "data": {
                    "url": "/",
                    "type": "test_local"
                }            }
        }
    except Exception as e:
        logger.error(f"Error creating local test notification: {e}", exc_info=True)
        return {
            "success": False,
            "message": "Failed to prepare local test notification. An internal error occurred. Please try again later."
        }
