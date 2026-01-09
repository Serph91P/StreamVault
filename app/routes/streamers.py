from typing import List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from app.services.streamer_service import StreamerService
from app.services.unified_image_service import unified_image_service
from app.services.communication.websocket_manager import websocket_manager
from app.events.handler_registry import EventHandlerRegistry
from app.dependencies import get_streamer_service, get_event_registry
from app.database import get_db
from app.models import (
    Stream,
    Streamer,
    StreamerRecordingSettings,
    StreamMetadata,
    StreamEvent,
    Recording,
    ActiveRecordingState,
)
from sqlalchemy.orm import Session, joinedload
import logging
import os
from pathlib import Path
import json
import re
from datetime import datetime, timezone
from app.utils import async_file

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/streamers", tags=["streamers"])


async def delete_files_async(files_to_delete: list) -> tuple[list, int]:
    """Delete files asynchronously and return deleted files list and count."""
    deleted_files = []
    for file_path in files_to_delete:
        try:
            path_obj = Path(file_path)
            if await async_file.path_exists(path_obj):
                await async_file.path_unlink(path_obj)
                deleted_files.append(str(path_obj))
                logger.info(f"Deleted file: {path_obj}")

                # Also try to delete companion files (like .vtt alongside .mp4, etc.)
                base_path = path_obj.with_suffix("")

                # Extended list of all possible metadata file extensions
                companion_extensions = [
                    ".vtt",
                    ".srt",
                    ".jpg",
                    ".png",
                    ".nfo",
                    ".json",
                    ".xml",
                    ".txt",
                    ".info.json",  # Specific for streamlink metadata
                ]

                for ext in companion_extensions:
                    companion = base_path.with_suffix(ext)
                    if await async_file.path_exists(companion) and companion != path_obj:
                        await async_file.path_unlink(companion)
                        deleted_files.append(str(companion))
                        logger.info(f"Deleted companion file: {companion}")

                # Also check for files with specific suffixes (like -ffmpeg-chapters.txt)
                companion_suffixes = [
                    "-thumb.jpg",
                    "-ffmpeg-chapters.txt",
                    "-chapters.txt",
                    "-chapters.vtt",
                    "-chapters.srt",
                    "_thumbnail.jpg",
                ]

                for suffix in companion_suffixes:
                    companion = Path(str(base_path) + suffix)
                    if await async_file.path_exists(companion):
                        await async_file.path_unlink(companion)
                        deleted_files.append(str(companion))
                        logger.info(f"Deleted companion file: {companion}")

                # Also try to delete thumbnail files with different naming patterns
                parent_dir = path_obj.parent
                base_filename = path_obj.stem

                # Check for thumbnail files with different naming patterns
                thumbnail_patterns = [
                    f"{base_filename}-thumb.jpg",
                    f"{base_filename}_thumbnail.jpg",
                ]

                for pattern in thumbnail_patterns:
                    thumbnail_path = parent_dir / pattern
                    if await async_file.path_exists(thumbnail_path):
                        await async_file.path_unlink(thumbnail_path)
                        deleted_files.append(str(thumbnail_path))
                        logger.info(f"Deleted thumbnail file: {thumbnail_path}")

                # Also check for streamer-specific thumbnail files
                # Try to extract streamer name from filename if possible
                try:
                    # Most files follow the pattern: "streamer - date - title.ext"
                    if " - " in base_filename:
                        streamer_name = base_filename.split(" - ")[0]
                        streamer_thumbnail = parent_dir / f"{streamer_name}_thumbnail.jpg"
                        if await async_file.path_exists(streamer_thumbnail):
                            await async_file.path_unlink(streamer_thumbnail)
                            deleted_files.append(str(streamer_thumbnail))
                            logger.info(f"Deleted streamer thumbnail file: {streamer_thumbnail}")
                except Exception as e:
                    logger.debug(f"Could not extract streamer name from filename {base_filename}: {e}")
            else:
                logger.warning(f"File not found: {file_path}")
        except Exception as file_error:
            logger.warning(f"Failed to delete file {file_path}: {file_error}")

    return deleted_files, len(deleted_files)


@router.get("")
async def get_streamers(streamer_service: StreamerService = Depends(get_streamer_service)):
    """Get all streamers with their current status

    Returns a dictionary with 'streamers' key for frontend compatibility.
    """
    streamers = await streamer_service.get_streamers()

    # Convert StreamerResponse objects to dictionaries for the response
    streamers_data = []
    for streamer in streamers:
        streamers_data.append(
            {
                "id": streamer.id,
                "twitch_id": streamer.twitch_id,
                "username": streamer.username,
                "display_name": streamer.username,  # Fallback to username if no display_name
                "is_live": streamer.is_live,
                "is_recording": streamer.is_recording,
                "recording_enabled": streamer.recording_enabled,
                "active_stream_id": streamer.active_stream_id,
                "title": streamer.title if streamer.is_live else None,  # Only show title when live
                "category_name": streamer.category_name if streamer.is_live else None,  # Only show game when live
                "language": streamer.language,
                "last_updated": streamer.last_updated.isoformat() if streamer.last_updated else None,
                "profile_image_url": unified_image_service.get_profile_image_url(
                    streamer.id, streamer.profile_image_url
                ),
                "original_profile_image_url": streamer.original_profile_image_url,
                # Last stream info (shown when offline)
                "last_stream_title": streamer.last_stream_title if not streamer.is_live else None,
                "last_stream_category_name": streamer.last_stream_category_name if not streamer.is_live else None,
                "last_stream_viewer_count": streamer.last_stream_viewer_count if not streamer.is_live else None,
                "last_stream_ended_at": (
                    streamer.last_stream_ended_at.isoformat()
                    if streamer.last_stream_ended_at and not streamer.is_live
                    else None
                ),
            }
        )

    # Return in the format expected by frontend
    return {"streamers": streamers_data}


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
        for sub in existing_subs.get("data", []):
            try:
                await event_registry.delete_subscription(sub["id"])
                logger.info(f"Deleted subscription {sub['id']}")
                results.append({"id": sub["id"], "status": "deleted"})
            except Exception as sub_error:
                logger.error(f"Failed to delete subscription {sub['id']}: {sub_error}", exc_info=True)
                results.append(
                    {
                        "id": sub["id"],  # FIXED: closed the string literal properly
                        "status": "failed",
                        "error": str(sub_error),
                    }
                )

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


@router.post("/resubscribe-all")
async def resubscribe_all(
    event_registry: EventHandlerRegistry = Depends(get_event_registry),
    streamer_service: StreamerService = Depends(get_streamer_service),
):
    """Resubscribe to all streamers' EventSub events"""
    try:
        # Get all streamers
        streamers = await streamer_service.get_streamers()

        # List current subscriptions
        current_subs = await event_registry.list_subscriptions()
        existing_user_ids = set()

        if current_subs and "data" in current_subs:
            for sub in current_subs["data"]:
                if sub.get("status") == "enabled" and "condition" in sub:
                    user_id = sub["condition"].get("broadcaster_user_id")
                    if user_id:
                        existing_user_ids.add(user_id)

        results = []
        for streamer in streamers:
            twitch_id = streamer.twitch_id

            # Skip if already subscribed
            if twitch_id in existing_user_ids:
                logger.debug(f"Skipping {streamer.username} - already has subscriptions")
                continue

            try:
                logger.debug(f"Resubscribing to events for {streamer.username}")
                await event_registry.subscribe_to_events(twitch_id)
                results.append({"streamer": streamer.username, "status": "success", "twitch_id": twitch_id})
            except Exception as e:
                logger.error(f"Failed to resubscribe for {streamer.username}: {e}")
                results.append({"streamer": streamer.username, "status": "failed", "error": str(e)})

        return {
            "success": True,
            "message": f"Resubscribed to {len(results)} streamer(s)",  # NEW: Frontend expects message field
            "results": results,
            "total_processed": len(results),
        }

    except Exception as e:
        logger.error(f"Error in resubscribe_all: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug-live-status")
async def debug_live_status(streamer_service: StreamerService = Depends(get_streamer_service)):
    """Debug endpoint to check live status of all streamers in database"""
    try:
        streamers = await streamer_service.get_all_streamers()
        debug_info = []

        for streamer in streamers:
            debug_info.append(
                {
                    "id": streamer.id,
                    "username": streamer.username,
                    "twitch_id": streamer.twitch_id,
                    "is_live": streamer.is_live,
                    "title": streamer.title,
                    "category_name": streamer.category_name,
                    "language": streamer.language,
                    "last_updated": streamer.last_updated.isoformat() if streamer.last_updated else None,
                    "active_stream_id": streamer.active_stream_id,
                }
            )

        return {"streamers": debug_info}
    except Exception as e:
        logger.error(f"Error in debug_live_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{streamer_id}/live-status")
async def check_streamer_live_status(
    streamer_id: int, db: Session = Depends(get_db), streamer_service: StreamerService = Depends(get_streamer_service)
):
    """Check if a specific streamer is currently live via Twitch API"""
    try:
        # Get streamer from database (exclude test data)
        streamer = (
            db.query(Streamer)
            .filter(Streamer.id == streamer_id, (Streamer.is_test_data.is_(False)) | (Streamer.is_test_data.is_(None)))
            .first()
        )
        if not streamer:
            raise HTTPException(status_code=404, detail="Streamer not found")

        # Check live status via Twitch API
        is_live = await streamer_service.check_streamer_live_status(streamer.twitch_id)

        # Send live status feedback via WebSocket
        await websocket_manager.send_live_status_feedback(streamer_name=streamer.username, is_live=is_live)

        return {
            "streamer_id": streamer_id,
            "username": streamer.username,
            "twitch_id": streamer.twitch_id,
            "is_live": is_live,
            "database_is_live": streamer.is_live,  # What the database thinks
            "last_updated": streamer.last_updated.isoformat() if streamer.last_updated else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking live status for streamer {streamer_id}: {e}", exc_info=True)

        # Send error toast notification
        try:
            await websocket_manager.send_toast_notification(
                toast_type="error", title="Live Status Check Failed", message=f"Failed to check live status: {str(e)}"
            )
        except Exception as notification_error:
            logger.error(f"Failed to send error notification: {notification_error}")

        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{username}")
async def add_streamer(
    username: str,
    data: Dict[str, Any] = Body(...),
    streamer_service: StreamerService = Depends(get_streamer_service),
    db: Session = Depends(get_db),
):
    """Add a new streamer with optional recording settings"""
    try:
        # Use the username from the path parameter
        username = username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")

        # Clean the username (remove @ if present)
        username = username.lstrip("@")

        # Add streamer
        new_streamer = await streamer_service.add_streamer(username)

        if not new_streamer:
            raise HTTPException(status_code=400, detail="Failed to add streamer")

        # Process recording settings if provided
        recording_enabled = True  # Default value
        if "recording" in data and isinstance(data["recording"], dict):
            recording_settings = data["recording"]
            recording_enabled = recording_settings.get("enabled", True)

            # Create or update streamer recording settings
            streamer_recording_settings = (
                db.query(StreamerRecordingSettings)
                .filter(StreamerRecordingSettings.streamer_id == new_streamer.id)
                .first()
            )

            if not streamer_recording_settings:
                streamer_recording_settings = StreamerRecordingSettings(streamer_id=new_streamer.id)
                db.add(streamer_recording_settings)

            # Update recording settings
            streamer_recording_settings.enabled = recording_enabled
            if "quality" in recording_settings and recording_settings["quality"]:
                streamer_recording_settings.quality = recording_settings["quality"]
            if "custom_filename" in recording_settings and recording_settings["custom_filename"]:
                streamer_recording_settings.custom_filename = recording_settings["custom_filename"]

            db.commit()
            logger.info(f"Set recording settings for streamer {new_streamer.username}: enabled={recording_enabled}")

        # Convert to response format
        return {
            "id": new_streamer.id,
            "username": new_streamer.username,
            "twitch_id": new_streamer.twitch_id,
            "profile_image_url": unified_image_service.get_profile_image_url(
                new_streamer.id, new_streamer.profile_image_url
            ),
            "is_live": new_streamer.is_live,
            "is_recording": False,
            "recording_enabled": recording_enabled,
            "active_stream_id": None,
            "title": new_streamer.title,
            "category_name": new_streamer.category_name,
            "language": new_streamer.language,
            "last_updated": new_streamer.last_updated.isoformat() if new_streamer.last_updated else None,
            "original_profile_image_url": new_streamer.original_profile_image_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding streamer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{streamer_id}")
async def delete_streamer(
    streamer_id: int,
    delete_recordings: bool = False,
    streamer_service: StreamerService = Depends(get_streamer_service),
    event_registry: EventHandlerRegistry = Depends(get_event_registry),
    db: Session = Depends(get_db),
):
    """
    Delete a streamer

    Args:
        streamer_id: ID of the streamer to delete
        delete_recordings: If True, also delete all recording files. If False, only delete database entries.
    """
    try:
        # Get streamer info before deletion
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail="Streamer not found")

        twitch_id = streamer.twitch_id
        streamer_username = streamer.username

        # If user wants to delete recordings too, collect and delete files first
        deleted_files_count = 0
        if delete_recordings:
            try:
                # Get all streams for this streamer
                streams = db.query(Stream).filter(Stream.streamer_id == streamer_id).all()

                files_to_delete = []
                for stream in streams:
                    if stream.recording_path:
                        recording_path = Path(stream.recording_path)

                        # Main recording file (.ts or .mp4)
                        if recording_path.exists():
                            files_to_delete.append(recording_path)

                        # Companion files (.nfo, -thumb.jpg, etc.)
                        if recording_path.exists():
                            parent_dir = recording_path.parent
                            stem = recording_path.stem

                            # NFO metadata file
                            nfo_path = parent_dir / f"{stem}.nfo"
                            if nfo_path.exists():
                                files_to_delete.append(nfo_path)

                            # Thumbnail
                            thumb_path = parent_dir / f"{stem}-thumb.jpg"
                            if thumb_path.exists():
                                files_to_delete.append(thumb_path)

                # Delete all collected files
                deleted_files, deleted_count = await delete_files_async(files_to_delete)
                deleted_files_count = deleted_count
                logger.info(f"Deleted {deleted_count} recording files for streamer {streamer_username}")

            except Exception as e:
                logger.error(f"Error deleting recording files for streamer {streamer_id}: {e}", exc_info=True)
                # Continue with deletion even if file deletion fails

        # Delete EventSub subscriptions
        try:
            subscriptions = await event_registry.list_subscriptions()
            if subscriptions and "data" in subscriptions:
                for sub in subscriptions["data"]:
                    if sub.get("condition", {}).get("broadcaster_user_id") == twitch_id:
                        await event_registry.delete_subscription(sub["id"])
                        logger.info(f"Deleted subscription {sub['id']} for streamer {twitch_id}")
        except Exception as e:
            logger.error(f"Error deleting subscriptions for streamer: {e}")

        # Delete streamer from database (this cascades to streams, recordings, etc.)
        deleted = await streamer_service.delete_streamer(streamer_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Streamer not found")

        # Build response message
        message = f"Streamer '{streamer_username}' deleted successfully"
        if delete_recordings and deleted_files_count > 0:
            message += f" ({deleted_files_count} recording files deleted)"
        elif delete_recordings:
            message += " (no recording files found)"
        else:
            message += " (recording files kept)"

        return {"success": True, "message": message, "deleted_files": deleted_files_count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting streamer: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"success": False, "message": "Failed to delete streamer. Please try again."}
        )


@router.get("/streamer/{streamer_id}")
async def get_streamer(
    streamer_id: str, streamer_service: StreamerService = Depends(get_streamer_service), db: Session = Depends(get_db)
):
    """Get detailed information about a specific streamer"""
    # Get streamer from database first (exclude test data)
    streamer = (
        db.query(Streamer)
        .filter(Streamer.id == int(streamer_id), (Streamer.is_test_data.is_(False)) | (Streamer.is_test_data.is_(None)))
        .first()
    )
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")

    # Get cached profile image URL
    profile_image_url = unified_image_service.get_profile_image_url(streamer.id, streamer.profile_image_url)

    # Get actual recording settings (not deprecated auto_record column)
    recording_settings = (
        db.query(StreamerRecordingSettings).filter(StreamerRecordingSettings.streamer_id == streamer.id).first()
    )

    # Return normalized format for frontend
    return {
        "id": streamer.id,
        "twitch_id": streamer.twitch_id,
        "name": streamer.username,  # Frontend expects 'name'
        "username": streamer.username,
        "display_name": streamer.username,  # Fallback to username
        "is_live": streamer.is_live,
        "is_recording": streamer.is_recording,  # FIXED: Use property that queries Recording table
        # FIXED: Use StreamerRecordingSettings, not auto_record
        "recording_enabled": recording_settings.enabled if recording_settings else True,
        "recording_quality": recording_settings.quality if recording_settings else None,
        "custom_filename": recording_settings.custom_filename if recording_settings else None,
        "title": streamer.title if streamer.is_live else None,
        "category_name": streamer.category_name if streamer.is_live else None,
        "profile_image_url": profile_image_url,
        "original_profile_image_url": streamer.profile_image_url,
        "description": None,  # TODO: Store description in DB if needed
        "last_updated": streamer.last_updated.isoformat() if streamer.last_updated else None,
    }


@router.put("/streamer/{streamer_id}/settings")
async def update_streamer_settings(
    streamer_id: int, settings: Dict[str, Any] = Body(...), db: Session = Depends(get_db)
):
    """Update recording settings for a specific streamer"""
    try:
        # Verify streamer exists
        streamer = (
            db.query(Streamer)
            .filter(Streamer.id == streamer_id, (Streamer.is_test_data.is_(False)) | (Streamer.is_test_data.is_(None)))
            .first()
        )
        if not streamer:
            raise HTTPException(status_code=404, detail="Streamer not found")

        # Get or create StreamerRecordingSettings
        recording_settings = (
            db.query(StreamerRecordingSettings).filter(StreamerRecordingSettings.streamer_id == streamer_id).first()
        )

        if not recording_settings:
            recording_settings = StreamerRecordingSettings(streamer_id=streamer_id, enabled=True, quality="best")
            db.add(recording_settings)

        # Update settings from request body
        if "autoRecord" in settings:
            recording_settings.enabled = settings["autoRecord"]
            logger.info(f"Updated recording enabled for {streamer.username}: {recording_settings.enabled}")

        if "quality" in settings and settings["quality"]:
            recording_settings.quality = settings["quality"]
            logger.info(f"Updated recording quality for {streamer.username}: {recording_settings.quality}")

        if "filenameTemplate" in settings:
            recording_settings.custom_filename = settings["filenameTemplate"] if settings["filenameTemplate"] else None
            logger.info(f"Updated custom filename for {streamer.username}: {recording_settings.custom_filename}")

        db.commit()
        db.refresh(recording_settings)

        # Return updated settings
        return {
            "success": True,
            "settings": {
                "autoRecord": recording_settings.enabled,
                "quality": recording_settings.quality,
                "filenameTemplate": recording_settings.custom_filename,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating streamer settings: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.get("/subscriptions")
async def list_subscriptions(event_registry: EventHandlerRegistry = Depends(get_event_registry)):
    """List all EventSub subscriptions"""
    try:
        subscriptions = await event_registry.list_subscriptions()

        # Transform the data for better readability
        if subscriptions and "data" in subscriptions:
            formatted_subs = []
            for sub in subscriptions["data"]:
                formatted_subs.append(
                    {
                        "id": sub["id"],
                        "type": sub["type"],
                        "status": sub["status"],
                        "created_at": sub.get("created_at", ""),
                        "condition": sub.get("condition", {}),
                    }
                )

            return {"total": subscriptions.get("total", 0), "subscriptions": formatted_subs}

        return {"total": 0, "subscriptions": []}

    except Exception as e:
        logger.error(f"Error listing subscriptions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(subscription_id: str, event_registry: EventHandlerRegistry = Depends(get_event_registry)):
    """Delete a specific EventSub subscription"""
    try:
        await event_registry.delete_subscription(subscription_id)
        return {"success": True, "message": f"Subscription {subscription_id} deleted"}
    except Exception as e:
        logger.error(f"Error deleting subscription: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{streamer_id}/streams", response_model=dict)
async def get_streams_by_streamer_id(streamer_id: int, db: Session = Depends(get_db)):
    """Get all streams for a streamer by their ID with category history"""
    try:
        # Überprüfen, ob der Streamer existiert (exclude test data)
        streamer = (
            db.query(Streamer)
            .filter(Streamer.id == streamer_id, (Streamer.is_test_data.is_(False)) | (Streamer.is_test_data.is_(None)))
            .first()
        )
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer with ID {streamer_id} not found")

        # PERF: Eager load stream_events to prevent N+1 queries
        # Alle Streams für diesen Streamer abrufen, nach Startdatum absteigend sortiert
        streams = (
            db.query(Stream)
            .filter(Stream.streamer_id == streamer_id)
            .options(joinedload(Stream.stream_events))
            .order_by(Stream.started_at.desc())
            .all()
        )

        # Streams in ein lesbares Format umwandeln
        formatted_streams = []
        for stream in streams:
            # Format events for the response (already loaded via joinedload)
            formatted_events = []
            for event in sorted(
                stream.stream_events, key=lambda e: e.timestamp or datetime.min.replace(tzinfo=timezone.utc)
            ):
                formatted_events.append(
                    {
                        "id": event.id,
                        "event_type": event.event_type,
                        "title": event.title,
                        "category_name": event.category_name,
                        "language": event.language,
                        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    }
                )

            formatted_streams.append(
                {
                    "id": stream.id,
                    "streamer_id": stream.streamer_id,
                    "started_at": stream.started_at.isoformat() if stream.started_at else None,
                    "ended_at": stream.ended_at.isoformat() if stream.ended_at else None,
                    "title": stream.title,
                    "category_name": stream.category_name,
                    "language": stream.language,
                    "twitch_stream_id": stream.twitch_stream_id,
                    "recording_path": stream.recording_path,  # Add recording path to API response
                    "episode_number": stream.episode_number,
                    "events": formatted_events,
                }
            )

        return {
            "streamer": {
                "id": streamer.id,
                "username": streamer.username,
                "profile_image_url": unified_image_service.get_profile_image_url(
                    streamer.id, streamer.profile_image_url
                ),
            },
            "streams": formatted_streams,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving streams for streamer {streamer_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve streams. Please try again.")


@router.delete("/{streamer_id}/streams/{stream_id}")
async def delete_stream(streamer_id: int, stream_id: int, db: Session = Depends(get_db)):
    """Delete a stream and all associated metadata files for a streamer"""
    try:
        # Check if the streamer exists
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer with ID {streamer_id} not found")

        # Check if the stream exists and belongs to the streamer
        stream = db.query(Stream).filter(Stream.id == stream_id, Stream.streamer_id == streamer_id).first()

        if not stream:
            raise HTTPException(status_code=404, detail=f"Stream with ID {stream_id} not found for this streamer")

        # Get metadata to find associated files
        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
        files_to_delete = []

        if metadata:
            # Collect all metadata files that need to be deleted (only actually generated files)
            for attr in [
                "thumbnail_path",
                "json_path",
                "nfo_path",
                "tvshow_nfo_path",
                "season_nfo_path",
                "chapters_vtt_path",
                "chapters_srt_path",
                "chapters_ffmpeg_path",
                "chapters_xml_path",
            ]:
                path = getattr(metadata, attr, None)
                if path:
                    files_to_delete.append(path)

            # Delete metadata record first (foreign key constraint)
            db.delete(metadata)

        # Check for recordings associated with this stream and collect their paths
        recordings = db.query(Recording).filter(Recording.stream_id == stream_id).all()
        for recording in recordings:
            if recording.path:
                files_to_delete.append(recording.path)
            # Delete recording record
            db.delete(recording)

        # Also check stream.recording_path and add all related files
        if stream.recording_path:
            files_to_delete.append(stream.recording_path)

            # Add all possible related files based on the recording path
            base_path = os.path.splitext(stream.recording_path)[0]
            related_files = [
                f"{base_path}-thumb.jpg",  # Thumbnail
                f"{base_path}.info.json",  # JSON metadata
                f"{base_path}.json",  # Alternative JSON metadata
                f"{base_path}.srt",  # Subtitle files
                f"{base_path}.vtt",  # WebVTT files
                f"{base_path}.xml",  # XML metadata
                f"{base_path}-ffmpeg-chapters.txt",  # FFmpeg chapter files
                f"{base_path}-chapters.txt",  # Alternative chapter markers
                f"{base_path}-chapters.vtt",  # WebVTT chapters
                f"{base_path}-chapters.srt",  # SRT chapters
                f"{base_path}.nfo",  # NFO metadata
                f"{base_path}_thumbnail.jpg",  # Alternative thumbnail naming
            ]

            # Add all related files that exist
            for related_file in related_files:
                if os.path.exists(related_file):
                    files_to_delete.append(related_file)

        # Delete all stream events
        db.query(StreamEvent).filter(StreamEvent.stream_id == stream_id).delete()

        # Delete any active recording state entries for this stream
        db.query(ActiveRecordingState).filter(ActiveRecordingState.stream_id == stream_id).delete()

        # Delete the stream record itself
        db.delete(stream)
        db.commit()

        # Now delete all the files
        deleted_files, deleted_count = await delete_files_async(files_to_delete)

        return {
            "success": True,
            "message": f"Stream {stream_id} deleted successfully",
            "deleted_files": deleted_files,
            "deleted_files_count": deleted_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting stream {stream_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete stream. Please try again.")


@router.get("/validate/{username}")
async def validate_streamer(username: str, streamer_service: StreamerService = Depends(get_streamer_service)):
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
                    "profile_image_url": unified_image_service.get_profile_image_url(
                        existing_streamer.id, existing_streamer.profile_image_url
                    ),
                    "description": "This streamer is already in your list",
                },
            }

        # Überprüfe den Streamer bei Twitch mit der vorhandenen Methode
        user_data = await streamer_service.get_user_data(username)

        if not user_data:
            return {"valid": False, "message": f"Streamer '{username}' not found on Twitch"}

        # Extrahiere die relevanten Informationen aus dem Twitch-Benutzer
        streamer_info = {
            "id": None,  # Noch nicht in der Datenbank
            "twitch_id": user_data.get("id"),
            "username": user_data.get("login"),
            "display_name": user_data.get("display_name"),
            "profile_image_url": user_data.get("profile_image_url"),
            "description": user_data.get("description", ""),
        }

        return {"valid": True, "message": "Valid Twitch username", "streamer_info": streamer_info}
    except Exception as e:
        logger.error(f"Error validating streamer: {e}", exc_info=True)
        return {"valid": False, "message": "Failed to validate streamer. Please try again."}


@router.get("/{streamer_id}/streams/{stream_id}/chapters")
async def get_stream_chapters(streamer_id: int, stream_id: int, db: Session = Depends(get_db)):
    """Get chapter data for a specific stream"""
    try:
        # First verify the stream exists for this streamer
        stream = db.query(Stream).filter(Stream.id == stream_id, Stream.streamer_id == streamer_id).first()

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
                with open(metadata.chapters_vtt_path, "r", encoding="utf-8") as f:
                    vtt_content = f.read()
                chapters.extend(parse_webvtt_chapters(vtt_content))
                logger.debug(f"Loaded {len(chapters)} chapters from WebVTT file")
            except Exception as e:
                logger.warning(f"Failed to parse WebVTT chapters: {e}")

        # If no WebVTT chapters, try to load from StreamEvents (API-based chapters)
        if not chapters:
            events = (
                db.query(StreamEvent)
                .filter(
                    StreamEvent.stream_id == stream_id, StreamEvent.event_type.in_(["stream.online", "channel.update"])
                )
                .order_by(StreamEvent.timestamp)
                .all()
            )

            for event in events:
                try:
                    event_data = json.loads(event.event_data) if event.event_data else {}
                    title = "Stream Event"

                    if event.event_type == "stream.online":
                        title = "Stream Started"
                    elif event.event_type == "channel.update":
                        title = event_data.get("title", "Channel Update")
                        # Limit title length for chapters
                        if len(title) > 50:
                            title = title[:47] + "..."

                    chapters.append({"start_time": event.timestamp.isoformat(), "title": title, "type": "event"})
                except Exception as e:
                    logger.warning(f"Failed to process event {event.id}: {e}")

            logger.debug(f"Generated {len(chapters)} chapters from events")

        # If still no chapters, create a basic chapter for the stream start
        if not chapters and stream.started_at:
            chapters.append(
                {"start_time": stream.started_at.isoformat(), "title": stream.title or "Stream", "type": "stream"}
            )

        # Return chapter data with metadata
        video_url = None
        if stream.recording_path:
            # Convert absolute path to relative URL for static file serving
            try:
                video_path = Path(stream.recording_path)
                if video_path.exists():
                    # Use the stream ID for direct video streaming
                    video_url = f"/api/videos/{stream.id}/stream"
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
                "has_ffmpeg": bool(metadata.chapters_ffmpeg_path and Path(metadata.chapters_ffmpeg_path).exists()),
            },
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
    lines = vtt_content.split("\n")
    current_chapter = None

    for line in lines:
        line = line.strip()

        # Skip empty lines and WebVTT header
        if not line or line == "WEBVTT":
            continue

        # Look for timestamp lines (format: 00:00:00.000 --> 00:00:00.000)
        timestamp_match = re.match(r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})", line)
        if timestamp_match:
            # Add the previous chapter before starting a new one
            if current_chapter and current_chapter.get("title"):
                chapters.append(current_chapter)

            start_time = timestamp_match.group(1)
            current_chapter = {"start_time": start_time, "title": "", "type": "chapter"}
        elif current_chapter and line and not line.startswith("NOTE"):
            # This is the chapter title
            if not current_chapter["title"]:
                current_chapter["title"] = line
            else:
                # Multi-line title
                current_chapter["title"] += " " + line

    # Add the last chapter (only if it has a title)
    if current_chapter and current_chapter.get("title"):
        chapters.append(current_chapter)

    return chapters


@router.delete("/{streamer_id}/streams")
async def delete_all_streams(streamer_id: int, exclude_active: bool = True, db: Session = Depends(get_db)):
    """Delete all streams and all associated metadata files for a streamer"""
    try:
        # Check if the streamer exists
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer with ID {streamer_id} not found")

        # Get all streams for this streamer
        streams = db.query(Stream).filter(Stream.streamer_id == streamer_id).all()

        # Identify streams that are currently being recorded (active recording state)
        # Use typing.List for compatibility across Python versions
        skipped_active_stream_ids: List[int] = []
        active_stream_ids: set[int] = set()
        if exclude_active:
            try:
                from datetime import datetime

                # Join to ensure we only consider this streamer's states
                active_states = (
                    db.query(ActiveRecordingState)
                    .join(Stream, ActiveRecordingState.stream_id == Stream.id)
                    .filter(Stream.streamer_id == streamer_id)
                    .all()
                )
                now_map = {}
                for state in active_states:
                    # Determine staleness (5 minutes default)
                    lh = state.last_heartbeat
                    if lh is None:
                        # Treat entries without heartbeat as active to be safe
                        active_stream_ids.add(state.stream_id)
                        continue
                    if lh.tzinfo not in now_map:
                        # Cache now() per tzinfo to avoid repeated calls
                        now_map[lh.tzinfo] = datetime.now(lh.tzinfo) if lh.tzinfo else datetime.utcnow()
                    now = now_map[lh.tzinfo]
                    age_seconds = (now - lh).total_seconds()
                    if age_seconds <= 300 and state.status in ("active", "stopping"):
                        active_stream_ids.add(state.stream_id)
                skipped_active_stream_ids = [s.id for s in streams if s.id in active_stream_ids]
            except Exception as e:
                # If any issue occurs determining active states, default to not skipping
                logger.warning(f"Failed to determine active recording states for streamer {streamer_id}: {e}")

        # Also handle orphaned recordings with null stream_id for this streamer
        orphaned_recordings = db.query(Recording).filter(Recording.stream_id.is_(None)).all()

        if not streams and not orphaned_recordings:
            return {
                "success": True,
                "message": f"No streams or recordings found for streamer {streamer_id}",
                "deleted_streams": 0,
                "deleted_files": [],
                "deleted_files_count": 0,
            }

        # Collect all metadata files that need to be deleted
        files_to_delete = []
        deleted_stream_ids = []

        for stream in streams:
            # Skip streams that are currently recording if requested
            if exclude_active and stream.id in active_stream_ids:
                continue
            deleted_stream_ids.append(stream.id)

            # Get metadata for this stream
            metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream.id).first()

            if metadata:
                # Collect all metadata files that need to be deleted (only actually generated files)
                for attr in [
                    "thumbnail_path",
                    "json_path",
                    "nfo_path",
                    "tvshow_nfo_path",
                    "season_nfo_path",
                    "chapters_vtt_path",
                    "chapters_srt_path",
                    "chapters_ffmpeg_path",
                    "chapters_xml_path",
                ]:
                    path = getattr(metadata, attr, None)
                    if path:
                        files_to_delete.append(path)

                # Delete metadata record (foreign key constraint)
                db.delete(metadata)

            # Check for recordings associated with this stream and collect their paths
            recordings = db.query(Recording).filter(Recording.stream_id == stream.id).all()
            for recording in recordings:
                if recording.path:
                    files_to_delete.append(recording.path)
                # Delete recording record
                db.delete(recording)

            # Delete all stream events for this stream
            db.query(StreamEvent).filter(StreamEvent.stream_id == stream.id).delete()

            # Delete active recording state for this stream
            db.query(ActiveRecordingState).filter(ActiveRecordingState.stream_id == stream.id).delete()

            # Delete the stream record itself
            db.delete(stream)

        # Handle orphaned recordings
        for recording in orphaned_recordings:
            if recording.path:
                files_to_delete.append(recording.path)
            # Delete orphaned recording record
            db.delete(recording)

        # Commit all database deletions
        db.commit()

        # Now delete all the files
        deleted_files, deleted_count = await delete_files_async(files_to_delete)

        return {
            "success": True,
            "message": (
                f"Deleted {len(deleted_stream_ids)} streams for streamer {streamer_id}"
                + (
                    f", skipped {len(skipped_active_stream_ids)} active recording(s)"
                    if exclude_active and skipped_active_stream_ids
                    else ""
                )
            ),
            "deleted_streams": len(deleted_stream_ids),
            "deleted_stream_ids": deleted_stream_ids,
            "skipped_active_stream_ids": skipped_active_stream_ids,
            "deleted_files": deleted_files,
            "deleted_files_count": deleted_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting all streams for streamer {streamer_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete all streams. Please try again.")
