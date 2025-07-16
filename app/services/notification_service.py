import logging
import aiohttp
import asyncio
import json
from typing import Dict, Optional, Any
from app.config.settings import settings as app_settings
from app.services.twitch_api import twitch_api
from apprise import Apprise, NotifyFormat
from app.models import GlobalSettings, NotificationSettings, Streamer, PushSubscription
from app.database import SessionLocal
from app.services.enhanced_push_service import EnhancedPushService, enhanced_push_service

logger = logging.getLogger("streamvault")

class NotificationService:
    def __init__(self, websocket_manager=None):
        self.apprise = Apprise()
        self._notification_url = None
        self.websocket_manager = websocket_manager
        self.push_service = enhanced_push_service
        self._initialize_apprise()

    def _initialize_apprise(self):
        """Initialize Apprise with the notification URL from settings"""
        try:
            with SessionLocal() as db:
                settings = db.query(GlobalSettings).first()
                if not settings or not settings.notifications_enabled:
                    logger.debug("Notifications disabled")
                    return
                
                if not settings.notification_url:
                    logger.debug("No notification URL configured")
                    return

                url = settings.notification_url.strip()
                self._notification_url = url
                self.apprise = Apprise()
                
                # Try to add the URL to Apprise
                if self.apprise.add(url):
                    logger.info(f"Apprise initialized successfully with URL: {url}")
                else:
                    logger.error(f"Failed to initialize Apprise with URL: {url}")
                    self._notification_url = None
                    
        except Exception as e:
            logger.error(f"Error initializing Apprise: {e}")
            self._notification_url = None

    async def send_notification(self, message: str, title: str = "StreamVault Notification") -> bool:
        with SessionLocal() as db:
            settings = db.query(GlobalSettings).first()
            if not settings or not settings.notifications_enabled:
                logger.debug("Notifications are disabled, skipping")
                return False
            if not settings.notification_url:
                logger.debug("No notification URLs configured, skipping")
                return False

        # Refresh URLs before sending
        self._initialize_apprise()
        
        logger.debug(f"Preparing to send notification: {message[:50]}...")
        try:
            result = await self.apprise.async_notify(
                body=message,
                title=title
            )
            if result:
                logger.info("Notification sent successfully")
            else:
                logger.error("Failed to send notification - Apprise returned False")
            return result
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            return False

    def _get_service_specific_url(self, base_url: str, twitch_url: str, profile_image: str, streamer_name: str, event_type: str, original_image_url: Optional[str] = None) -> str:
        """Configure service-specific parameters based on the notification service."""

        logger.debug(f"Configuring service-specific URL for {base_url}")
    
        # Get appropriate title based on event type
        title_map = {
            "online": f"{streamer_name} is live!",
            "offline": f"{streamer_name} went offline",
            "update": f"{streamer_name} updated stream info",
            "test": "StreamVault Test Notification"
        }
    
        if 'ntfy' in base_url:
            # Ntfy configuration
            params = [
                f"click={twitch_url}",
                f"priority={'high' if event_type == 'online' else 'default'}"
            ]
        
            # Event-spezifische Tags
            if event_type == "online":
                params.append("tags=live_stream,online")
            elif event_type == "offline":
                params.append("tags=stream,offline")
            elif event_type == "update":
                params.append("tags=stream,update")
            else:
                params.append("tags=notification")
        
            # Bevorzuge die Original-URL für Benachrichtigungen
            if original_image_url and original_image_url.startswith('http'):
                params.append(f"avatar_url={original_image_url}")
                logger.debug(f"Using original Twitch profile URL: {original_image_url}")
            elif profile_image and profile_image.startswith('http'):
                params.append(f"avatar_url={profile_image}")
                logger.debug(f"Using profile image URL: {profile_image}")
        
            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated ntfy URL: {final_url}")
            return final_url
    
        # Der Rest der Methode bleibt unverändert...    
        elif 'discord' in base_url:
            # Discord configuration
            final_url = (f"{base_url}?"
                    f"avatar_url={profile_image if event_type != 'test' else '/app/frontend/public/ms-icon-310x310.png'}&"
                    f"title={title_map.get(event_type, 'StreamVault Notification')}&"
                    f"href={twitch_url}&"
                    f"format=markdown")
            logger.debug(f"Generated discord URL: {final_url}")
            return final_url
            
        elif 'telegram' in base_url or 'tgram' in base_url:
            # Telegram configuration
            params = []
            if profile_image:
                params.append("image=yes")
            params.append("format=markdown")
            final_url = f"{base_url}?{'&'.join(params)}" if params else base_url
            logger.debug(f"Generated telegram URL: {final_url}")
            return final_url
    
        elif 'matrix' in base_url:
            # Matrix configuration
            params = [
                "msgtype=text",
                "format=markdown",
                f"thumbnail={'true' if profile_image else 'false'}"
            ]
            final_url = f"{base_url}?{'&'.join(params)}"
            logger.debug(f"Generated matrix URL: {final_url}")
            return final_url
    
        elif 'slack' in base_url:
            # Slack configuration
            final_url = (f"{base_url}?"
                    f"footer=yes&"
                    f"image={'yes' if profile_image else 'no'}")
            logger.debug(f"Generated slack URL: {final_url}")
            return final_url
    
        elif 'pover' in base_url:
            # Pushover configuration
            priority = "high" if event_type == "online" else "normal"
            final_url = (f"{base_url}?"
                    f"priority={priority}&"
                    f"url={twitch_url}&"
                    f"url_title=Watch Stream")
            logger.debug(f"Generated pushover URL: {final_url}")
            return final_url
    
        # Default case - return original URL if service not specifically handled
        logger.debug(f"No specific configuration for this service, using base URL: {base_url}")
        return base_url
    async def send_stream_notification(self, streamer_name: str, event_type: str, details: dict):
        try:
            logger.info(f"🔔 SEND_STREAM_NOTIFICATION: streamer={streamer_name}, event={event_type}, details_keys={list(details.keys())}")
            
            # Send WebSocket notification first
            if self.websocket_manager:
                # Map event types to correct WebSocket types
                websocket_type = f"stream.{event_type}"
                if event_type == "update":
                    websocket_type = "channel.update"
                
                websocket_notification = {
                    "type": websocket_type,
                    "data": {
                        "streamer_name": streamer_name,
                        "username": streamer_name,  # For compatibility
                        "title": details.get("title"),
                        "category_name": details.get("category_name"),
                        "language": details.get("language"),
                        "started_at": details.get("started_at"),
                        "url": details.get("url"),
                        "profile_image_url": details.get("profile_image_url"),
                        "streamer_id": details.get("streamer_id"),
                        "twitch_id": details.get("twitch_id"),
                        "is_live": details.get("is_live")
                    }
                }
                logger.debug(f"Sending WebSocket notification: {websocket_notification}")
                await self.websocket_manager.send_notification(websocket_notification)
            
            # Send push notifications to all active subscribers
            await self._send_push_notifications(streamer_name, event_type, details)
            
            # Check if we should send external notifications
            if 'streamer_id' in details:
                should_send = await self.should_notify(details['streamer_id'], event_type)
                if not should_send:
                    logger.debug(f"Notifications disabled for streamer {details['streamer_id']} and event {event_type}")
                    return
            
            # Send external notification (Apprise)
            await self._send_external_notification(streamer_name, event_type, details)
                
        except Exception as e:
            logger.error(f"Error in send_stream_notification: {e}", exc_info=True)
    
    async def _send_external_notification(self, streamer_name: str, event_type: str, details: dict):
        """Send external notification via Apprise"""
        try:
            logger.debug(f"Starting send_stream_notification for {streamer_name}, event type: {event_type}")
        
            with SessionLocal() as db:
                settings = db.query(GlobalSettings).first()
                if not settings or not settings.notifications_enabled:
                    logger.debug("Global notifications disabled")
                    return False

                # Case insensitive search for streamer
                streamer = db.query(Streamer).filter(
                    Streamer.username.ilike(streamer_name)
                ).first()
            
                if not streamer:
                    logger.debug(f"Streamer {streamer_name} not found in database")
                    return False

                # Check if notifications are enabled for this specific event type
                should_send = await self.should_notify(streamer.id, event_type)
                logger.debug(f"Should notify for {streamer_name} - {event_type}: {should_send}")
            
                if not should_send:
                    logger.debug(f"Notifications disabled for {streamer_name} - {event_type}")
                    return False

                # Get service-specific URL configuration
                twitch_url = f"https://twitch.tv/{streamer_name}"
                notification_url = self._get_service_specific_url(
                    base_url=settings.notification_url,
                    twitch_url=twitch_url,
                    profile_image=streamer.profile_image_url or "",
                    streamer_name=streamer_name,
                    event_type=event_type,
                    original_image_url=details.get("profile_image_url")
                )

                # Create new Apprise instance
                apprise = Apprise()
                if not apprise.add(notification_url):
                    logger.error(f"Failed to initialize notification URL: {notification_url}")
                    return False

                # Format message using existing method
                title, message = self._format_notification_message(
                    streamer_name=streamer_name,
                    event_type=event_type,
                    details=details
                )                # Send notification
                logger.debug(f"Sending notification with title: {title}, message: {message[:50]}...")
                result = await apprise.async_notify(
                    title=title,
                    body=message,
                    body_format=NotifyFormat.TEXT
                )
        
                if not result:
                    logger.error("Apprise notification failed to send")
            
                logger.debug(f"Notification result: {result}")
                return result

        except Exception as e:
            logger.error(f"Error sending notification: {e}", exc_info=True)
            return False
    
    async def _send_push_notifications(self, streamer_name: str, event_type: str, details: dict):
        """Send push notifications to all active subscribers"""
        try:
            logger.info(f"🔔 PUSH_NOTIFICATION_ATTEMPT: streamer={streamer_name}, event={event_type}, details={details}")
            
            with SessionLocal() as db:
                # Get all active push subscriptions
                active_subscriptions = db.query(PushSubscription).filter(
                    PushSubscription.is_active == True
                ).all()
                
                logger.info(f"🔔 PUSH_SUBSCRIPTIONS_FOUND: count={len(active_subscriptions)}")
                
                if not active_subscriptions:
                    logger.warning("🔔 NO_ACTIVE_PUSH_SUBSCRIPTIONS: No active push subscriptions found")
                    return
                
                streamer_id = details.get('streamer_id')
                stream_id = details.get('stream_id')
                stream_title = details.get('title', 'Stream')
                category_name = details.get('category_name', '')
                
                # Skip if we don't have essential data
                if not streamer_id:
                    logger.warning("No streamer_id in details, skipping push notifications")
                    return
                
                # Check if we should send push notifications for this event type and streamer
                should_send = await self.should_notify(int(streamer_id), event_type)
                logger.info(f"🔔 PUSH_NOTIFICATION_CHECK: streamer_id={streamer_id}, event={event_type}, should_send={should_send}")
                
                if not should_send:
                    logger.warning(f"🔔 PUSH_NOTIFICATIONS_DISABLED: streamer_id={streamer_id}, event={event_type}")
                    return
                
                # Send appropriate notification based on event type
                successful_sends = 0
                failed_sends = 0
                
                for subscription in active_subscriptions:
                    try:
                        subscription_data = json.loads(subscription.subscription_data)
                        logger.debug(f"🔔 SENDING_PUSH_TO_SUBSCRIPTION: endpoint={subscription_data.get('endpoint', 'unknown')[:50]}...")
                        
                        success = False
                        if event_type == 'online':
                            success = await self.push_service.send_stream_online_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                int(streamer_id),
                                int(stream_id) if stream_id else None,
                                category_name
                            )
                        elif event_type == 'offline':
                            success = await self.push_service.send_stream_offline_notification(
                                subscription_data,
                                streamer_name,
                                int(streamer_id)
                            )
                        elif event_type == 'update':
                            success = await self.push_service.send_stream_update_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                category_name,
                                int(streamer_id)
                            )
                        elif event_type == 'favorite_category':
                            success = await self.push_service.send_favorite_category_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                category_name,
                                int(streamer_id)
                            )
                        elif event_type == 'recording_started':
                            success = await self.push_service.send_recording_started_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                int(streamer_id),
                                int(stream_id) if stream_id else None
                            )
                        elif event_type == 'recording_finished' and stream_id:
                            duration = details.get('duration', 'Unknown')
                            success = await self.push_service.send_recording_finished_notification(
                                subscription_data,
                                streamer_name,
                                stream_title,
                                int(streamer_id),
                                int(stream_id),
                                duration
                            )
                        
                        if success:
                            successful_sends += 1
                            logger.debug(f"🔔 PUSH_SUCCESS: endpoint={subscription_data.get('endpoint', 'unknown')[:50]}...")
                        else:
                            failed_sends += 1
                            logger.warning(f"🔔 PUSH_FAILED: endpoint={subscription_data.get('endpoint', 'unknown')[:50]}...")
                        
                    except Exception as sub_error:
                        failed_sends += 1
                        logger.error(f"🔔 PUSH_EXCEPTION: {subscription.endpoint[:50]}: {sub_error}")
                        
                        # If subscription is invalid, deactivate it
                        if "410" in str(sub_error) or "expired" in str(sub_error).lower():
                            subscription.is_active = False
                            db.commit()
                            logger.info(f"Deactivated expired push subscription: {subscription.endpoint[:50]}")
                
                logger.info(f"🔔 PUSH_NOTIFICATION_SUMMARY: event={event_type}, successful={successful_sends}, failed={failed_sends}, total={len(active_subscriptions)}")
                
        except Exception as e:
            logger.error(f"🔔 PUSH_NOTIFICATION_ERROR: {e}", exc_info=True)
    
    async def should_notify(self, streamer_id: int, event_type: str) -> bool:
        with SessionLocal() as db:
            global_settings = db.query(GlobalSettings).first()
            logger.debug(f"Global settings: notifications_enabled={global_settings.notifications_enabled if global_settings else 'None'}")

            if not global_settings or not global_settings.notifications_enabled:
                logger.debug("Global notifications disabled")
                return False

            # Map event types to settings fields
            setting_map = {
                "online": ("notify_online", "notify_online_global"),
                "offline": ("notify_offline", "notify_offline_global"),
                "update": ("notify_update", "notify_update_global"),
                "favorite_category": ("notify_favorite_category", "notify_favorite_category_global")
            }

            streamer_field, global_field = setting_map.get(event_type, (None, None))
            if not streamer_field or not global_field:
                logger.debug(f"Unknown event type: {event_type}")
                return False
                
            # Wichtig: Debug-Ausgabe der globalen Einstellung
            global_enabled = getattr(global_settings, global_field)
            logger.debug(f"Global setting for {event_type}: {global_enabled}")
            
            if not global_enabled:
                logger.debug(f"Global notifications for {event_type} are disabled")
                return False

            # Streamer-spezifische Einstellungen prüfen
            streamer_settings = db.query(NotificationSettings)\
                .filter(NotificationSettings.streamer_id == streamer_id)\
                .first()

            # Wenn keine streamer-spezifischen Einstellungen existieren, verwende global
            if not streamer_settings:
                logger.debug(f"No specific settings for streamer {streamer_id}, using global: {global_enabled}")
                return global_enabled
                
            # Streamer-spezifische Einstellung holen
            streamer_enabled = getattr(streamer_settings, streamer_field)
            logger.debug(f"Streamer-specific setting for {event_type}: {streamer_enabled}")
            
            # Für diesen Streamer aktiviert?
            return streamer_enabled

    async def send_test_notification(self) -> bool:
        """Send a test notification using current settings"""
        try:
            if not self._notification_url:
                logger.error("No notification URL configured")
                return False

            # Create new Apprise instance for test
            apprise = Apprise()
            if not apprise.add(self._notification_url):
                logger.error(f"Invalid notification URL: {self._notification_url}")
                return False
                
            logger.debug(f"Sending test notification via: {self._notification_url}")
            
            result = await apprise.async_notify(
                title="🔔 StreamVault Test Notification",
                body=(
                    "This is a test notification from StreamVault.\n\n"
                    "If you receive this, your notification settings are working correctly!"
                )
            )
            
            if result:
                logger.info("Test notification sent successfully")
                return True
            
            logger.error("Failed to send test notification")
            return False
                
        except Exception as e:
            logger.error(f"Error sending test notification: {e}")
            return False

    def _format_notification_message(self, streamer_name: str, event_type: str, details: dict) -> tuple[str, str]:
        """Format notification message and title based on event type"""
        title = "StreamVault Notification"
    
        if event_type == "online":
            title = f"🟢 {streamer_name} is now live!"
            message = (
                f"Started streaming: {details.get('title', 'No title')}\n"
                f"Category: {details.get('category_name', 'No category')}"
            )
        elif event_type == "offline":
            title = f"🔴 {streamer_name} went offline"
            message = "Stream ended"
        elif event_type == "update":
            title = f"📝 {streamer_name} updated stream"
            message = (
                f"New title: {details.get('title', 'No title')}\n"
                f"Category: {details.get('category_name', 'No category')}"
            )
        elif event_type == "favorite_category":
            title = f"🎮 {streamer_name} spielt ein Favoriten-Spiel!"
            message = (
                f"🎮 {streamer_name} spielt jetzt {details.get('category_name', 'Unknown Game')}!\n\n"
                f"Titel: {details.get('title', 'No title')}\n"
                f"Dieses Spiel ist in deinen Favoriten."
            )
        else:
            title = f"StreamVault: {streamer_name}"
            message = f"Event notification for {streamer_name}"
    
        return title, message

async def get_user_info(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user info from Twitch API including profile image"""
    try:
        users = await twitch_api.get_users_by_id([user_id])
        return users[0] if users else None
    except Exception as e:
        logger.error(f"Error fetching user info: {e}")
        return None
