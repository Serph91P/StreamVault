from typing import Dict, Callable, Awaitable, Any
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from app.database import SessionLocal
from app.services.websocket_manager import ConnectionManager
from app.models import Streamer, Stream
from app.config.settings import settings
import logging
import asyncio
import hmac
import hashlib

logger = logging.getLogger('streamvault')

class EventHandlerRegistry:
    def __init__(self, connection_manager: ConnectionManager, twitch: Twitch = None, settings=None):
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {}
        self.manager = connection_manager
        self.twitch = twitch
        self.eventsub = None
        self.settings = settings
        # self.register_handlers()

    async def initialize_eventsub(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")

        full_webhook_url = f"{settings.WEBHOOK_URL}"
        logger.debug(f"Initializing EventSub with callback URL: {full_webhook_url}")

        self.eventsub = EventSubWebhook(
            callback_url=full_webhook_url,
            port=self.settings.EVENTSUB_PORT,
            twitch=self.twitch,
            callback_loop=asyncio.get_event_loop()
        )

        eventsub.secret = self.settings.EVENTSUB_SECRET

        self.eventsub.start()
        logger.info(f"EventSub initialized successfully with URL: {full_webhook_url}")

    async def subscribe_to_events(self, twitch_id: str):
        try:
            if not self.eventsub:
                raise ValueError("EventSub not initialized")

            logger.debug(f"Starting subscription process for twitch_id: {twitch_id}")

            # Check existing subscriptions
            existing_subs = await self.twitch.get_eventsub_subscriptions()
            logger.debug(f"Existing subscriptions: {existing_subs}")

            # Subscribe to stream.online event
            logger.debug("Setting up stream.online subscription")
            online_sub = await self.eventsub.listen_stream_online(
                broadcaster_user_id=twitch_id,
                callback=self.handle_stream_online
            )
            logger.info(f"Stream.online subscription created with ID: {online_sub}")

            logger.info(f"All subscriptions confirmed for twitch_id: {twitch_id}")
            return True

        except Exception as e:
            logger.error(f"Error subscribing to Twitch EventSub: {e}", exc_info=True)
            if hasattr(e, 'response') and e.response:
                logger.error(f"Twitch API response: {e.response.text}")
            raise

    async def handle_stream_online(self, data: dict):
        logger.info(f"Stream online event received: {data}")


    # async def handle_stream_online(self, data: dict):
    #     try:
    #         logger.debug(f"Handling stream.online event with data: {data}")
    #         twitch_id = str(data.get("broadcaster_user_id"))
    #         streamer_name = data.get("broadcaster_user_name")

    #         if not twitch_id or not streamer_name:
    #             logger.error("Missing broadcaster data in event")
    #             return

    #         with SessionLocal() as db:
    #             streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
    #             if streamer:
    #                 new_stream = Stream(
    #                     streamer_id=streamer.id,
    #                     event_type='stream.online'
    #                 )
    #                 db.add(new_stream)
    #                 db.commit()

    #                 await self.manager.send_notification({
    #                     "type": "stream.online",
    #                     "data": {
    #                         "streamer_id": twitch_id,
    #                         "streamer_name": streamer_name
    #                     }
    #                 })
    #                 logger.info(f"Handled stream online event for {streamer_name}")
    #             else:
    #                 logger.warning(f"No streamer found for twitch_id: {twitch_id}")
    #     except Exception as e:
    #         logger.error(f"Error handling stream.online event: {e}", exc_info=True)
    #         raise

    # def register_handlers(self):
    #     self.handlers['stream.online'] = self.handle_stream_online

    async def list_subscriptions(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")

        subs = await self.twitch.get_eventsub_subscriptions()
        logger.debug(f"Listing current subscriptions: {subs}")
        return {
            "subscriptions": [
                {
                    "id": sub.id,
                    "broadcaster_id": sub.condition.get('broadcaster_user_id'),
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

        subs = await self.twitch.get_eventsub_subscriptions()
        deletion_results = []

        for sub in subs.data:
            try:
                await self.twitch.delete_eventsub_subscription(sub.id)
                deletion_results.append({"id": sub.id, "status": "deleted"})
            except Exception as e:
                logger.error(f"Failed to delete subscription {sub.id}: {e}")
                deletion_results.append({"id": sub.id, "status": "failed", "error": str(e)})

        return {
            "message": "Subscription deletion complete",
            "results": deletion_results
        }
