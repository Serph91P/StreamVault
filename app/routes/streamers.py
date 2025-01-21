from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.services.streamer_service import StreamerService
from app.events.handler_registry import EventHandlerRegistry
from app.dependencies import get_streamer_service, get_event_registry
from app.config.settings import settings
import logging
import asyncio

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/streamers", tags=["streamers"])

@router.get("")
async def get_streamers(
    streamer_service: StreamerService = Depends(get_streamer_service)
):
    return await streamer_service.get_streamers()

@router.post("/{username}")
async def add_streamer(
    username: str,
    streamer_service: StreamerService = Depends(get_streamer_service),
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    # First, quickly add the streamer to database
    result = await streamer_service.add_streamer(username)
    if not result["success"]:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": result.get("message")}
        )
    
    # Commit immediately to ensure streamer is saved
    streamer_service.db.commit()
    
    # Create background task for EventSub setup
    asyncio.create_task(setup_eventsub_background(
        event_registry,
        result["twitch_id"],
        streamer_service,
        username
    ))
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": f"Streamer {username} added. Setting up notifications...",
            "streamer": {
                "id": result["streamer"].id,
                "username": result["streamer"].username
            }
        }
    )

async def setup_eventsub_background(
    event_registry: EventHandlerRegistry,
    twitch_id: str,
    streamer_service: StreamerService,
    username: str
):
    try:
        await event_registry.subscribe_to_events(twitch_id)
        await streamer_service.notify({
            "type": "success",
            "message": f"Successfully set up notifications for {username}"
        })
    except Exception as e:
        logger.error(f"Background EventSub setup failed: {e}")
        await streamer_service.notify({
            "type": "error",
            "message": f"Failed to set up notifications for {username}: {str(e)}"
        })

@router.delete("/{streamer_id}")
async def delete_streamer(
    streamer_id: int,
    streamer_service: StreamerService = Depends(get_streamer_service),
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    try:
        streamer = await streamer_service.delete_streamer(streamer_id)
        if streamer:
            # Delete all EventSub subscriptions for this streamer
            subs = await event_registry.list_subscriptions()
            for sub in subs["subscriptions"]:
                if sub["broadcaster_id"] == streamer.twitch_id:
                    await event_registry.delete_subscription(sub["id"])
            
            return {"success": True, "message": "Streamer deleted successfully"}
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Streamer not found"}
        )
    except Exception as e:
        logger.error(f"Error deleting streamer: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )

@router.get("/subscriptions")
async def get_subscriptions(
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    return await event_registry.list_subscriptions()

@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    return await event_registry.delete_subscription(subscription_id)

@router.delete("/subscriptions")
async def delete_all_subscriptions(
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    try:
        logger.debug("Attempting to delete all subscriptions")
        result = await event_registry.delete_all_subscriptions()
        return {
            "success": True,
            "message": "All subscriptions deleted successfully",
            "result": result
        }
    except Exception as e:
        logger.error(f"Failed to delete subscriptions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/test/subscription/{broadcaster_id}")
async def setup_test_subscription(
    broadcaster_id: str,
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    try:
        # Get user info from Twitch API
        users_generator = event_registry.twitch.get_users(user_ids=[broadcaster_id])
        users = []
        async for user in users_generator:
            users.append(user)
            break
        
        if not users:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Twitch user with ID {broadcaster_id} not found"
                }
            )
            
        test_sub_id = await event_registry.setup_test_subscription(users[0].id)
        
        # Commands for different event types
        test_commands = {
            "stream.online": f"twitch event trigger streamup -F {settings.WEBHOOK_URL}/callback -t {users[0].id} -u {test_sub_id}",
            "stream.offline": f"twitch event trigger streamdown -F {settings.WEBHOOK_URL}/callback -t {users[0].id} -u {test_sub_id}",
            "stream.change": f"twitch event trigger stream-change -F {settings.WEBHOOK_URL}/callback -t {users[0].id} -u {test_sub_id}"
        }

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "subscription_id": test_sub_id,
                "test_commands": test_commands,
                "verify_command": f"twitch event verify-subscription streamup -F {settings.WEBHOOK_URL}/callback"
            }
        )
    except Exception as e:
        logger.error(f"Failed to set up test subscription: {e}", exc_info=True)
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": str(e)
            }
        )
