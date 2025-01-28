from typing import Dict, Callable, Awaitable, Any
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from app.database import SessionLocal
from app.services.websocket_manager import ConnectionManager
from app.models import Streamer, Stream, StreamEvent
from app.config.settings import settings
import logging
import asyncio
import hmac
import hashlib
from datetime import datetime, timezone


logger = logging.getLogger('streamvault')

class EventHandlerRegistry:
    def __init__(self, connection_manager: ConnectionManager, twitch: Twitch = None, settings=None):
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

            logger.debug(f"Starting batch subscription process for twitch_id: {twitch_id}")

            # Create all subscriptions at once
            subscriptions = await asyncio.gather(
                self.eventsub.listen_stream_online(
                    broadcaster_user_id=twitch_id,
                    callback=self.handle_stream_online
                ),
                self.eventsub.listen_stream_offline(
                    broadcaster_user_id=twitch_id,
                    callback=self.handle_stream_offline
                ),
                self.eventsub.listen_channel_update(
                    broadcaster_user_id=twitch_id,
                    callback=self.handle_stream_update
                )
            )

            # Verify all subscriptions
            for sub_id in subscriptions:
                await self.verify_subscription(sub_id)

            logger.info(f"All subscriptions created and verified for twitch_id: {twitch_id}")
            return True

        except Exception as e:
            logger.error(f"Error in batch subscription: {e}", exc_info=True)
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
            twitch_stream_id = data.get("id")
            stream_type = data.get("type")
            started_at = data.get("started_at")

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    # Check for any existing active streams and close them (safeguard)
                    existing_active = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .first()
                    if existing_active:
                        existing_active.ended_at = datetime.utcnow()

                    # Create new stream session
                    new_stream = Stream(
                        streamer_id=streamer.id,
                        twitch_stream_id=twitch_stream_id,
                        stream_type=stream_type,
                        started_at=started_at
                    )
                    db.add(new_stream)
                    db.flush()

                    stream_event = StreamEvent(
                        stream_id=new_stream.id,
                        event_type='stream.online'
                    )
                    db.add(stream_event)
                    db.commit()

                    await self.manager.send_notification({
                        "type": "stream.online",
                        "data": {
                            "streamer_id": twitch_id,
                            "streamer_name": streamer_name,
                            "stream_id": twitch_stream_id,
                            "started_at": started_at
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
                    # Find the latest active stream
                    current_stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .order_by(Stream.started_at.desc())\
                        .first()
                
                    if current_stream:
                        # Keep the stream data but mark it as ended
                        current_stream.ended_at = datetime.now(timezone.utc)
                    
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
                                "streamer_name": streamer_name,
                                "title": current_stream.title,
                                "category_name": current_stream.category_name,
                                "language": current_stream.language
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
            category_id = data.get("category_id")
            category_name = data.get("category_name")
            language = data.get("language")

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    # Record the update event regardless of stream status
                    stream_event = StreamEvent(
                        stream_id=None,  # Will be updated if there's an active stream
                        event_type='channel.update',
                        title=title,
                        category_id=category_id,
                        category_name=category_name,
                        language=language
                    )

                    # If there's an active stream, update it and link the event
                    current_stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .first()
                
                    if current_stream:

                        current_stream.title = title
                        current_stream.category_id = category_id
                        current_stream.category_name = category_name
                        current_stream.language = language
                        stream_event.stream_id = current_stream.id

                    db.add(stream_event)
                    db.commit()

                    await self.manager.send_notification({
                        "type": "channel.update",
                        "data": {
                            "streamer_id": twitch_id,
                            "streamer_name": streamer_name,
                            "title": title,
                            "category_name": category_name,
                            "language": language,
                            "is_live": current_stream is not None,
                            "last_updated": datetime.now(timezone.utc).isoformat()
                        }
                    })

        except Exception as e:
            logger.error(f"Error handling channel.update event: {e}", exc_info=True)
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

        try:
            subs = await self.twitch.get_eventsub_subscriptions()
            deletion_results = []

            for sub in subs.data:
                try:
                    await self.twitch.delete_eventsub_subscription(sub.id)
                    deletion_results.append({"id": sub.id, "status": "deleted"})
                    await self.manager.send_notification({
                        "type": "subscription.deleted",
                        "data": {
                            "subscription_id": sub.id,
                            "message": f"Subscription {sub.id} deleted successfully"
                        }
                    })
                except Exception as e:
                    logger.error(f"Failed to delete subscription {sub.id}: {e}")
                    deletion_results.append({"id": sub.id, "status": "failed", "error": str(e)})

            await self.manager.send_notification({
                "type": "subscriptions.deleted.all",
                "data": {
                    "message": "All subscriptions deleted successfully",
                    "count": len(deletion_results)
                }
            })

            return {
                "success": True,
                "message": "All subscriptions deleted successfully",
                "results": deletion_results
            }
        except Exception as e:
            logger.error(f"Error deleting all subscriptions: {e}", exc_info=True)
            raise