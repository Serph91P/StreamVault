from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PushSubscription
from app.config.settings import get_settings
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("streamvault")
router = APIRouter(prefix="/api/push", tags=["push"])

settings = get_settings()

@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Get VAPID public key for push subscription"""
    # You should generate these keys and store them securely
    # For now, return a placeholder - in production, use real VAPID keys
    public_key = getattr(settings, 'VAPID_PUBLIC_KEY', 'BEl62iUYgUivxIkv69yViEuiBIa40HI0DLLuxazjqAKHSr')
    
    return {
        "publicKey": public_key
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
        from app.services.push_service import PushService
        
        push_service = PushService()
        
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
        
        sent_count = 0
        for subscription in active_subscriptions:
            try:
                subscription_data = json.loads(subscription.subscription_data)
                await push_service.send_notification(subscription_data, notification_data)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send test notification to {subscription.endpoint[:50]}: {e}")
        
        return {
            "success": True,
            "message": f"Test notifications sent to {sent_count} subscribers"
        }
        
    except Exception as e:
        logger.error(f"Error sending test notification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
