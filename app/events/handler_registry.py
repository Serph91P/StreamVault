from typing import Dict, Callable, Awaitable, Any
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
        self.register_handlers()

    async def initialize_eventsub(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
        logger.info("EventSub initialized successfully")

    async def subscribe_to_events(self, user_id: str):
        try:
            if not self.twitch:
                raise ValueError("Twitch client not initialized")

            logger.debug(f"Subscribing to events for user_id: {user_id}")
            
            # Create subscriptions using Twitch API directly
            for event_type in ['stream.online', 'stream.offline', 'channel.update']:
                await self.twitch.create_eventsub_subscription(
                    type=event_type,
                    version='1',
                    condition={'broadcaster_user_id': str(user_id)},
                    transport={
                        'method': 'webhook',
                        'callback': f"{settings.WEBHOOK_URL}/callback",
                        'secret': settings.WEBHOOK_SECRET
                    }
                )
                logger.info(f"Successfully subscribed to {event_type} for user_id: {user_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to events for user {user_id}: {e}", exc_info=True)
            raise

    async def handle_stream_online(self, data: dict):
        try:
            logger.debug(f"Handling stream.online event with data: {data}")
            streamer_id = data.get("broadcaster_user_id")
            streamer_name = data.get("broadcaster_user_name")

            if not streamer_id or not streamer_name:
                logger.error("Missing broadcaster data in event")
                return

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if streamer:
                    new_stream = Stream(streamer_id=streamer_id, event_type='stream.online')
                    db.add(new_stream)
                    db.commit()
                    
                    await self.manager.send_notification({
                        "type": "stream.online",
                        "data": {
                            "streamer_id": streamer_id,
                            "streamer_name": streamer_name
                        }
                    })
                    logger.info(f"Handled stream online event for {streamer_name}")
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

    def register_handlers(self):
        self.handlers['stream.online'] = self.handle_stream_online
        self.handlers['stream.offline'] = self.handle_stream_offline
        self.handlers['channel.update'] = self.handle_channel_update

    async def list_subscriptions(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
        
        subs = await self.twitch.get_eventsub_subscriptions()
        return {
            "subscriptions": [
                {
                    "id": sub.id,
                    "type": sub.type,
                    "status": sub.status,
                    "condition": sub.condition,
                    "created_at": sub.created_at
                } for sub in subs.data
            ]
        }

    async def delete_subscription(self, subscription_id: str):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
        
        await self.twitch.delete_eventsub_subscription(subscription_id)
        return {"message": f"Subscription {subscription_id} deleted successfully"}

    async def delete_all_subscriptions(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
        
        deleted_count = 0
        subs = await self.twitch.get_eventsub_subscriptions()
        for sub in subs.data:
            await self.twitch.delete_eventsub_subscription(sub.id)
            deleted_count += 1
        
        return {"message": f"Deleted {deleted_count} subscriptions"}
