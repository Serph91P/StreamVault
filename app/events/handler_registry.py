import logging
import aiohttp
import asyncio
from typing import Dict, Callable, Awaitable, Any
from app.database import SessionLocal
from app.services.websocket_manager import ConnectionManager
from app.services.notification_service import NotificationService
from app.models import Streamer, Stream, StreamEvent
from app.config.settings import settings as app_settings
from datetime import datetime, timezone

logger = logging.getLogger('streamvault')

class EventHandlerRegistry:
    def __init__(self, connection_manager: ConnectionManager, settings=None):
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {
            "stream.online": self.handle_stream_online,
            "stream.offline": self.handle_stream_offline,
            "channel.update": self.handle_stream_update
        }
        self.manager = connection_manager
        self.settings = settings or app_settings
        self.notification_service = NotificationService()
        self._access_token = None
        self.eventsub = None

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
    async def handle_stream_online(self, data: dict):
        try:
            logger.info(f"Stream online event received: {data}")
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(
                    Streamer.twitch_id == data["broadcaster_user_id"]
                ).first()
                
                if streamer:
                    stream = Stream(
                        streamer_id=streamer.id,
                        started_at=datetime.fromisoformat(data["started_at"].replace('Z', '+00:00')),
                        status="live"
                    )
                    db.add(stream)
                    db.commit()
                    
                    # Send WebSocket notification
                    await self.manager.send_notification({
                        "type": "stream.online",
                        "data": {
                            "streamer_id": streamer.id,
                            "twitch_id": data["broadcaster_user_id"],
                            "started_at": data["started_at"]
                        }
                    })
                    
                    # Send Apprise notification
                    await self.notification_service.send_stream_notification(
                        streamer_name=data["broadcaster_user_name"],
                        event_type="online",
                        details={"started_at": data["started_at"]}
                    )
        except Exception as e:
            logger.error(f"Error handling stream online event: {e}", exc_info=True)

    async def handle_stream_offline(self, data: dict):
        try:
            logger.info(f"Stream offline event received: {data}")
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(
                    Streamer.twitch_id == data["broadcaster_user_id"]
                ).first()
                
                if streamer:
                    stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .order_by(Stream.started_at.desc())\
                        .first()
                    
                    if stream:
                        stream.ended_at = datetime.now(timezone.utc)
                        stream.status = "offline"
                        db.commit()
                    
                    # Send WebSocket notification
                    await self.manager.send_notification({
                        "type": "stream.offline",
                        "data": {
                            "streamer_id": streamer.id,
                            "twitch_id": data["broadcaster_user_id"]
                        }
                    })
                    
                    # Send Apprise notification
                    await self.notification_service.send_stream_notification(
                        streamer_name=data["broadcaster_user_name"],
                        event_type="offline",
                        details={}
                    )
        except Exception as e:
            logger.error(f"Error handling stream offline event: {e}", exc_info=True)
    async def handle_stream_update(self, data: dict):
        try:
            logger.info(f"Stream update event received: {data}")
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(
                    Streamer.twitch_id == data["broadcaster_user_id"]
                ).first()
                
                if streamer:
                    stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .order_by(Stream.started_at.desc())\
                        .first()
                    
                    if stream:
                        event = StreamEvent(
                            stream_id=stream.id,
                            event_type="channel.update",
                            title=data.get("title"),
                            category_name=data.get("category_name"),
                            language=data.get("language"),
                            timestamp=datetime.now(timezone.utc)
                        )
                        db.add(event)
                        db.commit()
                        
                        # Send WebSocket notification
                        logger.debug("Sending WebSocket notification")
                        await self.manager.send_notification({
                            "type": "channel.update",
                            "data": {
                                "streamer_id": streamer.id,
                                "twitch_id": data["broadcaster_user_id"],
                                "title": data.get("title"),
                                "category_name": data.get("category_name")
                            }
                        })
                        
                        # Send Apprise notification
                        await self.notification_service.send_stream_notification(
                            streamer_name=data["broadcaster_user_name"],
                            event_type="update",
                            details={
                                "title": data.get("title"),
                                "category_name": data.get("category_name")
                            }
                        )
                        
                        logger.debug("Notifications sent successfully")
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