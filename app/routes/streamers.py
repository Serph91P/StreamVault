from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.services.streamer_service import StreamerService
from app.events.handler_registry import EventHandlerRegistry
from app.dependencies import get_streamer_service, get_event_registry
import logging
from app.config.settings import settings


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
    logger.debug(f"Add streamer request received for username: {username}")
    
    # Add more detailed logging here to track the flow
    logger.debug("Starting streamer addition process")
    
    # Check for existing streamer first
    existing = await streamer_service.get_streamer_by_username(username)
    logger.debug(f"Existing streamer check result: {existing}")

    if existing:
        logger.debug(f"Streamer {username} already exists")
        return JSONResponse(
            status_code=409,  # Changed from 400 to 409 for conflict
            content={"message": f"Streamer {username} is already subscribed."}
        )
    
    try:
        # Add logging before streamer addition attempt
        logger.debug(f"Attempting to add streamer {username}")
        
        # Attempt to add the streamer
        result = await streamer_service.add_streamer(username)
        logger.debug(f"Add streamer result: {result}")
        
        if result["success"]:
            try:
                logger.debug(f"Setting up EventSub for streamer ID: {result['streamer'].id}")
                await event_registry.subscribe_to_events(str(result['streamer'].id))
                
                return JSONResponse(
                    status_code=201,  # Changed to 201 for resource creation
                    content={
                        "success": True,
                        "message": f"Successfully added streamer {username}",
                        "streamer": {
                            "id": result['streamer'].id,
                            "username": result['streamer'].username
                        }
                    }
                )
            except Exception as sub_error:
                # Add more detailed error logging
                logger.error(f"EventSub setup failed with error type {type(sub_error)}")
                logger.error(f"EventSub setup failed: {sub_error}", exc_info=True)
                return JSONResponse(
                    status_code=500,  # Changed from 400 to 500 for server error
                    content={
                        "success": False,
                        "message": f"Failed to set up notifications: {str(sub_error)}"
                    }
                )
        else:
            logger.error(f"Failed to add streamer: {result.get('message')}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": result.get("message", "Failed to add streamer")
                }
            )
            
    except Exception as e:
        logger.error(f"Unexpected error adding streamer: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Internal server error: {str(e)}"
            }
        )
    
@router.delete("/{streamer_id}")
async def delete_streamer(
    streamer_id: int,
    streamer_service: StreamerService = Depends(get_streamer_service),
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    if await streamer_service.delete_streamer(streamer_id):
        await event_registry.unsubscribe_from_events(str(streamer_id))
        return {"message": "Streamer deleted successfully"}
    raise HTTPException(status_code=404, detail="Streamer not found")

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
        users = await event_registry.twitch.get_users(user_ids=[broadcaster_id])
        if not users.data:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Twitch user with ID {broadcaster_id} not found"
                }
            )
        
        user = users.data[0]
        test_sub_id = await event_registry.setup_test_subscription(user.id)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "subscription_id": test_sub_id,
                "test_command": f"twitch event trigger stream.online -F {settings.WEBHOOK_URL}/callback -t {user.id} -u {test_sub_id} -s {settings.WEBHOOK_SECRET}"
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