from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.services.streamer_service import StreamerService
from app.schemas.streamers import StreamerResponse, StreamerList
from app.events.handler_registry import EventHandlerRegistry
from app.dependencies import get_streamer_service, get_event_registry
import logging
import asyncio

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/streamers", tags=["streamers"])

@router.get("", response_model=List[StreamerResponse])
async def get_streamers(streamer_service = Depends(get_streamer_service)):
    return await streamer_service.get_streamers()

@router.post("/{username}", response_model=StreamerResponse)
async def add_streamer(
    username: str,
    streamer_service: StreamerService = Depends(get_streamer_service)
):
    try:
        streamer = await streamer_service.add_streamer(username)
        if not streamer:
            raise HTTPException(
                status_code=400,
                detail="Failed to add streamer"
            )
        
        # Convert Streamer model to StreamerResponse
        return StreamerResponse(
            id=streamer.id,
            twitch_id=streamer.twitch_id,
            username=streamer.username,
            is_live=streamer.is_live,
            title=streamer.title,
            category_name=streamer.category_name,
            language=streamer.language,
            last_updated=streamer.last_updated,
            profile_image_url=streamer.profile_image_url
        )
    except Exception as e:
        logger.error(f"Error adding streamer: {e}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
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
        # First get the streamer to have access to twitch_id
        streamer = await streamer_service.delete_streamer(streamer_id)
        if streamer:
            # Delete all EventSub subscriptions for this streamer
            subs = await event_registry.list_subscriptions()
            if "data" in subs:
                for sub in subs["data"]:
                    if sub["condition"]["broadcaster_user_id"] == streamer["twitch_id"]:
                        await event_registry.delete_subscription(sub["id"])
            
            return {"success": True, "message": "Streamer and subscriptions deleted successfully"}
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

@router.get("/streamer/{streamer_id}")
async def get_streamer(streamer_id: str, streamer_service: StreamerService = Depends(get_streamer_service)):
    streamer_info = await streamer_service.get_streamer_info(streamer_id)
    if not streamer_info:
        raise HTTPException(status_code=404, detail="Streamer not found")
    return streamer_info

@router.get("/subscriptions")
async def get_subscriptions(
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    logger.debug("Fetching all subscriptions")
    subscriptions = await event_registry.list_subscriptions()
    logger.debug(f"Subscriptions fetched: {subscriptions}")
    return {"subscriptions": subscriptions.get("data", [])}

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
        return result
    except Exception as e:
        logger.error(f"Failed to delete subscriptions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
