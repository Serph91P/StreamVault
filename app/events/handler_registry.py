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

        self.eventsub.secret = self.settings.EVENTSUB_SECRET

        self.eventsub.start()
        
        logger.info(f"EventSub initialized successfully with URL: {full_webhook_url}")
        logger.debug(f"EventSub initialized successfully with secret: {self.eventsub.secret}")

    async def subscribe_to_events(self, twitch_id: str):
        try:
            if not self.eventsub:
                raise ValueError("EventSub not initialized")

            logger.debug(f"Starting subscription process for twitch_id: {twitch_id}")

            # Stream.online subscription and verification
            online_sub = await self.eventsub.listen_stream_online(
                broadcaster_user_id=twitch_id,
                callback=self.handle_stream_online
            )
            logger.info(f"Stream.online subscription created with ID: {online_sub}")
            await self.verify_subscription(online_sub)

            # Stream.offline subscription and verification
            offline_sub = await self.eventsub.listen_stream_offline(
                broadcaster_user_id=twitch_id,
                callback=self.handle_stream_offline
            )
            logger.info(f"Stream.offline subscription created with ID: {offline_sub}")
            await self.verify_subscription(offline_sub)

            # Channel.update subscription and verification
            update_sub = await self.eventsub.listen_channel_update(
                broadcaster_user_id=twitch_id,
                callback=self.handle_stream_update
            )
            logger.info(f"Channel.update subscription created with ID: {update_sub}")
            await self.verify_subscription(update_sub)

            logger.info(f"All subscriptions confirmed for twitch_id: {twitch_id}")
            return True

        except Exception as e:
            logger.error(f"Error subscribing to Twitch EventSub: {e}", exc_info=True)
            raise

    async def verify_subscription(self, subscription_id: str, max_attempts: int = 30):
        """Verify that a subscription is enabled"""
        for attempt in range(max_attempts):
            subs = await self.twitch.get_eventsub_subscriptions()
            for sub in subs.data:
                if sub.id == subscription_id:
                    if sub.status == "enabled":
                        logger.info(f"Subscription {subscription_id} verified as enabled")
                        return True
                    elif sub.status == "webhook_callback_verification_pending":
                        await asyncio.sleep(1)
                        continue
                    else:
                        raise ValueError(f"Subscription {subscription_id} failed with status: {sub.status}")
            await asyncio.sleep(1)
        raise TimeoutError(f"Subscription {subscription_id} verification timed out")

    async def handle_stream_online(self, data: dict):
        try:
            logger.debug(f"Handling stream.online event with data: {data}")
            twitch_id = str(data.get("broadcaster_user_id"))
            streamer_name = data.get("broadcaster_user_name")
            title = data.get("title")
            category = data.get("category_name")

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    # Create new stream session
                    new_stream = Stream(
                        streamer_id=streamer.id,
                        current_title=title,
                        current_category=category
                    )
                    db.add(new_stream)
                    db.flush()  # Get the stream ID

                    # Record the online event
                    stream_event = StreamEvent(
                        stream_id=new_stream.id,
                        event_type='stream.online',
                        title=title,
                        category=category
                    )
                    db.add(stream_event)
                    db.commit()

                    await self.manager.send_notification({
                        "type": "stream.online",
                        "data": {
                            "streamer_id": twitch_id,
                            "streamer_name": streamer_name,
                            "title": title,
                            "category": category
                        }
                    })
                    logger.info(f"Handled stream online event for {streamer_name}")

        except Exception as e:
            logger.error(f"Error handling stream.online event: {e}", exc_info=True)
            raise

    async def handle_stream_offline(self, data: dict):
        try:
            logger.debug(f"Handling stream.offline event with data: {data}")
            twitch_id = str(data.get("broadcaster_user_id"))
            streamer_name = data.get("broadcaster_user_name")

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    # Find and close current stream
                    current_stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .first()
                    
                    if current_stream:
                        current_stream.ended_at = datetime.utcnow()
                    
                        # Record the offline event
                        stream_event = StreamEvent(
                            stream_id=current_stream.id,
                            event_type='stream.offline'
                        )
                        db.add(stream_event)
                        db.commit()

                        await self.manager.send_notification({
                            "type": "stream.offline",
                            "data": {
                                "streamer_id": twitch_id,
                                "streamer_name": streamer_name
                            }
                        })
                        logger.info(f"Handled stream offline event for {streamer_name}")

        except Exception as e:
            logger.error(f"Error handling stream.offline event: {e}", exc_info=True)
            raise

    async def handle_stream_update(self, data: dict):
        try:
            logger.debug(f"Handling channel.update event with data: {data}")
            twitch_id = str(data.get("broadcaster_user_id"))
            streamer_name = data.get("broadcaster_user_name")
            title = data.get("title")
            category = data.get("category_name")

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    # Get current active stream or create offline updates container
                    current_stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .first()
                    
                    if not current_stream:
                        # Create container for offline updates
                        current_stream = Stream(
                            streamer_id=streamer.id,
                            current_title=title,
                            current_category=category
                        )
                        db.add(current_stream)
                        db.flush()
                    else:
                        # Update current stream state
                        current_stream.current_title = title
                        current_stream.current_category = category

                    # Record the update event
                    stream_event = StreamEvent(
                        stream_id=current_stream.id,
                        event_type='stream.update',
                        title=title,
                        category=category
                    )
                    db.add(stream_event)
                    db.commit()

                    await self.manager.send_notification({
                        "type": "stream.update",
                        "data": {
                            "streamer_id": twitch_id,
                            "streamer_name": streamer_name,
                            "title": title,
                            "category": category
                        }
                    })
                    logger.info(f"Handled stream update event for {streamer_name}")

        except Exception as e:
            logger.error(f"Error handling stream.update event: {e}", exc_info=True)
            raise

    async def list_subscriptions(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")

        subs = await self.twitch.get_eventsub_subscriptions()
        subscriptions_data = []
    
        for sub in subs.data:
            broadcaster_id = sub.condition.get('broadcaster_user_id')
            broadcaster_name = None
        
            if broadcaster_id:
                users = []
                async for user in self.twitch.get_users(user_ids=[broadcaster_id]):
                    broadcaster_name = user.display_name
                    break

            subscriptions_data.append({
                "id": sub.id,
                "broadcaster_id": broadcaster_id,
                "broadcaster_name": broadcaster_name,
                "type": sub.type,
                "status": sub.status,
                "condition": sub.condition,
                "created_at": sub.created_at
            })
    
        return {"subscriptions": subscriptions_data}

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
