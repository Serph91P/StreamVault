from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.services.streamer_service import StreamerService
from app.schemas.streamers import StreamerResponse, StreamerList
from app.events.handler_registry import EventHandlerRegistry
from app.dependencies import get_streamer_service, get_event_registry
from app.database import SessionLocal, get_db
from app.models import Stream, Streamer
from app.schemas.streams import StreamList, StreamResponse
from sqlalchemy.orm import Session
import logging
import asyncio

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/streamers", tags=["streamers"])

@router.get("", response_model=List[StreamerResponse])
async def get_streamers(streamer_service = Depends(get_streamer_service)):
    return await streamer_service.get_streamers()

@router.delete("/subscriptions", status_code=200)
async def delete_all_subscriptions(event_registry: EventHandlerRegistry = Depends(get_event_registry)):
    """Delete all EventSub subscriptions"""
    try:
        logger.debug("Attempting to delete all subscriptions")
        
        # Get all existing subscriptions
        existing_subs = await event_registry.list_subscriptions()
        logger.debug(f"Found {len(existing_subs.get('data', []))} subscriptions to delete")
        
        # Delete each subscription
        results = []
        for sub in existing_subs.get('data', []):
            try:
                result = await event_registry.delete_subscription(sub['id'])
                logger.info(f"Deleted subscription {sub['id']}")
                results.append(result)
            except Exception as sub_error:
                logger.error(f"Failed to delete subscription {sub['id']}: {sub_error}", exc_info=True)
                results.append({
                    "id": sub['id'],
                    "status": "failed",
                    "error": str(sub_error)
                })
        
        # Summary of results
        return {
            "success": True,
            "deleted_subscriptions": results,
            "total_deleted": len([res for res in results if res.get("status") == "deleted"]),
            "total_failed": len([res for res in results if res.get("status") == "failed"]),
        }

    except Exception as e:
        logger.error(f"Error deleting all subscriptions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resubscribe-all", status_code=200)
async def resubscribe_all(
    event_registry: EventHandlerRegistry = Depends(get_event_registry),
    streamer_service: StreamerService = Depends(get_streamer_service)
):
    """Resubscribe to all events for all streamers, skipping existing subscriptions."""
    try:
        logger.debug("Starting resubscription for all streamers")
        
        # Get all streamers
        streamers = await streamer_service.get_streamers()
        
        # Get existing subscriptions
        existing_subs = await event_registry.list_subscriptions()
        existing_twitch_ids = set()
        
        for sub in existing_subs.get("data", []):
            if "condition" in sub and "broadcaster_user_id" in sub["condition"]:
                existing_twitch_ids.add(sub["condition"]["broadcaster_user_id"])
        
        # Track results
        results = {
            "total": len(streamers),
            "processed": 0,
            "skipped": 0,
            "errors": []
        }
        
        # Process each streamer
        for streamer in streamers:
            try:
                twitch_id = streamer["twitch_id"]
                
                # Check if all event types already exist for this streamer
                if twitch_id in existing_twitch_ids:
                    logger.debug(f"Skipping {streamer['username']} - already has subscriptions")
                    results["skipped"] += 1
                    continue
                
                # Subscribe to events
                logger.debug(f"Resubscribing to events for {streamer['username']}")
                await event_registry.subscribe_to_events(twitch_id)
                results["processed"] += 1
                
            except Exception as e:
                logger.error(f"Error resubscribing for {streamer.get('username', 'unknown')}: {e}")
                results["errors"].append({
                    "streamer": streamer.get("username", "unknown"),
                    "error": str(e)
                })
        
        logger.info(f"Resubscription complete: {results['processed']} processed, {results['skipped']} skipped")
        return {
            "success": True,
            "message": f"Resubscribed to events for {results['processed']} streamers, skipped {results['skipped']}",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to resubscribe to all events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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

@router.get("/{streamer_id}/streams", response_model=dict)
async def get_streams_by_streamer_id(
    streamer_id: int,
    db: Session = Depends(get_db)
):
    """Get all streams for a streamer by their ID"""
    try:
        # Überprüfen, ob der Streamer existiert
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer with ID {streamer_id} not found")
        
        # Alle Streams für diesen Streamer abrufen, nach Startdatum absteigend sortiert
        streams = db.query(Stream).filter(
            Stream.streamer_id == streamer_id
        ).order_by(
            Stream.started_at.desc()
        ).all()
        
        # Streams in ein lesbares Format umwandeln
        formatted_streams = []
        for stream in streams:
            formatted_streams.append({
                "id": stream.id,
                "streamer_id": stream.streamer_id,
                "started_at": stream.started_at.isoformat() if stream.started_at else None,
                "ended_at": stream.ended_at.isoformat() if stream.ended_at else None,
                "title": stream.title,
                "category_name": stream.category_name,
                "language": stream.language,
                "twitch_stream_id": stream.twitch_stream_id
            })
        
        return {
            "streamer": {
                "id": streamer.id,
                "username": streamer.username,
                "profile_image_url": streamer.profile_image_url
            },
            "streams": formatted_streams
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving streams for streamer {streamer_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))