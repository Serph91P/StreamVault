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
        if self.eventsub:
            logger.debug("EventSub already initialized, skipping...")
            return
            
        if not self.twitch:
            raise ValueError("Twitch client not initialized")

        full_webhook_url = f"{settings.WEBHOOK_URL}"
        logger.debug(f"Initializing EventSub with callback URL: {full_webhook_url}")
        logger.debug(f"EventSub server will listen on port: {self.settings.EVENTSUB_PORT}")

        self.eventsub = EventSubWebhook(
            callback_url=full_webhook_url,
            port=self.settings.EVENTSUB_PORT,
            twitch=self.twitch,
            callback_loop=asyncio.get_event_loop()
        )

        self.eventsub.secret = self.settings.EVENTSUB_SECRET
        self.eventsub.wait_for_subscription_confirm = True
        self.eventsub.wait_for_subscription_confirm_timeout = 60

        try:
            self.eventsub.start()
            logger.info(f"EventSub webhook server started successfully on port {self.settings.EVENTSUB_PORT}")
        except Exception as e:
            logger.error(f"Failed to start EventSub webhook server: {e}")
            raise

    async def verify_subscription(self, subscription_id: str, max_attempts: int = 10) -> bool:
        for attempt in range(max_attempts):
            try:
                subs = await self.twitch.get_eventsub_subscriptions()
                for sub in subs.data:
                    if sub.id == subscription_id and sub.status == "enabled":
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
            
            async def create_sub(sub_type: str) -> str:
                try:
                    if sub_type == "stream.online":
                        return await self.eventsub.listen_stream_online(
                            broadcaster_user_id=twitch_id,
                            callback=self.handle_stream_online
                        )
                    elif sub_type == "stream.offline":
                        return await self.eventsub.listen_stream_offline(
                            broadcaster_user_id=twitch_id,
                            callback=self.handle_stream_offline
                        )
                    elif sub_type == "channel.update":
                        return await self.eventsub.listen_channel_update(
                            broadcaster_user_id=twitch_id,
                            callback=self.handle_stream_update
                        )
                except Exception as e:
                    logger.error(f"Failed to create {sub_type} subscription: {e}")
                    raise

            # Create all subscriptions in parallel
            sub_types = ["stream.online", "stream.offline", "channel.update"]
            sub_ids = await asyncio.gather(*[create_sub(st) for st in sub_types])
            
            # Verify all subscriptions
            verifications = await asyncio.gather(*[
                self.verify_subscription(sub_id) for sub_id in sub_ids if sub_id
            ])

            return [sid for sid, verified in zip(sub_ids, verifications) if verified]

        except Exception as e:
            logger.error(f"Error in batch subscription: {e}", exc_info=True)
            raise

    async def handle_stream_online(self, data: dict):
        try:
            logger.debug(f"Handling stream.online event with data: {data}")
            twitch_id = str(data.get("broadcaster_user_id"))
            streamer_name = data.get("broadcaster_user_name")
            title = data.get("title")
            category_name = data.get("category_name")
            language = data.get("language")

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    # Create new stream session
                    new_stream = Stream(
                        streamer_id=streamer.id,
                        title=title,
                        category_name=category_name,
                        language=language
                    )
                    db.add(new_stream)
                    db.flush()

                    # Record the online event
                    stream_event = StreamEvent(
                        stream_id=new_stream.id,
                        event_type='stream.online',
                        title=title,
                        category_name=category_name,
                        language=language
                    )
                    db.add(stream_event)
                    db.commit()

                    await self.manager.send_notification({
                        "type": "stream.online",
                        "data": {
                            "streamer_id": twitch_id,
                            "streamer_name": streamer_name,
                            "title": title,
                            "category_name": category_name,
                            "language": language
                        }
                    })

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
                    current_stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .first()

                    if current_stream:
                        current_stream.ended_at = datetime.utcnow()
                    
                        stream_event = StreamEvent(
                            stream_id=current_stream.id,
                            event_type='stream.offline',
                            title=current_stream.title,
                            category_name=current_stream.category_name,
                            language=current_stream.language
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

        except Exception as e:
            logger.error(f"Error handling stream.offline event: {e}", exc_info=True)
            raise

    async def handle_stream_update(self, data: dict):
        try:
            logger.debug(f"Handling channel.update event with data: {data}")
            twitch_id = str(data.get("broadcaster_user_id"))
            streamer_name = data.get("broadcaster_user_name")
            title = data.get("title")
            category_name = data.get("category_name")
            language = data.get("language")

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    # Get or create stream record
                    current_stream = db.query(Stream)\
                        .filter(Stream.streamer_id == streamer.id)\
                        .filter(Stream.ended_at.is_(None))\
                        .first()

                    if not current_stream:
                        # Create new stream record for updates
                        current_stream = Stream(
                            streamer_id=streamer.id,
                            title=title,
                            category_name=category_name,
                            language=language
                        )
                        db.add(current_stream)
                    else:
                        # Update existing stream
                        current_stream.title = title
                        current_stream.category_name = category_name
                        current_stream.language = language
                        # Don't change is_live status here

                    db.commit()

                    await self.manager.send_notification({
                        "type": "channel.update",
                        "data": {
                            "streamer_id": twitch_id,
                            "streamer_name": streamer_name,
                            "title": title,
                            "category_name": category_name,
                            "language": language,
                            "is_live": current_stream.is_live  # Ensure is_live status is not changed
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