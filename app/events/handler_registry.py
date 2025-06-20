import logging
import aiohttp
import asyncio
from typing import Dict, Callable, Awaitable, Any, Optional
from datetime import datetime, timezone, timedelta

from app.database import SessionLocal
from app.services.websocket_manager import ConnectionManager
from app.services.notification_service import NotificationService
from app.services.recording_service import RecordingService
from app.models import (
    Streamer, 
    Stream, 
    StreamEvent, 
    Category,
    User,
    FavoriteCategory,
    NotificationSettings
)
from app.config.settings import settings as app_settings

logger = logging.getLogger('streamvault')

class EventHandlerRegistry:
    def __init__(self, connection_manager: ConnectionManager, settings=None):
        self.recording_service = RecordingService()
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {
            "stream.online": self.handle_stream_online,
            "stream.offline": self.handle_stream_offline,
            "channel.update": self.handle_stream_update
        }
        self.manager = connection_manager
        self.settings = settings or app_settings
        self.notification_service = NotificationService(websocket_manager=connection_manager)
        self._access_token = None
        self.eventsub = None
        self._processed_events = {}
        self._event_cache_timeout = 60

    async def get_access_token(self) -> str:
        if not self._access_token:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://id.twitch.tv/oauth2/token",
                    params={
                        "client_id": self.settings.TWITCH_APP_ID,
                        "client_secret": self.settings.TWITCH_APP_SECRET,
                        "grant_type": "client_credentials"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._access_token = data["access_token"]
                    else:
                        raise ValueError(f"Failed to get access token: {response.status}")
        return self._access_token

    async def initialize_eventsub(self):
        if self.eventsub:
            logger.debug("EventSub already initialized, skipping...")
            return

        base_url = self.settings.WEBHOOK_URL if self.settings else app_settings.WEBHOOK_URL
        callback_url = f"{base_url}/eventsub"
        logger.debug(f"Initializing EventSub with callback URL: {callback_url}")

        self.eventsub = {
            "callback_url": callback_url,
            "secret": self.settings.EVENTSUB_SECRET
        }

        logger.info("EventSub initialized successfully")

    async def subscribe_to_events(self, twitch_id: str):
        if not self.eventsub:
            raise ValueError("EventSub not initialized")

        access_token = await self.get_access_token()
        logger.debug(f"Starting batch subscription process for twitch_id: {twitch_id}")

        async with aiohttp.ClientSession() as session:
            for event_type in self.handlers.keys():
                try:
                    async with session.post(
                        "https://api.twitch.tv/helix/eventsub/subscriptions",
                        headers={
                            "Client-ID": self.settings.TWITCH_APP_ID,
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "type": event_type,
                            "version": "1",
                            "condition": {
                                "broadcaster_user_id": twitch_id
                            },
                            "transport": {
                                "method": "webhook",
                                "callback": self.eventsub["callback_url"],
                                "secret": self.eventsub["secret"]
                            }
                        }
                    ) as response:
                        if response.status == 202:
                            logger.info(f"Subscribed to {event_type} for twitch_id: {twitch_id}")
                        else:
                            error_data = await response.json()
                            logger.error(f"Failed to subscribe to {event_type}. Status: {response.status}, Error: {error_data}")
                except Exception as e:
                    logger.error(f"Error subscribing to {event_type}: {e}")
                    raise

    async def verify_subscription(self, subscription_id: str, max_attempts: int = 10) -> bool:
        access_token = await self.get_access_token()
        
        for attempt in range(max_attempts):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://api.twitch.tv/helix/eventsub/subscriptions",
                        headers={
                            "Client-ID": self.settings.TWITCH_APP_ID,
                            "Authorization": f"Bearer {access_token}"
                        }
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            for sub in data.get("data", []):
                                if sub["id"] == subscription_id and sub["status"] == "enabled":
                                    return True
                        await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error verifying subscription {subscription_id}: {e}")
                await asyncio.sleep(1)
        return False

    def _is_duplicate_event(self, data: dict) -> bool:
        try:
            message_id = data.get("id")
            if not message_id:
                return False
                
            event_data = data.get("event", {})
            broadcaster_id = event_data.get("broadcaster_user_id")
            event_type = data.get("subscription", {}).get("type")
            
            if not broadcaster_id or not event_type:
                return False
                
            event_key = f"{broadcaster_id}:{event_type}"
            event_fingerprint = f"{message_id}:{event_key}"
            now = datetime.now()
            
            expired_keys = []
            for key, timestamp in self._processed_events.items():
                if (now - timestamp).total_seconds() > self._event_cache_timeout:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._processed_events[key]
            
            if event_fingerprint in self._processed_events:
                logger.info(f"Ignoring duplicate event: {event_type} for broadcaster {broadcaster_id}")
                return True
            
            self._processed_events[event_fingerprint] = now
            return False
            
        except Exception as e:
            logger.error(f"Error checking for duplicate event: {e}", exc_info=True)
            return False

    async def handle_stream_online(self, data: dict):
        if self._is_duplicate_event(data):
            return
            
        try:
            user_info = await self.get_user_info(data["broadcaster_user_id"])
            
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(
                    Streamer.twitch_id == data["broadcaster_user_id"]
                ).first()
                
                if streamer:
                    if user_info and user_info.get("profile_image_url"):
                        streamer.profile_image_url = user_info["profile_image_url"]
                
                    stream = Stream(
                        streamer_id=streamer.id,
                        started_at=datetime.fromisoformat(data["started_at"].replace('Z', '+00:00')),
                        twitch_stream_id=data["id"],
                        title=streamer.title,
                        category_name=streamer.category_name,
                        language=streamer.language
                    )
                    db.add(stream)
                    db.flush()
                    
                    initial_event = StreamEvent(
                        stream_id=stream.id,
                        event_type="stream.online",
                        title=streamer.title,
                        category_name=streamer.category_name,
                        language=streamer.language,
                        timestamp=datetime.fromisoformat(data["started_at"].replace('Z', '+00:00'))
                    )
                    db.add(initial_event)
                    
                    if streamer.category_name:
                        pre_stream_event = StreamEvent(
                            stream_id=stream.id,
                            event_type="channel.update",
                            title=streamer.title,
                            category_name=streamer.category_name, 
                            language=streamer.language,
                            timestamp=datetime.fromisoformat(data["started_at"].replace('Z', '+00:00')) - timedelta(seconds=1)
                        )
                        db.add(pre_stream_event)
                        logger.debug(f"Added pre-stream category event for {streamer.category_name}")
                    
                    streamer.is_live = True
                    streamer.last_updated = datetime.now(timezone.utc)
                    db.commit()

                    # Send notification only via notification_service to avoid duplicates
                    await self.notification_service.send_stream_notification(
                        streamer_name=streamer.username,
                        event_type="online",
                        details={
                            "streamer_id": streamer.id,
                            "url": f"https://twitch.tv/{data['broadcaster_user_login']}",
                            "started_at": data["started_at"],
                            "title": streamer.title,
                            "category_name": streamer.category_name,
                            "language": streamer.language,
                            "profile_image_url": streamer.profile_image_url,
                            "twitch_login": data["broadcaster_user_login"]
                        }
                    )
                    
                    logger.debug("Notifications sent successfully")

                    streamer_id = streamer.id
                    await self.recording_service.start_recording(streamer_id, {
                        "id": data["id"],
                        "broadcaster_user_id": data["broadcaster_user_id"],
                        "broadcaster_user_name": data["broadcaster_user_name"],
                        "started_at": data["started_at"],
                        "title": streamer.title,
                        "category_name": streamer.category_name,
                        "language": streamer.language
                    }, force_mode=False)  # Normal EventSub recordings use standard settings
            
        except Exception as e:
            logger.error(f"Error handling stream online event: {e}", exc_info=True)
            
    async def handle_stream_offline(self, data: dict):
        # Event-Deduplizierung
        if self._is_duplicate_event(data):
            return
            
        try:
            logger.info(f"Stream offline event received: {data}")
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(
                    Streamer.twitch_id == data["broadcaster_user_id"]
                ).first()
        
                if streamer:
                    streamer.is_live = False
                    streamer.last_updated = datetime.now(timezone.utc)
                
                    stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .order_by(Stream.started_at.desc())\
                        .first()                    
                    if stream:
                        stream.ended_at = datetime.now(timezone.utc)
                        # stream.status = "offline"  # Remove - status is not a field in the Stream model
                
                    db.commit()
            
                    # Send notification only via notification_service to avoid duplicates
                    await self.notification_service.send_stream_notification(
                        streamer_name=streamer.username,
                        event_type="offline",
                        details={
                            "streamer_id": streamer.id,
                            "url": f"https://twitch.tv/{data['broadcaster_user_login']}",
                            "profile_image_url": streamer.profile_image_url,
                            "twitch_login": data['broadcaster_user_login']
                        }
                    )

                    await self.recording_service.stop_recording(streamer.id)
            
        except Exception as e:
            logger.error(f"Error handling stream offline event: {e}", exc_info=True)
            
    async def handle_stream_update(self, data: dict):
        # Event-Deduplizierung
        if self._is_duplicate_event(data):
            return
            
        try:
            logger.debug(f"Processing stream update event: {data}")
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(
                    Streamer.twitch_id == data["broadcaster_user_id"]
                ).first()
            
                if streamer:
                    logger.debug(f"Found streamer: {streamer.username} (ID: {streamer.id})")
                    streamer.title = data.get("title")
                    streamer.category_name = data.get("category_name")
                    streamer.language = data.get("language")
                    streamer.last_updated = datetime.now(timezone.utc)
                
                    db.commit()
                    logger.debug(f"Updated streamer info in database: {streamer.title}")

                    stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .order_by(Stream.started_at.desc())\
                        .first()
                
                    if stream:
                        stream_event = StreamEvent(
                            stream_id=stream.id,
                            event_type="channel.update",
                            title=data.get("title"),
                            category_name=data.get("category_name"),
                            language=data.get("language"),
                            timestamp=datetime.now(timezone.utc)
                        )
                        db.add(stream_event)
                        db.commit()
                    else:
                        logger.info(f"Streamer {streamer.username} is offline, storing update for future use")
                
                    # Send notification only via notification_service to avoid duplicates
                    logger.debug(f"Attempting to send notification for {streamer.username}, event_type=update")
                    notification_result = await self.notification_service.send_stream_notification(
                        streamer_name=streamer.username,
                        event_type="update",
                        details={
                            "streamer_id": streamer.id,
                            "url": f"https://twitch.tv/{data['broadcaster_user_login']}",
                            "title": data.get("title"),
                            "category_name": data.get("category_name"),
                            "language": data.get("language"),
                            "profile_image_url": streamer.profile_image_url,
                            "twitch_login": data["broadcaster_user_login"],
                            "is_live": streamer.is_live
                        }
                    )
                    logger.debug(f"Notification result: {notification_result}")
                
                    logger.debug("Notifications sent successfully")
                    category_name = data.get("category_name")
                    category_id = data.get("category_id")
                    
                    if category_name and category_id:
                        from app.services.streamer_service import StreamerService
                        
                        category = db.query(Category).filter(Category.twitch_id == category_id).first()
                        
                        if not category:
                            streamer_service = StreamerService(
                                db=db, 
                                websocket_manager=self.manager,
                                event_registry=self
                            )
                            game_data = await streamer_service.get_game_data(category_id)
                            
                            category = Category(
                                twitch_id=category_id,
                                name=category_name,
                                box_art_url=game_data.get("box_art_url") if game_data else None
                            )
                            db.add(category)
                        else:
                            category.name = category_name
                            category.last_seen = datetime.now(timezone.utc)
                        
                        db.commit()

                        users_with_favorite = db.query(User).join(FavoriteCategory).filter(
                            FavoriteCategory.category_id == category.id
                        ).all()
                        
                        if users_with_favorite:
                            for user in users_with_favorite:
                                settings = db.query(NotificationSettings).filter(
                                    NotificationSettings.streamer_id == streamer.id
                                ).first()
                                
                                if settings and settings.notify_favorite_category:
                                    await self.notification_service.send_stream_notification(
                                        streamer_name=streamer.username,
                                        event_type="favorite_category",
                                        details={
                                            "url": f"https://twitch.tv/{data['broadcaster_user_login']}",
                                            "title": data.get("title"),
                                            "category_name": category_name,
                                            "language": data.get("language"),
                                            "profile_image_url": streamer.profile_image_url,
                                            "twitch_login": data['broadcaster_user_login']
                                        }
                                    )
        except Exception as e:
            logger.error(f"Error handling stream update event: {e}", exc_info=True)
                        
    async def list_subscriptions(self):
        logger.debug("Entering list_subscriptions()")
        access_token = await self.get_access_token()
        logger.debug(f"Using access_token: {access_token[:6]}... (truncated)")

        async with aiohttp.ClientSession() as session:
            url = "https://api.twitch.tv/helix/eventsub/subscriptions"
            headers = {
                "Client-ID": self.settings.TWITCH_APP_ID,
                "Authorization": f"Bearer {access_token}"
            }
            logger.debug(f"Requesting Twitch subscriptions {url} with headers={headers}")
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received subscription data: {data}")
                    return data
                else:
                    logger.error(f"Failed to list subscriptions: HTTP {response.status}")
                    return {"data": []}

    async def delete_subscription(self, subscription_id: str):
        access_token = await self.get_access_token()
        
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"https://api.twitch.tv/helix/eventsub/subscriptions?id={subscription_id}",
                headers={
                    "Client-ID": self.settings.TWITCH_APP_ID,
                    "Authorization": f"Bearer {access_token}"
                }
            ) as response:
                if response.status == 204:
                    return {
                        "id": subscription_id,
                        "status": "deleted"
                    }
                else:
                    return {
                        "id": subscription_id,
                        "status": "failed",
                        "error": f"Status code: {response.status}"
                    }

    async def delete_all_subscriptions(self):
        subs = await self.list_subscriptions()
        results = []
        
        for sub in subs.get("data", []):
            try:
                result = await self.delete_subscription(sub["id"])
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to delete subscription {sub['id']}: {e}")
                results.append({
                    "id": sub["id"],
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "success": True,
            "results": results
        }

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user info from Twitch API including profile image"""
        try:
            access_token = await self.get_access_token()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.twitch.tv/helix/users?id={user_id}",
                    headers={
                        "Client-ID": self.settings.TWITCH_APP_ID,
                        "Authorization": f"Bearer {access_token}"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["data"][0] if data.get("data") else None
            return None
        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
            return None