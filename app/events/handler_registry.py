import logging
import aiohttp
import asyncio
from typing import Dict, Callable, Awaitable, Any
from app.database import SessionLocal
from app.services.websocket_manager import ConnectionManager
from app.models import Streamer, Stream, StreamEvent
from app.config.settings import settings
from datetime import datetime, timezone

logger = logging.getLogger('streamvault')

class EventHandlerRegistry:
    def __init__(self, connection_manager: ConnectionManager, twitch: Any = None, settings=None):
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {
            "stream.online": self.handle_stream_online,
            "stream.offline": self.handle_stream_offline,
            "channel.update": self.handle_stream_update
        }
        self.manager = connection_manager
        self.twitch = twitch
        self.eventsub = None
        self.settings = settings

    async def initialize_eventsub(self):
        if self.eventsub:
            logger.debug("EventSub already initialized, skipping...")
            return
            
        if not self.twitch:
            raise ValueError("Twitch client not initialized")

        base_url = self.settings.WEBHOOK_URL if self.settings else settings.WEBHOOK_URL
        callback_url = f"{base_url}/eventsub"
        logger.debug(f"Initializing EventSub with callback URL: {callback_url}")
        logger.debug(f"EventSub server will listen on port: {self.settings.EVENTSUB_PORT}")

        self.eventsub = {
            "callback_url": callback_url,
            "port": self.settings.EVENTSUB_PORT,
            "secret": self.settings.EVENTSUB_SECRET
        }

        logger.info(f"EventSub webhook server started successfully on port {self.settings.EVENTSUB_PORT}")

    async def verify_subscription(self, subscription_id: str, max_attempts: int = 10) -> bool:
        for attempt in range(max_attempts):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"https://api.twitch.tv/helix/eventsub/subscriptions?id={subscription_id}", headers={
                        "Client-ID": self.settings.TWITCH_APP_ID,
                        "Authorization": f"Bearer {self.settings.TWITCH_APP_SECRET}"
                    }) as response:
                        if response.status == 200:
                            subs = await response.json()
                            for sub in subs.get("data", []):
                                if sub["id"] == subscription_id and sub["status"] == "enabled":
                                    return True
                        await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error checking subscription {subscription_id}: {e}")
                await asyncio.sleep(1)
        return False
    
    async def subscribe_to_events(self, twitch_id: str):
        try:
            if not self.eventsub:
                raise ValueError("EventSub not initialized")

            logger.debug(f"Starting batch subscription process for twitch_id: {twitch_id}")

            async with aiohttp.ClientSession() as session:
                for event_type in self.handlers.keys():
                    async with session.post("https://api.twitch.tv/helix/eventsub/subscriptions", json={
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
                    }, headers={
                        "Client-ID": self.settings.TWITCH_APP_ID,
                        "Authorization": f"Bearer {self.settings.TWITCH_APP_SECRET}",
                        "Content-Type": "application/json"
                    }) as response:
                        if response.status == 202:
                            logger.info(f"Subscribed to {event_type} for twitch_id: {twitch_id}")
                        else:
                            logger.error(f"Failed to subscribe to {event_type} for twitch_id: {twitch_id}. Status: {response.status}")
        except Exception as e:
            logger.error(f"Error in batch subscription: {e}", exc_info=True)
            raise

    async def handle_stream_online(self, data: dict):
        try:
            logger.info(f"Stream online: {data}")
            # Handle stream online event
        except Exception as e:
            logger.error(f"Error handling stream online event: {e}", exc_info=True)

    async def handle_stream_offline(self, data: dict):
        try:
            logger.info(f"Stream offline: {data}")
            # Handle stream offline event
        except Exception as e:
            logger.error(f"Error handling stream offline event: {e}", exc_info=True)

    async def handle_stream_update(self, data: dict):
        try:
            logger.info(f"Stream update: {data}")
            # Handle stream update event
        except Exception as e:
            logger.error(f"Error handling stream update event: {e}", exc_info=True)
        
    async def list_subscriptions(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")

        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.twitch.tv/helix/eventsub/subscriptions", headers={
                "Client-ID": self.settings.TWITCH_APP_ID,
                "Authorization": f"Bearer {self.settings.TWITCH_APP_SECRET}"
            }) as response:
                if response.status == 200:
                    subs = await response.json()
                    subscriptions_data = []
                    for sub in subs.get("data", []):
                        subscriptions_data.append(sub)
                    return {"subscriptions": subscriptions_data}
                else:
                    logger.error(f"Failed to list subscriptions. Status: {response.status}")
                    return {"subscriptions": []}

    async def delete_subscription(self, subscription_id: str):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")

        async with aiohttp.ClientSession() as session:
            async with session.delete(f"https://api.twitch.tv/helix/eventsub/subscriptions?id={subscription_id}", headers={
                "Client-ID": self.settings.TWITCH_APP_ID,
                "Authorization": f"Bearer {self.settings.TWITCH_APP_SECRET}"
            }) as response:
                if response.status == 204:
                    logger.info(f"Deleted subscription {subscription_id}")
                    return {"message": f"Subscription {subscription_id} deleted successfully"}
                else:
                    logger.error(f"Failed to delete subscription {subscription_id}. Status: {response.status}")
                    return {"message": f"Failed to delete subscription {subscription_id}"}

    async def delete_all_subscriptions(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.twitch.tv/helix/eventsub/subscriptions", headers={
                    "Client-ID": self.settings.TWITCH_APP_ID,
                    "Authorization": f"Bearer {self.settings.TWITCH_APP_SECRET}"
                }) as response:
                    if response.status == 200:
                        subs = await response.json()
                        for sub in subs.get("data", []):
                            await self.delete_subscription(sub["id"])
                    else:
                        logger.error(f"Failed to list subscriptions for deletion. Status: {response.status}")
        except Exception as e:
            logger.error(f"Error deleting all subscriptions: {e}", exc_info=True)
            raise