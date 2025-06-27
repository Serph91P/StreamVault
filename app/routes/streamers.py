from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body  # Body hinzugefügt
from fastapi.responses import JSONResponse
from app.services.streamer_service import StreamerService
from app.schemas.streamers import StreamerResponse, StreamerList
from app.events.handler_registry import EventHandlerRegistry
from app.dependencies import get_streamer_service, get_event_registry
from app.database import SessionLocal, get_db
from app.models import Stream, Streamer, NotificationSettings, StreamerRecordingSettings, StreamMetadata, StreamEvent
from app.schemas.streams import StreamList, StreamResponse
from sqlalchemy.orm import Session
import logging
import asyncio
from pathlib import Path
import json
import re

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
        raise HTTPException(status_code=500, detail="Failed to delete subscriptions. Please try again.")

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
                results["errors"].append({                    "streamer": streamer.get("username", "unknown"),
                    "error": "Subscription failed"  # Don't expose detailed error info
                })
        
        logger.info(f"Resubscription complete: {results['processed']} processed, {results['skipped']} skipped")
        return {
            "success": True,
            "message": f"Resubscribed to events for {results['processed']} streamers, skipped {results['skipped']}",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to resubscribe to all events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resubscribe to events. Please try again.")

@router.post("/{username}")
async def add_streamer(
    username: str,
    settings: dict = Body(...),
    streamer_service: StreamerService = Depends(get_streamer_service),
    db: Session = Depends(get_db)
):
    """Fügt einen neuen Streamer hinzu mit benutzerdefinierten Einstellungen"""
    try:
        # Überprüfe, ob der Streamer bereits existiert
        existing_streamer = await streamer_service.get_streamer_by_username(username)
        if existing_streamer:
            return JSONResponse(
                status_code=400,
                content={"message": f"Streamer '{username}' already exists"}
            )
        
        # Streamer bei Twitch überprüfen und hinzufügen
        streamer = await streamer_service.add_streamer(username)
        
        if not streamer:
            return JSONResponse(
                status_code=404,
                content={"message": f"Streamer '{username}' not found on Twitch"}
            )
        
        # Benachrichtigungseinstellungen aktualisieren, falls vorhanden
        if "notifications" in settings:
            notification_settings = db.query(NotificationSettings).filter(
                NotificationSettings.streamer_id == streamer.id
            ).first()
            
            if not notification_settings:
                notification_settings = NotificationSettings(streamer_id=streamer.id)
                db.add(notification_settings)
            
            # Aktualisiere die Einstellungen
            notification_data = settings["notifications"]
            if "notify_online" in notification_data:
                notification_settings.notify_online = notification_data["notify_online"]
            if "notify_offline" in notification_data:
                notification_settings.notify_offline = notification_data["notify_offline"]
            if "notify_update" in notification_data:
                notification_settings.notify_update = notification_data["notify_update"]
            if "notify_favorite_category" in notification_data:
                notification_settings.notify_favorite_category = notification_data["notify_favorite_category"]
        
        # Aufnahmeeinstellungen aktualisieren, falls vorhanden
        if "recording" in settings:
            recording_settings = db.query(StreamerRecordingSettings).filter(
                StreamerRecordingSettings.streamer_id == streamer.id
            ).first()
            
            if not recording_settings:
                recording_settings = StreamerRecordingSettings(streamer_id=streamer.id)
                db.add(recording_settings)
            
            # Aktualisiere die Einstellungen
            recording_data = settings["recording"]
            if "enabled" in recording_data:
                recording_settings.enabled = recording_data["enabled"]
            if "quality" in recording_data:
                recording_settings.quality = recording_data["quality"]
            if "custom_filename" in recording_data:
                recording_settings.custom_filename = recording_data["custom_filename"]
        
        db.commit()
        
        return {
            "id": streamer.id,
            "username": streamer.username,
            "twitch_id": streamer.twitch_id,
            "profile_image_url": streamer.profile_image_url,
            "message": f"Streamer '{username}' added successfully with custom settings"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding streamer: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"message": "Failed to add streamer. Please try again."}
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
            "message": f"Failed to set up notifications for {username}. Please try again."
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
            content={"success": False, "message": "Failed to delete streamer. Please try again."}
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
        raise HTTPException(status_code=500, detail="Failed to delete subscriptions. Please try again.")

@router.get("/{streamer_id}/streams", response_model=dict)
async def get_streams_by_streamer_id(
    streamer_id: int,
    db: Session = Depends(get_db)
):
    """Get all streams for a streamer by their ID with category history"""
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
            # Get all events for this stream, ordered by timestamp
            events = db.query(StreamEvent).filter(
                StreamEvent.stream_id == stream.id
            ).order_by(
                StreamEvent.timestamp.asc()
            ).all()
            
            # Format events for the response
            formatted_events = []
            for event in events:
                formatted_events.append({
                    "id": event.id,
                    "event_type": event.event_type,
                    "title": event.title,
                    "category_name": event.category_name,
                    "language": event.language,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None
                })
            
            formatted_streams.append({
                "id": stream.id,
                "streamer_id": stream.streamer_id,
                "started_at": stream.started_at.isoformat() if stream.started_at else None,
                "ended_at": stream.ended_at.isoformat() if stream.ended_at else None,
                "title": stream.title,
                "category_name": stream.category_name,
                "language": stream.language,
                "twitch_stream_id": stream.twitch_stream_id,
                "events": formatted_events
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
        raise HTTPException(status_code=500, detail="Failed to retrieve streams. Please try again.")

@router.delete("/{streamer_id}/streams/{stream_id}")
async def delete_stream(
    streamer_id: int,
    stream_id: int,
    db: Session = Depends(get_db)
):
    """Delete a stream and all associated metadata files for a streamer"""
    try:
        # Check if the streamer exists
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer with ID {streamer_id} not found")
        
        # Check if the stream exists and belongs to the streamer
        stream = db.query(Stream).filter(
            Stream.id == stream_id, 
            Stream.streamer_id == streamer_id
        ).first()
        
        if not stream:
            raise HTTPException(status_code=404, detail=f"Stream with ID {stream_id} not found for this streamer")
        
        # Get metadata to find associated files
        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
        files_to_delete = []
        
        if metadata:
            # Collect all metadata files that need to be deleted
            for attr in [
                'thumbnail_path', 'nfo_path', 'json_path', 'chat_path', 
                'chat_srt_path', 'chapters_path', 'chapters_vtt_path', 
                'chapters_srt_path', 'chapters_ffmpeg_path'
            ]:
                path = getattr(metadata, attr, None)
                if path:
                    files_to_delete.append(path)
                    
            # Delete metadata record first (foreign key constraint)
            db.delete(metadata)
        
        # Delete all stream events
        db.query(StreamEvent).filter(StreamEvent.stream_id == stream_id).delete()
        
        # Delete the stream record itself
        db.delete(stream)
        db.commit()
        
        # Now delete all the files
        deleted_files = []
        for file_path in files_to_delete:
            try:
                path_obj = Path(file_path)
                if path_obj.exists():
                    path_obj.unlink()
                    deleted_files.append(str(path_obj))
                    
                    # Also try to delete companion files (like .vtt alongside .mp4, etc.)
                    base_path = path_obj.with_suffix('')
                    for ext in ['.vtt', '.srt', '.jpg', '.png', '.nfo', '.json', '.xml', '.txt']:
                        companion = base_path.with_suffix(ext)
                        if companion.exists() and companion != path_obj:
                            companion.unlink()
                            deleted_files.append(str(companion))
            except Exception as file_error:
                logger.warning(f"Failed to delete file {file_path}: {file_error}")
        
        return {
            "success": True, 
            "message": f"Stream {stream_id} deleted successfully",
            "deleted_files": deleted_files,
            "deleted_files_count": len(deleted_files)
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting stream {stream_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete stream. Please try again.")

@router.get("/validate/{username}")
async def validate_streamer(
    username: str,
    streamer_service: StreamerService = Depends(get_streamer_service)
):
    """Überprüft, ob ein Twitch-Benutzername gültig ist"""
    try:
        # Überprüfe, ob der Streamer bereits in der Datenbank existiert
        existing_streamer = await streamer_service.get_streamer_by_username(username)
        if existing_streamer:
            return {
                "valid": True,
                "message": "Streamer already exists in your list",
                "streamer_info": {
                    "id": existing_streamer.id,
                    "twitch_id": existing_streamer.twitch_id,
                    "username": existing_streamer.username,
                    "display_name": existing_streamer.username,
                    "profile_image_url": existing_streamer.profile_image_url,
                    "description": "This streamer is already in your list"
                }
            }
        
        # Überprüfe den Streamer bei Twitch mit der vorhandenen Methode
        user_data = await streamer_service.get_user_data(username)
        
        if not user_data:
            return {
                "valid": False,
                "message": f"Streamer '{username}' not found on Twitch"
            }
        
        # Extrahiere die relevanten Informationen aus dem Twitch-Benutzer
        streamer_info = {
            "id": None,  # Noch nicht in der Datenbank
            "twitch_id": user_data.get("id"),
            "username": user_data.get("login"),
            "display_name": user_data.get("display_name"),
            "profile_image_url": user_data.get("profile_image_url"),
            "description": user_data.get("description", "")
        }
        
        return {
            "valid": True,
            "message": "Valid Twitch username",
            "streamer_info": streamer_info
        }
    except Exception as e:
        logger.error(f"Error validating streamer: {e}", exc_info=True)
        return {
            "valid": False,
            "message": "Failed to validate streamer. Please try again."
        }

@router.get("/{streamer_id}/streams/{stream_id}/chapters")
async def get_stream_chapters(
    streamer_id: int,
    stream_id: int,
    db: Session = Depends(get_db)
):
    """Get chapter data for a specific stream"""
    try:
        # First verify the stream exists for this streamer
        stream = db.query(Stream).filter(
            Stream.id == stream_id,
            Stream.streamer_id == streamer_id
        ).first()
        
        if not stream:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        # Get metadata for the stream
        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
        
        if not metadata:
            return {"chapters": [], "message": "No metadata found for this stream"}
        
        chapters = []
        
        # Try to load chapters from WebVTT file first
        if metadata.chapters_vtt_path and Path(metadata.chapters_vtt_path).exists():
            try:
                with open(metadata.chapters_vtt_path, 'r', encoding='utf-8') as f:
                    vtt_content = f.read()
                chapters.extend(parse_webvtt_chapters(vtt_content))
                logger.debug(f"Loaded {len(chapters)} chapters from WebVTT file")
            except Exception as e:
                logger.warning(f"Failed to parse WebVTT chapters: {e}")
        
        # If no WebVTT chapters, try to load from StreamEvents (API-based chapters)
        if not chapters:
            events = db.query(StreamEvent).filter(
                StreamEvent.stream_id == stream_id,
                StreamEvent.event_type.in_(['stream.online', 'channel.update'])
            ).order_by(StreamEvent.timestamp).all()
            
            for event in events:
                try:
                    event_data = json.loads(event.event_data) if event.event_data else {}
                    title = "Stream Event"
                    
                    if event.event_type == 'stream.online':
                        title = "Stream Started"
                    elif event.event_type == 'channel.update':
                        title = event_data.get('title', 'Channel Update')
                        # Limit title length for chapters
                        if len(title) > 50:
                            title = title[:47] + "..."
                    
                    chapters.append({
                        "start_time": event.timestamp.isoformat(),
                        "title": title,
                        "type": "event"
                    })
                except Exception as e:
                    logger.warning(f"Failed to process event {event.id}: {e}")
            
            logger.debug(f"Generated {len(chapters)} chapters from events")
        
        # If still no chapters, create a basic chapter for the stream start
        if not chapters and stream.started_at:
            chapters.append({
                "start_time": stream.started_at.isoformat(),
                "title": stream.title or "Stream",
                "type": "stream"
            })
        
        # Return chapter data with metadata
        video_url = None
        if stream.recording_path:
            # Convert absolute path to relative URL for static file serving
            try:
                video_path = Path(stream.recording_path)
                if video_path.exists():
                    # Use the stream ID for direct video streaming
                    video_url = f"/api/videos/stream/{stream.id}"
                else:
                    logger.warning(f"Video file not found: {video_path}")
            except Exception as e:
                logger.warning(f"Failed to generate video URL: {e}")
        
        # Calculate duration if possible
        duration = None
        if stream.started_at and stream.ended_at:
            duration = (stream.ended_at - stream.started_at).total_seconds()
        
        return {
            "chapters": chapters,
            "stream_id": stream_id,
            "stream_title": stream.title or f"Stream {stream_id}",
            "duration": duration,
            "video_url": video_url,
            "video_file": stream.recording_path,
            "metadata": {
                "has_vtt": bool(metadata.chapters_vtt_path and Path(metadata.chapters_vtt_path).exists()),
                "has_srt": bool(metadata.chapters_srt_path and Path(metadata.chapters_srt_path).exists()),
                "has_ffmpeg": bool(metadata.chapters_ffmpeg_path and Path(metadata.chapters_ffmpeg_path).exists())
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chapters for stream {stream_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load stream chapters. Please try again.")

def parse_webvtt_chapters(vtt_content: str) -> List[Dict[str, Any]]:
    """Parse WebVTT chapter content and return chapter data"""
    chapters = []
    
    # Split into cues by looking for timestamp lines
    lines = vtt_content.split('\n')
    current_chapter = None
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines and WebVTT header
        if not line or line == 'WEBVTT':
            continue
        
        # Look for timestamp lines (format: 00:00:00.000 --> 00:00:00.000)
        timestamp_match = re.match(r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})', line)
        if timestamp_match:
            if current_chapter:
                chapters.append(current_chapter)
            
            start_time = timestamp_match.group(1)
            current_chapter = {
                "start_time": start_time,
                "title": "",
                "type": "chapter"
            }
        elif current_chapter and line and not line.startswith('NOTE'):
            # This is the chapter title
            if not current_chapter["title"]:
                current_chapter["title"] = line
            else:
                # Multi-line title
                current_chapter["title"] += " " + line
    
    # Add the last chapter
    if current_chapter:
        chapters.append(current_chapter)
    
    return chapters
