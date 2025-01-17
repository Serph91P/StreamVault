from fastapi import APIRouter, HTTPException
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.object.eventsub import ChannelFollowEvent
import asyncio
from app.config.settings import settings
import logging

logger = logging.getLogger('streamvault')

router = APIRouter(prefix="/test", tags=["test"])

async def on_follow(data: ChannelFollowEvent):
    logger.info(f'Follow Event Received: {data.event.user_name} now follows {data.event.broadcaster_user_name}!')

@router.get("/eventsub/test/{broadcaster_name}")
async def test_eventsub(broadcaster_name: str):
    try:
        logger.info(f"Starting EventSub test for broadcaster: {broadcaster_name}")
        
        # Initialize Twitch API
        logger.debug("Initializing Twitch API client")
        twitch = Twitch(settings.TWITCH_APP_ID, settings.TWITCH_APP_SECRET)
        await twitch.authenticate_app([])
        logger.info("Twitch API client authenticated successfully")
        
        # Get broadcaster info using first helper
        logger.debug(f"Fetching user info for broadcaster: {broadcaster_name}")
        broadcaster = await first(twitch.get_users(logins=[broadcaster_name]))
        if not broadcaster:
            logger.error(f"Broadcaster not found: {broadcaster_name}")
            raise HTTPException(status_code=404, detail="Broadcaster not found")
        logger.info(f"Found broadcaster: {broadcaster.display_name} (ID: {broadcaster.id})")
        
        # Setup EventSub
        full_webhook_url = f"{settings.WEBHOOK_URL}/callback"
        logger.debug(f"Initializing EventSub with callback URL: {full_webhook_url}")
        eventsub = EventSubWebhook(
            callback_url=full_webhook_url,
            port=settings.EVENTSUB_PORT,
            twitch=twitch
        )
        
        # Clear existing subscriptions
        logger.debug("Clearing existing EventSub subscriptions")
        await eventsub.unsubscribe_all()
        logger.info("Successfully cleared existing subscriptions")
        
        # Start EventSub
        logger.debug("Starting EventSub webhook server")
        eventsub.start()
        logger.info("EventSub webhook server started successfully")
        
        # Subscribe to follow events
        logger.debug(f"Setting up follow event subscription for broadcaster ID: {broadcaster.id}")
        subscription = await eventsub.listen_channel_follow_v2(
            broadcaster_id=broadcaster.id,
            moderator_id=broadcaster.id,
            callback=on_follow
        )
        logger.info(f"Successfully subscribed to follow events. Subscription ID: {subscription}")
        
        return {
            "status": "success",
            "message": f"EventSub test started for broadcaster: {broadcaster_name}",
            "broadcaster_id": broadcaster.id,
            "subscription_id": subscription,
            "callback_url": full_webhook_url
        }
        
    except Exception as e:
        logger.error(f"Error in test_eventsub: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/eventsub/stop")
async def stop_eventsub():
    try:
        logger.info("Starting EventSub shutdown process")
        
        # Initialize Twitch API
        logger.debug("Initializing Twitch API client for shutdown")
        twitch = Twitch(settings.TWITCH_APP_ID, settings.TWITCH_APP_SECRET)
        await twitch.authenticate_app([])
        logger.info("Twitch API client authenticated for shutdown")
        
        # Create EventSub instance
        logger.debug("Creating EventSub instance for cleanup")
        eventsub = EventSubWebhook(
            callback_url=f"{settings.WEBHOOK_URL}/callback",
            port=settings.EVENTSUB_PORT,
            twitch=twitch
        )
        
        # Cleanup subscriptions
        logger.debug("Unsubscribing from all EventSub subscriptions")
        await eventsub.unsubscribe_all()
        logger.info("Successfully unsubscribed from all events")
        
        logger.debug("Stopping EventSub webhook server")
        await eventsub.stop()
        logger.info("EventSub webhook server stopped successfully")
        
        return {
            "status": "success",
            "message": "EventSub test stopped and all subscriptions cleared"
        }
        
    except Exception as e:
        logger.error(f"Error in stop_eventsub: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
