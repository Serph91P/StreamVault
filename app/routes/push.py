from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PushSubscription
from app.config.settings import get_settings
from app.utils.error_handler import handle_api_error, create_error_response, ERRORS
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
        logger.info("🔔 PUSH_SUBSCRIBE_REQUEST: Starting subscription process")
        logger.debug(f"🔔 Request data keys: {list(subscription_data.keys())}")

        subscription = subscription_data.get('subscription', {})
        user_agent = subscription_data.get('userAgent', '')

        logger.debug(f"🔔 Subscription keys: {list(subscription.keys()) if subscription else 'None'}")
        logger.debug(f"🔔 User agent: {user_agent[:50]}..." if user_agent else "🔔 No user agent")

        if not subscription or 'endpoint' not in subscription:
            logger.error("🔔 INVALID_SUBSCRIPTION_DATA: Missing subscription or endpoint")
            raise HTTPException(status_code=400, detail="Invalid subscription data")

        endpoint = subscription['endpoint']
        logger.debug(f"🔔 Endpoint: {endpoint[:50]}...")

        # Check if subscription already exists
        existing = db.query(PushSubscription).filter(
            PushSubscription.endpoint == endpoint
        ).first()

        if existing:
            logger.info(f"🔔 UPDATING_EXISTING_SUBSCRIPTION: id={existing.id}")
            # Update existing subscription
            existing.subscription_data = json.dumps(subscription)
            existing.user_agent = user_agent
            existing.is_active = True
        else:
            logger.info("🔔 CREATING_NEW_SUBSCRIPTION")
            # Create new subscription
            new_subscription = PushSubscription(
                endpoint=endpoint,
                subscription_data=json.dumps(subscription),
                user_agent=user_agent,
                is_active=True
            )
            db.add(new_subscription)

        db.commit()

        # Verify subscription was saved
        total_active = db.query(PushSubscription).filter(PushSubscription.is_active.is_(True)).count()
        logger.info(f"🔔 SUBSCRIPTION_SAVED: endpoint={endpoint[:50]}...")
        logger.info(f"🔔 TOTAL_ACTIVE_SUBSCRIPTIONS: count={total_active}")

        return {
            "success": True,
            "message": "Push subscription successful"
        }

    except Exception as e:
        db.rollback()
        raise handle_api_error(e, "subscribing to push notifications", 500, ERRORS["SUBSCRIPTION_FAILED"])


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
        raise handle_api_error(e, "unsubscribing from push notifications", 500, ERRORS["UNSUBSCRIPTION_FAILED"])


@router.post("/test")
async def send_test_notification(db: Session = Depends(get_db)):
    """Send a test push notification to all active subscriptions"""
    try:
        logger.info("🧪 PUSH_TEST_REQUESTED: Starting push notification test")

        from app.services.communication.webpush_service import ModernWebPushService
        from app.models import GlobalSettings

        # Check VAPID configuration
        if not settings.has_push_notifications_configured:
            logger.warning("🧪 PUSH_TEST_FAILED: VAPID keys not configured")
            return {
                "success": False,
                "message": "Push notification service is not properly configured. Please contact an administrator."
            }

        # Initialize push service
        vapid_claims = {
            "sub": getattr(settings, 'VAPID_CLAIMS_SUB', "mailto:admin@streamvault.local")
        }
        push_service = ModernWebPushService(
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims=vapid_claims
        )

        # Check global notification settings
        global_settings = db.query(GlobalSettings).first()
        global_notifications_enabled = global_settings and global_settings.notifications_enabled

        logger.info(f"🧪 GLOBAL_NOTIFICATIONS_ENABLED: {global_notifications_enabled}")

        # Get active subscriptions
        active_subscriptions = db.query(PushSubscription).filter(
            PushSubscription.is_active.is_(True)
        ).all()

        logger.info(f"🧪 ACTIVE_SUBSCRIPTIONS_FOUND: {len(active_subscriptions)}")

        if not active_subscriptions:
            return {
                "success": False,
                "message": "No active push subscriptions found. Please enable push notifications in a browser first."
            }

        notification_data = {
            "title": "🧪 StreamVault Test",
            "body": "This is a test notification from StreamVault. If you see this, push notifications are working!",
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "test",
            "url": "/",
            "requireInteraction": True,
            "timestamp": int(time.time() * 1000)
        }

        sent_count = 0
        failed_count = 0
        failed_endpoints = []

        for subscription in active_subscriptions:
            try:
                subscription_data = json.loads(subscription.subscription_data)
                endpoint = subscription_data.get('endpoint', 'unknown')[:50]

                logger.debug(f"🧪 SENDING_TEST_TO: {endpoint}...")

                success = push_service.send_notification(subscription_data, notification_data)
                if success:
                    sent_count += 1
                    logger.info(f"🧪 TEST_SUCCESS: {endpoint}...")
                else:
                    failed_count += 1
                    failed_endpoints.append(endpoint)
                    logger.warning(f"🧪 TEST_FAILED: {endpoint}...")

            except Exception as e:
                failed_count += 1
                endpoint = subscription.endpoint[:50] if subscription.endpoint else 'unknown'
                failed_endpoints.append(f"{endpoint} (error: {str(e)[:30]})")
                logger.error(f"🧪 TEST_EXCEPTION: {endpoint}: {e}")

        logger.info(f"🧪 PUSH_TEST_SUMMARY: sent={sent_count}, failed={failed_count}, total={len(active_subscriptions)}")

        # Only include debug info in development mode or for admin users
        # Remove sensitive debug information for production

        if sent_count > 0:
            return {
                "success": True,
                "message": f"Test notifications sent to {sent_count} subscribers"
                + (f" ({failed_count} failed)" if failed_count > 0 else ""),
                "sent_count": sent_count,
                "failed_count": failed_count
            }
        else:
            return {
                "success": False,
                "message": f"Failed to send notifications to all {len(active_subscriptions)} subscribers. Check VAPID key configuration or subscription validity.",
                "suggestion": "Check browser console for errors or try re-subscribing to push notifications"
            }

    except Exception:
        return create_error_response(
            success=False,
            message="Server error while sending test notification. Please contact support if the issue persists.",
            error_code="NOTIFICATION_TEST_FAILED"
        )


@router.get("/debug")
async def get_push_debug_info(db: Session = Depends(get_db)):
    """Get debug information about push notification configuration - Admin only"""
    try:
        # Note: This endpoint should ideally be protected by authentication
        # For security, we'll limit the information returned

        from app.models import GlobalSettings, NotificationSettings

        # Check basic configuration status
        vapid_configured = settings.has_push_notifications_configured

        # Check global settings
        global_settings = db.query(GlobalSettings).first()
        global_notifications_enabled = global_settings and global_settings.notifications_enabled

        # Check subscriptions count
        active_subscriptions = db.query(PushSubscription).filter(
            PushSubscription.is_active.is_(True)
        ).count()

        # Check streamers count
        streamers_with_settings = db.query(NotificationSettings).count()

        # Build a minimal debug response
        debug_info = {
            "configuration_status": {
                "vapid_configured": vapid_configured,
                "global_notifications_enabled": global_notifications_enabled,
                "has_active_subscriptions": active_subscriptions > 0,
                "has_streamer_settings": streamers_with_settings > 0
            },
            "issues": []
        }

        # Identify potential issues
        if not vapid_configured:
            debug_info["issues"].append("Push notification service not configured")
        if not global_notifications_enabled:
            debug_info["issues"].append("Global notifications disabled")
        if active_subscriptions == 0:
            debug_info["issues"].append("No active push subscriptions")
        if streamers_with_settings == 0:
            debug_info["issues"].append("No streamer notification settings configured")

        return {
            "success": True,
            "debug": debug_info
        }

    except Exception:
        return create_error_response(
            success=False,
            message="Failed to get debug information",
            error_code="DEBUG_INFO_FAILED"
        )


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
                }}
        }
    except Exception as e:
        logger.error(f"Error creating local test notification: {e}", exc_info=True)
        return {
            "success": False,
            "message": "Failed to prepare local test notification. An internal error occurred. Please try again later."
        }
