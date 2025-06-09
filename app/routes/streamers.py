from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from app.services.streamer_service import StreamerService
from app.schemas.streamers import StreamerResponse, StreamerList, AddStreamerSettingsSchema
from app.events.handler_registry import EventHandlerRegistry
from app.dependencies import get_streamer_service, get_event_registry
from app.database import SessionLocal, get_db
from app.models import Stream, Streamer, NotificationSettings, StreamerRecordingSettings, StreamMetadata, StreamEvent, RecordingSettings
from app.schemas.streams import StreamList, StreamResponse
from sqlalchemy.orm import Session, selectinload
import logging
import asyncio
from pathlib import Path
import os

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

@router.post("/{username}")
async def add_streamer(
    username: str,
    settings: AddStreamerSettingsSchema, # Changed from dict = Body(...)
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
        # Note: The original task implies streamer_service.add_streamer would handle settings.
        # However, current route code handles DB updates directly.
        # We are adapting to use the Pydantic model for reading settings.
        streamer_entity = await streamer_service.add_streamer(username) # Renamed to avoid confusion with streamer_id from models
        
        if not streamer_entity:
            return JSONResponse(
                status_code=404,
                content={"message": f"Streamer '{username}' not found on Twitch"}
            )
        
        # Benachrichtigungseinstellungen aktualisieren, falls vorhanden
        if settings.notifications:
            notification_settings_db = db.query(NotificationSettings).filter(
                NotificationSettings.streamer_id == streamer_entity.id
            ).first()
            
            if not notification_settings_db:
                notification_settings_db = NotificationSettings(streamer_id=streamer_entity.id)
                db.add(notification_settings_db)
            
            if settings.notifications.notify_online is not None:
                notification_settings_db.notify_online = settings.notifications.notify_online
            if settings.notifications.notify_offline is not None:
                notification_settings_db.notify_offline = settings.notifications.notify_offline
            # Assuming 'notify_update' corresponds to title/game change for now
            if settings.notifications.notify_title_change is not None:
                 # Assuming 'notify_update' was a general flag, let's map title change to it.
                 # If precise mapping is needed, DB model might need notify_title_change, notify_game_change fields.
                notification_settings_db.notify_update = settings.notifications.notify_title_change
            if settings.notifications.notify_game_change is not None:
                # Similar to above, if DB has a specific field, use it. For now, also mapping to notify_update
                # Or, if notify_update is a general bucket, this could be an OR condition or separate logic.
                # For simplicity, let's assume notify_update covers these.
                # If you have distinct DB fields like `notify_game_change`, use them:
                # notification_settings_db.notify_game_change = settings.notifications.notify_game_change
                pass # Placeholder if DB model doesn't have a direct match for notify_game_change
            # notify_new_vod is not in the current DB model NotificationSettings based on prior context.
            # if settings.notifications.notify_new_vod is not None:
            #    notification_settings_db.notify_new_vod = settings.notifications.notify_new_vod

        # Aufnahmeeinstellungen aktualisieren, falls vorhanden
        if settings.recording:
            recording_settings_db = db.query(StreamerRecordingSettings).filter(
                StreamerRecordingSettings.streamer_id == streamer_entity.id
            ).first()
            
            if not recording_settings_db:
                recording_settings_db = StreamerRecordingSettings(streamer_id=streamer_entity.id)
                db.add(recording_settings_db)
            
            if settings.recording.enabled is not None:
                recording_settings_db.enabled = settings.recording.enabled
            if settings.recording.quality is not None:
                recording_settings_db.quality = settings.recording.quality
            if settings.recording.custom_filename is not None:
                recording_settings_db.custom_filename = settings.recording.custom_filename
            if settings.recording.max_streams is not None:
                recording_settings_db.max_streams = settings.recording.max_streams
        
        db.commit()
        
        return {
            "id": streamer_entity.id,
            "username": streamer_entity.username,
            "twitch_id": streamer_entity.twitch_id,
            "profile_image_url": streamer_entity.profile_image_url,
            "message": f"Streamer '{username}' added successfully with custom settings"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding streamer: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"message": f"Error adding streamer: {str(e)}"}
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
    """Get all streams for a streamer by their ID with category history"""
    try:
        # Überprüfen, ob der Streamer existiert
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer with ID {streamer_id} not found")
        
        # Alle Streams für diesen Streamer abrufen, nach Startdatum absteigend sortiert
        # Eager load events using selectinload
        streams = db.query(Stream).filter(
            Stream.streamer_id == streamer_id
        ).options(
            selectinload(Stream.events)
        ).order_by(
            Stream.started_at.desc()
        ).all()
        
        # Streams in ein lesbares Format umwandeln
        formatted_streams = []
        for stream in streams:
            # Format events for the response (events are now pre-loaded with stream.events)
            formatted_events = []
            for event in stream.events: # Iterate over pre-loaded stream.events
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
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{streamer_id}/streams/{stream_id}")
async def delete_stream(
    streamer_id: int,
    stream_id: int,
    db: Session = Depends(get_db)
):
    """Delete a stream and all associated metadata files for a streamer"""
    try:
        # Get base recording directory for validation
        global_recording_settings = db.query(RecordingSettings).first()
        if not global_recording_settings or not global_recording_settings.output_directory:
            logger.error("Global recording output directory not configured. Aborting file deletion.")
            # Potentially raise HTTPException or return an error response
            # For now, we prevent deletions if this critical setting is missing.
            raise HTTPException(status_code=500, detail="Recording output directory not configured, cannot safely delete files.")

        base_recording_dir = os.path.abspath(global_recording_settings.output_directory)

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
        skipped_files = [] # Keep track of files skipped due to validation

        for file_path_str in files_to_delete: # Renamed to avoid clash with Path object
            try:
                path_obj = Path(file_path_str)
                if path_obj.exists():
                    abs_file_path = os.path.abspath(str(path_obj))
                    if abs_file_path.startswith(base_recording_dir):
                        path_obj.unlink()
                        deleted_files.append(str(path_obj))
                    else:
                        logger.warning(
                            f"Skipping deletion of file outside recording directory: {str(path_obj)}"
                        )
                        skipped_files.append(str(path_obj))
                    
                    # Also try to delete companion files (like .vtt alongside .mp4, etc.)
                    # Ensure path_obj is the original main file (e.g., .mp4) for correct suffix stripping
                    # This part of logic might need refinement if files_to_delete contains non-primary files
                    # For now, assuming path_obj refers to a primary media or metadata file.
                    base_path_for_companions = path_obj.with_suffix('')
                    for ext in ['.vtt', '.srt', '.jpg', '.png', '.nfo', '.json', '.xml', '.txt']:
                        companion = base_path_for_companions.with_suffix(ext)
                        if companion.exists() and companion != path_obj: # Avoid deleting the file itself if ext matches
                            abs_companion_path = os.path.abspath(str(companion))
                            if abs_companion_path.startswith(base_recording_dir):
                                companion.unlink()
                                deleted_files.append(str(companion))
                            else:
                                logger.warning(
                                    f"Skipping deletion of companion file outside recording directory: {str(companion)}"
                                )
                                skipped_files.append(str(companion))
            except Exception as file_error:
                logger.warning(f"Failed to process file {file_path_str} for deletion: {file_error}")
        
        response_message = f"Stream {stream_id} processed for deletion."
        if skipped_files:
            response_message += f" Some files were skipped due to path validation: {len(skipped_files)}."

        return {
            "success": True,
            "message": response_message,
            "deleted_files": deleted_files,
            "deleted_files_count": len(deleted_files),
            "skipped_files": skipped_files,
            "skipped_files_count": len(skipped_files)
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting stream {stream_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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
            "message": f"Error validating streamer: {str(e)}"
        }
