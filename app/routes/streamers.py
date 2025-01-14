from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.services.streamer_service import StreamerService
from app.events.handler_registry import EventHandlerRegistry
from app.dependencies import get_streamer_service, get_event_registry
import logging

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
    
    # Check for existing streamer first
    existing = await streamer_service.get_streamer_by_username(username)
    if existing:
        logger.debug(f"Streamer {username} already exists")
        return JSONResponse(
            status_code=400,
            content={"message": f"Streamer {username} is already added"}
        )
    
    try:
        # Attempt to add the streamer
        result = await streamer_service.add_streamer(username)
        logger.debug(f"Add streamer result: {result}")
        
        if result["success"]:
            # Set up EventSub subscriptions
            try:
                logger.debug(f"Setting up EventSub for streamer ID: {result['streamer'].id}")
                await event_registry.subscribe_to_events(str(result['streamer'].id))
                
                return JSONResponse(
                    status_code=200,
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
                # If EventSub setup fails, we should still return success but log the error
                logger.error(f"EventSub setup failed: {sub_error}", exc_info=True)
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": f"Added streamer {username} but failed to set up notifications",
                        "streamer": {
                            "id": result['streamer'].id,
                            "username": result['streamer'].username
                        }
                    }
                )
        else:
            # Handle failed streamer addition
            logger.debug(f"Failed to add streamer: {result.get('message')}")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": result.get("message", "Failed to add streamer")
                }
            )
            
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error adding streamer: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error while adding streamer"
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
        return await event_registry.delete_all_subscriptions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))