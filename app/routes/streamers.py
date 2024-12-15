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
    
    existing = await streamer_service.get_streamer_by_username(username)
    if existing:
        return JSONResponse(
            status_code=400,
            content={"message": f"Streamer {username} is already subscribed."}
        )
    
    result = await streamer_service.add_streamer(username)
    if result["success"]:
        try:
            await event_registry.subscribe_to_events(result["streamer"].id)
            return JSONResponse(
                status_code=200,
                content={"message": f"Successfully added streamer {username}"}
            )
        except Exception as e:
            logger.error(f"Failed to subscribe to events: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return JSONResponse(
        status_code=400,
        content={"message": result.get("message", "Failed to add streamer")}
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