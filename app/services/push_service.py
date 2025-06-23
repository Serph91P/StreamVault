import json
import logging
import base64
from typing import Dict, Any, Optional
from pywebpush import webpush, WebPushException
from app.config.settings import settings

logger = logging.getLogger("streamvault")

class PushService:
    def __init__(self):
        self.settings = settings
        
        # VAPID keys - pywebpush expects raw DER bytes for private key
        vapid_private_key_raw = getattr(self.settings, 'VAPID_PRIVATE_KEY', None)
        vapid_public_key_raw = getattr(self.settings, 'VAPID_PUBLIC_KEY', None)
        
        # For pywebpush, we need to pass the private key as raw DER bytes
        if vapid_private_key_raw and isinstance(vapid_private_key_raw, str):
            try:
                # Decode from base64 to get the raw DER bytes
                self.vapid_private_key = base64.b64decode(vapid_private_key_raw)
            except Exception as e:
                logger.error(f"Failed to decode VAPID private key: {e}")
                self.vapid_private_key = None
        else:
            self.vapid_private_key = vapid_private_key_raw
              # For public key, keep it as base64 string for frontend API
        self.vapid_public_key = vapid_public_key_raw
            
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
            
            # Debug logging
            logger.debug(f"Sending push notification with payload: {payload[:100]}...")
            logger.debug(f"Private key type: {type(self.vapid_private_key)}")
            logger.debug(f"Private key length: {len(self.vapid_private_key) if self.vapid_private_key else 0}")
            
            # Send the push notification using raw DER bytes
            webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=self.vapid_private_key,  # This should be raw DER bytes
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
        stream_id: Optional[int] = None,
        category_name: str = None
    ) -> bool:
        """Send a notification when a stream goes online"""
        # Use same format as Apprise notifications
        title = f"🟢 {streamer_name} is now live!"
        body = f"Started streaming: {stream_title or 'No title'}"
        if category_name:
            body += f"\nCategory: {category_name}"
            
        notification_data = {
            "title": title,
            "body": body,
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "stream_online",
            "data": {
                "streamer_id": streamer_id,
                "stream_id": stream_id,
                "url": f"https://twitch.tv/{streamer_name.lower()}",
                "internal_url": f"/streamer/{streamer_id}"
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
        # Simple recording notification - no actions needed for recording start
        notification_data = {
            "title": f"📹 Recording started: {streamer_name}",
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
            "title": f"✅ Recording finished: {streamer_name}",
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

    async def send_stream_offline_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        streamer_id: int
    ) -> bool:
        """Send a notification when a stream goes offline"""
        # Use same format as Apprise notifications - simple offline notification
        notification_data = {
            "title": f"🔴 {streamer_name} went offline",
            "body": "Stream ended",
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "stream_offline",
            "data": {
                "streamer_id": streamer_id,
                "url": f"/streamer/{streamer_id}"
            },
            "tag": f"stream-offline-{streamer_id}"
        }
        
        return await self.send_notification(subscription, notification_data)

    async def send_stream_update_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        stream_title: str,
        category_name: str,
        streamer_id: int
    ) -> bool:
        """Send a notification when stream info is updated"""
        # Use same format as Apprise notifications
        title = f"📝 {streamer_name} updated stream"
        body = f"New title: {stream_title or 'No title'}"
        if category_name:
            body += f"\nCategory: {category_name}"
            
        notification_data = {
            "title": title,
            "body": body,
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "stream_update",
            "data": {
                "streamer_id": streamer_id,
                "url": f"https://twitch.tv/{streamer_name.lower()}",
                "internal_url": f"/streamer/{streamer_id}"
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
            "tag": f"stream-update-{streamer_id}"
        }
        
        return await self.send_notification(subscription, notification_data)

    async def send_favorite_category_notification(
        self,
        subscription: Dict[str, Any],
        streamer_name: str,
        stream_title: str,
        category_name: str,
        streamer_id: int
    ) -> bool:
        """Send a notification when a streamer plays a favorite game"""
        # Use same format as Apprise notifications
        title = f"🎮 {streamer_name} spielt ein Favoriten-Spiel!"
        body = f"🎮 {streamer_name} spielt jetzt {category_name}!\n\nTitel: {stream_title or 'No title'}\nDieses Spiel ist in deinen Favoriten."
            
        notification_data = {
            "title": title,
            "body": body,
            "icon": "/android-icon-192x192.png",
            "badge": "/android-icon-96x96.png",
            "type": "favorite_category",
            "data": {
                "streamer_id": streamer_id,
                "category_name": category_name,
                "url": f"https://twitch.tv/{streamer_name.lower()}",
                "internal_url": f"/streamer/{streamer_id}"
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
            "tag": f"favorite-category-{streamer_id}"
        }
        
        return await self.send_notification(subscription, notification_data)
