from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
import hmac
import hashlib
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.object.eventsub import ChannelFollowEvent
from twitchAPI.helper import first
import asyncio
from app.config.settings import settings
import logging

logger = logging.getLogger('streamvault')

router = APIRouter(prefix="/test", tags=["test"])

async def on_online(data: ChannelFollowEvent):
    logger.info(f'Online Event Received: {data.event.user_name}!')

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
        
        # Setup EventSub with test-specific callback URL and different port
        full_webhook_url = f"{settings.BASE_URL}/test/eventsub/test"
        test_port = settings.EVENTSUB_PORT + 1
        logger.debug(f"Initializing EventSub with test callback URL: {full_webhook_url} on port {test_port}")
        eventsub = EventSubWebhook(
            callback_url=full_webhook_url,
            port=test_port,
            twitch=twitch,
            callback_loop=asyncio.get_event_loop()
        )
        
        # Clear existing subscriptions
        logger.debug("Clearing existing EventSub subscriptions")
        await eventsub.unsubscribe_all()
        logger.info("Successfully cleared existing subscriptions")
        
        # Start EventSub
        logger.debug("Starting EventSub webhook server")
        eventsub.start()
        logger.info("EventSub webhook server started successfully")
        
        # Subscribe to stream.online events
        logger.debug(f"Setting up stream.online subscription for broadcaster ID: {broadcaster.id}")
        subscription = await eventsub.listen_stream_online(
            broadcaster_user_id=broadcaster.id,
            callback=on_online
        )
        logger.info(f"Successfully subscribed to stream.online events. Subscription ID: {subscription}")
        
        return {
            "status": "success",
            "message": f"EventSub test started for broadcaster: {broadcaster_name}",
            "broadcaster_id": broadcaster.id,
            "subscription_id": subscription,
            "callback_url": f"{full_webhook_url}/callback"
        }
        
    except Exception as e:
        logger.error(f"Error in test_eventsub: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/eventsub/test/callback")
async def handle_test_callback(request: Request):
    try:
        logger.debug("Received test callback")
        # Read the headers and body
        headers = request.headers
        body = await request.body()

        # Extract the Twitch Message Type
        message_type = headers.get("Twitch-Eventsub-Message-Type")
        logger.debug(f"Received EventSub request: type={message_type}, headers={headers}, body={body}")

        # Verify signature
        message_id = headers.get("Twitch-Eventsub-Message-Id", "")
        timestamp = headers.get("Twitch-Eventsub-Message-Timestamp", "")
        signature = headers.get("Twitch-Eventsub-Message-Signature", "")

        if not all([message_id, timestamp, signature]):
            logger.error("Missing required headers for signature verification")
            return JSONResponse(status_code=403, content={"error": "Missing required headers"})

        # Compute and verify HMAC signature
        hmac_message = message_id + timestamp + body.decode()
        expected_signature = "sha256=" + hmac.new(
            settings.WEBHOOK_SECRET.encode("utf-8"),
            hmac_message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if signature != expected_signature:
            logger.error("Invalid webhook signature")
            return JSONResponse(status_code=403, content={"error": "Invalid signature"})

        # Handle verification challenge
        if message_type == "webhook_callback_verification":
            challenge_data = await request.json()
            challenge = challenge_data.get("challenge")
            if challenge:
                logger.info("Challenge request received and processed successfully")
                return Response(content=challenge, media_type="text/plain")

        # Handle notifications
        if message_type == "notification":
            data = await request.json()
            logger.info(f"Received event notification: {data}")
            return JSONResponse(content={"success": True})

        # Handle revocation
        if message_type == "revocation":
            data = await request.json()
            logger.warning(f"Subscription revoked: {data}")
            return JSONResponse(content={"success": True})

        return Response(status_code=204)

    except Exception as e:
        logger.error(f"Error handling test callback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
