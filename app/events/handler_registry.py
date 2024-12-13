from typing import Dict, Callable, Awaitable, Any
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.twitch import Twitch
from app.database import SessionLocal
from app.services.websocket_manager import ConnectionManager
from app.models import Streamer, Stream
from app.config.settings import settings
import logging

logger = logging.getLogger('streamvault')

class EventHandlerRegistry:
    def __init__(self, connection_manager: ConnectionManager, twitch: Twitch = None):
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {}
        self.manager = connection_manager
        self.twitch = twitch
        self.event_sub = None
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
                broadcaster_user_id=user_id,
                callback=handle_stream_online
            )
            await self.event_sub.listen_stream_offline(
                broadcaster_user_id=user_id,
                callback=handle_stream_offline
            )
            await self.event_sub.listen_channel_update(
                broadcaster_user_id=user_id,
                callback=handle_channel_update
            )

            logger.info(f"Successfully subscribed to all events for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to events for user {user_id}: {e}", exc_info=True)
            raise

    async def unsubscribe_from_events(self, user_id: str):
        try:
            if not self.event_sub:
                await self.initialize_eventsub()

            # Retrieve all subscriptions
            subscriptions = await self.event_sub.get_subscriptions()
            for sub in subscriptions.data:
                if sub.condition.get("broadcaster_user_id") == user_id:
                    await self.event_sub.delete_subscription(sub.id)

            logger.info(f"Successfully unsubscribed all events for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from events for user {user_id}: {e}", exc_info=True)

    async def shutdown(self):
        if self.event_sub:
            await self.event_sub.stop()
            logger.info("EventSub shutdown complete")

    async def handle_stream_online(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                new_stream = Stream(streamer_id=streamer_id, event_type='stream.online')
                db.add(new_stream)
                db.commit()
                await self.manager.send_notification(f"{streamer.username} is now **online**!")
                logger.info(f"Handled stream online event for {streamer.username}")

    async def handle_stream_offline(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                new_stream = Stream(streamer_id=streamer_id, event_type='stream.offline')
                db.add(new_stream)
                db.commit()
                await self.manager.send_notification(f"{streamer.username} is now **offline**!")
                logger.info(f"Handled stream offline event for {streamer.username}")

    async def handle_channel_update(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                await self.manager.send_notification(f"{streamer.username} updated their channel!")
                logger.info(f"Handled channel update event for {streamer.username}")

    async def handle_channel_update_v2(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                await self.manager.send_notification(f"{streamer.username} made channel updates!")
                logger.info(f"Handled channel update v2 event for {streamer.username}")

    def register_handlers(self):
        self.handlers['stream.online'] = self.handle_stream_online
        self.handlers['stream.offline'] = self.handle_stream_offline
        self.handlers['channel.update'] = self.handle_channel_update
        self.handlers['channel.update.v2'] = self.handle_channel_update_v2
