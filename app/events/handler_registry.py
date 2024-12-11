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
    def __init__(self, connection_manager: ConnectionManager, twitch: Twitch):
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {}
        self.manager = connection_manager
        self.twitch = twitch
        self.event_sub = None

    async def initialize_eventsub(self):
        self.event_sub = EventSubWebhook(
            settings.WEBHOOK_URL,
            8080,
            self.twitch
        )
        await self.event_sub.unsubscribe_all()
        self.event_sub.start()
        logger.info("EventSub initialized successfully")

    async def subscribe_to_events(self, user_id: str):
        await self.event_sub.listen_stream_online(user_id, self.handle_stream_online)
        await self.event_sub.listen_stream_offline(user_id, self.handle_stream_offline)
        await self.event_sub.listen_channel_update(user_id)
        await self.event_sub.listen_channel_update_v2(user_id)

    async def unsubscribe_from_events(self, user_id: str):
        await self.event_sub.delete_all_subscriptions_of_type('stream.online', user_id)
        await self.event_sub.delete_all_subscriptions_of_type('stream.offline', user_id)
        await self.event_sub.delete_all_subscriptions_of_type('channel.update', user_id)
        await self.event_sub.delete_all_subscriptions_of_type('channel.update.v2', user_id)

    async def shutdown(self):
        if self.event_sub:
            await self.event_sub.stop()

    async def handle_stream_online(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                new_stream = Stream(streamer_id=streamer_id, event_type='stream.online')
                db.add(new_stream)
                db.commit()
                await self.manager.send_notification(f"{streamer.username} is now **online**!")

    async def handle_stream_offline(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                new_stream = Stream(streamer_id=streamer_id, event_type='stream.offline')
                db.add(new_stream)
                db.commit()
                await self.manager.send_notification(f"{streamer.username} is now **offline**!")

    async def handle_channel_update(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                await self.manager.send_notification(f"{streamer.username} updated their channel!")

    async def handle_channel_update_v2(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                await self.manager.send_notification(f"{streamer.username} made channel updates!")

    def register_handlers(self):
        self.handlers['stream.online'] = self.handle_stream_online
        self.handlers['stream.offline'] = self.handle_stream_offline
        self.handlers['channel.update'] = self.handle_channel_update
        self.handlers['channel.update.v2'] = self.handle_channel_update_v2        self.handlers['stream.offline'] = self.handle_stream_offline