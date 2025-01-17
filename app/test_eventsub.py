from fastapi import APIRouter, HTTPException
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.object.eventsub import ChannelFollowEvent
import asyncio
from app.config.settings import settings

router = APIRouter(prefix="/test", tags=["test"])

async def on_follow(data: ChannelFollowEvent):
    print(f'{data.event.user_name} now follows {data.event.broadcaster_user_name}!')

@router.get("/eventsub/test/{broadcaster_name}")
async def test_eventsub(broadcaster_name: str):
    try:
        # Initialize Twitch API
        twitch = Twitch(settings.TWITCH_APP_ID, settings.TWITCH_APP_SECRET)
        await twitch.authenticate_app([])
        
        # Get broadcaster info
        users = await twitch.get_users(logins=[broadcaster_name])
        if not users.data:
            raise HTTPException(status_code=404, detail="Broadcaster not found")
        broadcaster = users.data[0]
        
        # Setup EventSub with full webhook URL including /callback
        full_webhook_url = f"{settings.WEBHOOK_URL}/callback"
        eventsub = EventSubWebhook(
            callback_url=full_webhook_url,
            port=settings.EVENTSUB_PORT,
            twitch=twitch
        )
        
        # Clear existing subscriptions and start
        await eventsub.unsubscribe_all()
        eventsub.start()
        
        # Subscribe to follow events
        subscription = await eventsub.listen_channel_follow_v2(
            broadcaster_id=broadcaster.id,
            moderator_id=broadcaster.id,
            callback=on_follow
        )
        
        return {
            "status": "success",
            "message": f"EventSub test started for broadcaster: {broadcaster_name}",
            "broadcaster_id": broadcaster.id,
            "subscription_id": subscription,
            "callback_url": full_webhook_url
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/eventsub/stop")
async def stop_eventsub():
    try:
        # Initialize Twitch API using settings
        twitch = await Twitch(settings.TWITCH_APP_ID, settings.TWITCH_APP_SECRET)
        
        # Create EventSub instance
        eventsub = EventSubWebhook(
            callback_url=settings.WEBHOOK_URL,
            port=settings.EVENTSUB_PORT,
            twitch=twitch
        )
        
        # Unsubscribe from all events
        await eventsub.unsubscribe_all()
        await eventsub.stop()
        
        return {
            "status": "success",
            "message": "EventSub test stopped and all subscriptions cleared"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
