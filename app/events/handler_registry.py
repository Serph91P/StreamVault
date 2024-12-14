from typing import Dict, Callable, Awaitable, Any
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.twitch import Twitch
from app.database import SessionLocal
from app.services.websocket_manager import ConnectionManager
from app.models import Streamer, Stream
from app.config.settings import settings
import asyncio
import logging

logger = logging.getLogger('streamvault')

class EventHandlerRegistry:
    def __init__(self, connection_manager: ConnectionManager, twitch: Twitch = None):
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {}
        self.manager = connection_manager
        self.twitch = twitch
        self.event_sub = None
        logger.debug(f"EventHandlerRegistry initialized with methods: {[method for method in dir(self) if not method.startswith('_')]}")
        self.register_handlers()

    async def initialize_eventsub(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
            
        self.event_sub = EventSubWebhook(
            settings.WEBHOOK_URL,
            8080,
            self.twitch
        )
        await self.event_sub.unsubscribe_all()
        self.event_sub.start()
        logger.info("EventSub initialized successfully")

    async def subscribe_to_events(self, user_id: str):
        try:
            if not self.event_sub:
                await self.initialize_eventsub()

            # Check existing subscriptions
            subscriptions = await self.twitch.get_eventsub_subscriptions()
            logger.info(f"Current subscriptions: {subscriptions}")
        
            # Continue with subscription logic...
            logger.debug(f"Subscribing to events for user_id: {user_id}")

            async def handle_stream_online(event):
                logger.info(f"Stream online event received: {event}")
                await self.handle_stream_online(event)

            async def handle_stream_offline(event):
                logger.info(f"Stream offline event received: {event}")
                await self.handle_stream_offline(event)

            async def handle_channel_update(event):
                logger.info(f"Channel update event received: {event}")
                await self.handle_channel_update(event)

            await self.event_sub.listen_stream_online(
                broadcaster_user_id=str(user_id),
                callback=handle_stream_online
            )
    
            await self.event_sub.listen_stream_offline(
                broadcaster_user_id=str(user_id),
                callback=handle_stream_offline
            )
    
            await self.event_sub.listen_channel_update(
                broadcaster_user_id=str(user_id),
                callback=handle_channel_update
            )

            logger.info(f"All subscriptions set up successfully for user_id: {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to check/create subscriptions for user {user_id}: {e}", exc_info=True)
            raise
    async def unsubscribe_from_events(self, user_id: str):
        try:
            if not self.event_sub:
                await self.initialize_eventsub()

            logger.debug(f"Fetching subscriptions for user ID: {user_id}")
            subscriptions = await self.event_sub.get_subscriptions()

            deleted_count = 0
            for sub in subscriptions.data:
                if sub.condition.get("broadcaster_user_id") == user_id:
                    await self.event_sub.delete_subscription(sub.id)
                    deleted_count += 1

            logger.info(f"Deleted {deleted_count} subscriptions for user ID: {user_id}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from events for user {user_id}: {e}", exc_info=True)

    async def shutdown(self):
        if self.event_sub:
            await self.event_sub.stop()
            logger.info("EventSub shutdown complete")

    async def handle_stream_online(self, data: dict):
        try:
            logger.debug(f"Handling stream.online event with data: {data}")

            streamer_id = data.get("broadcaster_user_id")
            streamer_name = data.get("broadcaster_user_name")

            if not streamer_id or not streamer_name:
                logger.error("Missing broadcaster_user_id or broadcaster_user_name in event data")
                return

            logger.info(f"Streamer {streamer_name} (ID: {streamer_id}) is now online.")
            await self.manager.send_notification({
                "type": "stream.online",
                "data": {
                    "streamer_id": streamer_id,
                    "streamer_name": streamer_name
                }
            })
        except Exception as e:
            logger.error(f"Error handling stream.online event: {e}", exc_info=True)
            raise


    async def handle_stream_offline(self, data: dict) -> None:
        try:
            logger.debug(f"Handling stream.offline event with data: {data}")

            streamer_id = data.get("broadcaster_user_id")

            if not streamer_id:
                logger.error("Missing broadcaster_user_id in event data")
                return

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if streamer:
                    new_stream = Stream(streamer_id=streamer_id, event_type='stream.offline')
                    db.add(new_stream)
                    db.commit()
                    await self.manager.send_notification({
                        "type": "stream.offline",
                        "data": {
                            "streamer_id": streamer_id,
                            "streamer_name": streamer.username
                        }
                    })
                    logger.info(f"Handled stream offline event for {streamer.username}")
        except Exception as e:
            logger.error(f"Error handling stream.offline event: {e}", exc_info=True)
            raise


    async def handle_channel_update(self, data: dict) -> None:
        try:
            logger.debug(f"Handling channel.update event with data: {data}")

            streamer_id = data.get("broadcaster_user_id")

            if not streamer_id:
                logger.error("Missing broadcaster_user_id in event data")
                return

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if streamer:
                    await self.manager.send_notification({
                        "type": "channel.update",
                        "data": {
                            "streamer_id": streamer_id,
                            "streamer_name": streamer.username
                        }
                    })
                    logger.info(f"Handled channel update event for {streamer.username}")
        except Exception as e:
            logger.error(f"Error handling channel.update event: {e}", exc_info=True)
            raise


    async def handle_channel_update_v2(self, data: dict) -> None:
        try:
            logger.debug(f"Handling channel.update.v2 event with data: {data}")

            streamer_id = data.get("broadcaster_user_id")

            if not streamer_id:
                logger.error("Missing broadcaster_user_id in event data")
                return

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if streamer:
                    await self.manager.send_notification({
                        "type": "channel.update.v2",
                        "data": {
                            "streamer_id": streamer_id,
                            "streamer_name": streamer.username
                        }
                    })
                    logger.info(f"Handled channel update v2 event for {streamer.username}")
        except Exception as e:
            logger.error(f"Error handling channel.update.v2 event: {e}", exc_info=True)
            raise

    def register_handlers(self):
        self.handlers['stream.online'] = self.handle_stream_online
        self.handlers['stream.offline'] = self.handle_stream_offline
        self.handlers['channel.update'] = self.handle_channel_update
        self.handlers['channel.update.v2'] = self.handle_channel_update_v2

    async def list_subscriptions(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
        logger.debug("Attempting to list subscriptions")
        subscriptions = []
    
        # Get the subscriptions first
        subs = await self.twitch.get_eventsub_subscriptions()
    
        # Then process them
        for sub in subs:
            subscriptions.append({
                "id": sub.id,
                "type": sub.type,
                "status": sub.status,
                "condition": sub.condition,
                "created_at": sub.created_at
            })
        return {"subscriptions": subscriptions}

    async def delete_subscription(self, subscription_id: str):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
        
        await self.twitch.delete_eventsub_subscription(subscription_id)
        return {"message": f"Subscription {subscription_id} deleted successfully"}

    async def delete_all_subscriptions(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
        
        deleted_count = 0
        async for sub in self.twitch.get_eventsub_subscriptions():
            await self.twitch.delete_eventsub_subscription(sub.id)
            deleted_count += 1
        
        return {"message": f"Deleted {deleted_count} subscriptions"}