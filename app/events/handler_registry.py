from typing import Dict, Callable, Awaitable, Any
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from app.database import SessionLocal
from app.services.websocket_manager import ConnectionManager
from app.models import Streamer, Stream
from app.config.settings import settings
import logging
import asyncio

logger = logging.getLogger('streamvault')

class EventHandlerRegistry:
    def __init__(self, connection_manager: ConnectionManager, twitch: Twitch = None):
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {}
        self.manager = connection_manager
        self.twitch = twitch
        self.eventsub = None
        self.register_handlers()

    async def initialize_eventsub(self):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
        
        full_webhook_url = f"{settings.WEBHOOK_URL}/callback"
        logger.debug(f"Initializing EventSub with callback URL: {full_webhook_url}")
        
        self.eventsub = EventSubWebhook(
            callback_url=settings.WEBHOOK_URL,
            port=settings.EVENTSUB_PORT,
            twitch=self.twitch,
            callback_loop=asyncio.get_event_loop()
        )
        
        self.eventsub.start()
        logger.info(f"EventSub initialized successfully with URL: {full_webhook_url}")

    async def subscribe_to_events(self, twitch_id: str):
        try:
            if not self.eventsub:
                raise ValueError("EventSub not initialized")
            
            logger.debug(f"Starting subscription process for twitch_id: {twitch_id}")

            subscription_statuses = {}

            # Subscribe to stream.online
            logger.debug("Unsubscribing from all existing subscriptions")
            await self.eventsub.unsubscribe_all()
            logger.debug("Setting up stream.online subscription")
            online_sub = await self.eventsub.listen_stream_online(twitch_id, self.handle_stream_online)
            logger.info(f"Stream.online subscription created with ID: {online_sub}")
            subscription_statuses['stream.online'] = online_sub

            # Log current subscriptions
            # subs = await self.twitch.get_eventsub_subscriptions()
            # logger.debug(f"Subscriptions after stream.online: {subs.data}")

            # Subscribe to stream.offline
            # logger.debug("Setting up stream.offline subscription")
            # offline_sub = await self.eventsub.listen_stream_offline(twitch_id, self.handle_stream_offline)
            # logger.info(f"Stream.offline subscription created with ID: {offline_sub}")
            # subscription_statuses['stream.offline'] = offline_sub

            # subs = await self.twitch.get_eventsub_subscriptions()
            # logger.debug(f"Subscriptions after stream.offline: {subs.data}")

            # Subscribe to channel.update
            # logger.debug("Setting up channel.update subscription")
            # update_sub = await self.eventsub.listen_channel_update(twitch_id, self.handle_channel_update)
            # logger.info(f"Channel.update subscription created with ID: {update_sub}")
            # subscription_statuses['channel.update'] = update_sub

            subs = await self.twitch.get_eventsub_subscriptions()
            logger.debug(f"Subscriptions after channel.update: {subs.data}")

            logger.info(f"All subscriptions confirmed for twitch_id: {twitch_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to events for user {twitch_id}: {e}", exc_info=True)
            # Clean up any successful subscriptions
            for sub_id in subscription_statuses.values():
                try:
                    await self.eventsub.delete_subscription(sub_id)
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up subscription {sub_id}: {cleanup_error}")
            raise

    async def handle_stream_online(self, data: dict):
        try:
            logger.debug(f"Handling stream.online event with data: {data}")
            twitch_id = str(data.get("broadcaster_user_id"))
            streamer_name = data.get("broadcaster_user_name")

            if not twitch_id or not streamer_name:
                logger.error("Missing broadcaster data in event")
                return

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    new_stream = Stream(
                        streamer_id=streamer.id,
                        event_type='stream.online'
                    )
                    db.add(new_stream)
                    db.commit()
                    
                    await self.manager.send_notification({
                        "type": "stream.online",
                        "data": {
                            "streamer_id": twitch_id,
                            "streamer_name": streamer_name
                        }
                    })
                    logger.info(f"Handled stream online event for {streamer_name}")
                else:
                    logger.warning(f"No streamer found for twitch_id: {twitch_id}")
        except Exception as e:
            logger.error(f"Error handling stream.online event: {e}", exc_info=True)
            raise

    async def handle_stream_offline(self, data: dict) -> None:
        try:
            logger.debug(f"Handling stream.offline event with data: {data}")
            twitch_id = str(data.get("broadcaster_user_id"))

            if not twitch_id:
                logger.error("Missing broadcaster_user_id in event data")
                return

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    new_stream = Stream(
                        streamer_id=streamer.id,
                        event_type='stream.offline'
                    )
                    db.add(new_stream)
                    db.commit()
                    await self.manager.send_notification({
                        "type": "stream.offline",
                        "data": {
                            "streamer_id": twitch_id,
                            "streamer_name": streamer.username
                        }
                    })
                    logger.info(f"Handled stream offline event for {streamer.username}")
                else:
                    logger.warning(f"No streamer found for twitch_id: {twitch_id}")
        except Exception as e:
            logger.error(f"Error handling stream.offline event: {e}", exc_info=True)
            raise

    async def handle_channel_update(self, data: dict) -> None:
        try:
            logger.debug(f"Handling channel.update event with data: {data}")
            twitch_id = str(data.get("broadcaster_user_id"))

            if not twitch_id:
                logger.error("Missing broadcaster_user_id in event data")
                return

            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.twitch_id == twitch_id).first()
                if streamer:
                    await self.manager.send_notification({
                        "type": "channel.update",
                        "data": {
                            "streamer_id": twitch_id,
                            "streamer_name": streamer.username
                        }
                    })
                    logger.info(f"Handled channel update event for {streamer.username}")
                else:
                    logger.warning(f"No streamer found for twitch_id: {twitch_id}")
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

    async def setup_test_subscription(self, broadcaster_id: str):
        if not self.twitch:
            raise ValueError("Twitch client not initialized")
            
        logger.debug(f"Setting up test subscription for broadcaster ID: {broadcaster_id}")
        
        # Verify the broadcaster exists
        users = await self.twitch.get_users(user_ids=[broadcaster_id])
        if not users.data:
            logger.error(f"No Twitch user found for ID: {broadcaster_id}")
            return {
                "success": False,
                "message": f"No Twitch user found for ID: {broadcaster_id}"
            }
        
        try:
            test_sub_id = await self.eventsub.listen_stream_online(broadcaster_id, self.handle_stream_online)
            
            # Verify subscription status
            subs = await self.twitch.get_eventsub_subscriptions()
            if not any(sub.id == test_sub_id and sub.status == "enabled" for sub in subs.data):
                raise Exception("Failed to confirm test subscription")
            
            logger.info(f"Test subscription created successfully with ID: {test_sub_id}")
            
            # Commands for different event types
            test_commands = {
                "stream.online": f"twitch event trigger streamup -F {settings.WEBHOOK_URL}/callback -t {broadcaster_id} -u {test_sub_id}",
                "stream.offline": f"twitch event trigger streamdown -F {settings.WEBHOOK_URL}/callback -t {broadcaster_id} -u {test_sub_id}",
                "stream.change": f"twitch event trigger stream-change -F {settings.WEBHOOK_URL}/callback -t {broadcaster_id} -u {test_sub_id}"
            }

            return {
                "success": True,
                "subscription_id": test_sub_id,
                "test_commands": test_commands,
                "verify_command": f"twitch event verify-subscription streamup -F {settings.WEBHOOK_URL}/callback"
            }
            
        except Exception as e:
            logger.error(f"Failed to set up test subscription: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to set up test subscription: {str(e)}"
            }
