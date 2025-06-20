import json
import logging
from typing import Dict, Any, Optional
from pywebpush import webpush, WebPushException
from app.config.settings import settings

logger = logging.getLogger("streamvault")

class PushService:
    def __init__(self):
        self.settings = settings
        
        # VAPID keys - in production, generate these and store securely
        self.vapid_private_key = getattr(self.settings, 'VAPID_PRIVATE_KEY', None)
        self.vapid_public_key = getattr(self.settings, 'VAPID_PUBLIC_KEY', None)
        self.vapid_claims = {
            "sub": getattr(self.settings, 'VAPID_CLAIMS_SUB', "mailto:admin@streamvault.local")
        }
    
    async def send_notification(
        self, 
        subscription: Dict[str, Any], 
        notification_data: Dict[str, Any]
    ) -> bool:
        """Send a push notification to a specific subscription"""
        try:
            if not self.vapid_private_key or not self.vapid_public_key:
                logger.warning("VAPID keys not configured, cannot send push notifications")
                return False
            
            # Prepare the notification payload
            payload = json.dumps(notification_data)
            
            # Send the push notification
            webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=self.vapid_claims
            )
            
            logger.debug(f"Push notification sent successfully to {subscription.get('endpoint', 'unknown')[:50]}...")
            return True
            
        except WebPushException as e:
            logger.error(f"WebPush error: {e}")
            
            # Handle different error codes
            if e.response and e.response.status_code == 410:
                # Subscription is no longer valid
                logger.info(f"Subscription expired: {subscription.get('endpoint', 'unknown')[:50]}...")
                return False
            elif e.response and e.response.status_code == 413:
                logger.warning("Payload too large")
                return False
            else:
                logger.error(f"Push notification failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Unexpected error sending push notification: {e}", exc_info=True)
            return False
    
    async def send_stream_online_notification(
        self, 
        subscription: Dict[str, Any], 
        streamer_name: str,
        stream_title: str,
        streamer_id: int,
        stream_id: Optional[int] = None
    ) -> bool:
        """Send a notification when a stream goes online"""
        notification_data = {
            "title": f"{streamer_name} is now live!",
            "body": stream_title or "Started streaming",
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "stream_online",
            "data": {
                "streamer_id": streamer_id,
                "stream_id": stream_id,
                "url": f"/streamer/{streamer_id}"
            },
            "actions": [
                {
                    "action": "view_stream",
                    "title": "View Stream"
                },
                {
                    "action": "dismiss",
                    "title": "Dismiss"
                }
            ],
            "requireInteraction": True,
            "tag": f"stream-online-{streamer_id}"
        }
        
        return await self.send_notification(subscription, notification_data)
    
    async def send_recording_started_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        stream_title: str,
        streamer_id: int,
        stream_id: Optional[int] = None
    ) -> bool:
        """Send a notification when recording starts"""
        notification_data = {
            "title": f"Recording started: {streamer_name}",
            "body": f"Now recording: {stream_title or 'Stream'}",
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "recording_started",
            "data": {
                "streamer_id": streamer_id,
                "stream_id": stream_id,
                "url": f"/streamer/{streamer_id}"
            },
            "tag": f"recording-started-{streamer_id}"
        }
        
        return await self.send_notification(subscription, notification_data)
    
    async def send_recording_finished_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        stream_title: str,
        streamer_id: int,
        stream_id: int,
        duration: str
    ) -> bool:
        """Send a notification when recording finishes"""
        notification_data = {
            "title": f"Recording finished: {streamer_name}",
            "body": f"Recorded {duration}: {stream_title or 'Stream'}",
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "recording_finished",
            "data": {
                "streamer_id": streamer_id,
                "stream_id": stream_id,
                "url": f"/streamer/{streamer_id}/stream/{stream_id}/watch"
            },
            "actions": [
                {
                    "action": "view_recording",
                    "title": "Watch Recording"
                },
                {
                    "action": "dismiss",
                    "title": "Dismiss"
                }
            ],
            "tag": f"recording-finished-{stream_id}"
        }
        
        return await self.send_notification(subscription, notification_data)
