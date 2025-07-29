from fastapi import APIRouter, HTTPException, Depends
from app.database import SessionLocal, get_db
from app.models import RecordingSettings, StreamerRecordingSettings, Streamer, Stream, Recording
from app.schemas.recording import RecordingSettingsSchema, StreamerRecordingSettingsSchema, ActiveRecordingSchema
from app.schemas.recording import CleanupPolicySchema, StorageUsageSchema
from app.services.recording.recording_service import RecordingService  # Changed import path
from app.services.recording.config_manager import FILENAME_PRESETS  # Import FILENAME_PRESETS from config_manager
from app.services.system.logging_service import logging_service
from app.services.unified_image_service import unified_image_service
from app.services.communication.websocket_manager import websocket_manager
from sqlalchemy.orm import Session, joinedload
import logging
import json
from typing import List, Dict
from datetime import datetime, timezone

# Cache constants
FALLBACK_SUFFIX = "_fallback"

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/api/recording",
    tags=["recording"]
)

recording_service = None

def get_recording_service():
    """Lazy initialization of recording service"""
    global recording_service
    if recording_service is None:
        recording_service = RecordingService()
    return recording_service

@router.get("/settings", response_model=RecordingSettingsSchema)
async def get_recording_settings():
    try:
        with SessionLocal() as db:
            settings = db.query(RecordingSettings).first()
            if not settings:
                # Initialize with default values
                settings = RecordingSettings(
                    enabled=True,
                    output_directory="/recordings",
                    filename_template="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
                    filename_preset="default",
                    default_quality="best",
                    use_chapters=True,
                )
                db.add(settings)
                db.commit()
                db.refresh(settings)
                
            # Parse the cleanup policy if it exists
            cleanup_policy = None
            if settings.cleanup_policy:
                try:
                    import json
                    cleanup_policy = CleanupPolicySchema.parse_obj(json.loads(settings.cleanup_policy))
                except Exception as e:
                    logger.warning(f"Error parsing cleanup policy: {e}")
                    
            # Create response
            response = RecordingSettingsSchema(
                enabled=settings.enabled,
                output_directory=settings.output_directory,
                filename_template=settings.filename_template,
                filename_preset=getattr(settings, 'filename_preset', 'default'),
                default_quality=settings.default_quality,
                use_chapters=settings.use_chapters,
                use_category_as_chapter_title=getattr(settings, 'use_category_as_chapter_title', False),
                max_streams_per_streamer=getattr(settings, 'max_streams_per_streamer', 0),
                cleanup_policy=cleanup_policy
            )
            
            return response
    except Exception as e:
        logger.error(f"Error fetching recording settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/settings", response_model=RecordingSettingsSchema)
async def update_recording_settings(settings_data: RecordingSettingsSchema):
    try:
        with SessionLocal() as db:
            # Get existing settings
            existing_settings = db.query(RecordingSettings).first()
            
            if not existing_settings:
                # Create new settings if doesn't exist
                existing_settings = RecordingSettings()
                db.add(existing_settings)
                db.commit()
                db.refresh(existing_settings)
                
            # Update fields
            existing_settings.enabled = settings_data.enabled
            existing_settings.output_directory = settings_data.output_directory
            existing_settings.filename_template = settings_data.filename_template
            existing_settings.default_quality = settings_data.default_quality
            existing_settings.use_chapters = settings_data.use_chapters
            
            # Update filename_preset if provided
            if hasattr(settings_data, 'filename_preset') and settings_data.filename_preset:
                existing_settings.filename_preset = settings_data.filename_preset
            
            # Add the new field
            if hasattr(settings_data, 'use_category_as_chapter_title'):
                existing_settings.use_category_as_chapter_title = settings_data.use_category_as_chapter_title
                
            if hasattr(settings_data, 'max_streams_per_streamer'):
                existing_settings.max_streams_per_streamer = settings_data.max_streams_per_streamer
                
            # Update cleanup policy if provided
            if hasattr(settings_data, 'cleanup_policy') and settings_data.cleanup_policy:
                import json
                existing_settings.cleanup_policy = json.dumps(settings_data.cleanup_policy.dict())
            
            # Save changes
            db.commit()
            # This refreshes the instance after commit so it's bound to the session
            db.refresh(existing_settings)
            
            # Parse cleanup policy back to object for response
            cleanup_policy = None
            if existing_settings.cleanup_policy:
                try:
                    import json
                    from app.schemas.recording import CleanupPolicySchema
                    cleanup_policy = CleanupPolicySchema.parse_obj(json.loads(existing_settings.cleanup_policy))
                except Exception as e:
                    logger.warning(f"Error parsing cleanup policy for response: {e}")
            
            # Create response with properly parsed cleanup policy
            return RecordingSettingsSchema(
                enabled=existing_settings.enabled,
                output_directory=existing_settings.output_directory,
                filename_template=existing_settings.filename_template,
                filename_preset=getattr(existing_settings, 'filename_preset', 'default'),
                default_quality=existing_settings.default_quality,
                use_chapters=existing_settings.use_chapters,
                use_category_as_chapter_title=getattr(existing_settings, 'use_category_as_chapter_title', False),
                max_streams_per_streamer=getattr(existing_settings, 'max_streams_per_streamer', 0),
                cleanup_policy=cleanup_policy
            )
    except Exception as e:
        logger.error(f"Error updating recording settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))    
        
@router.get("/streamers", response_model=List[StreamerRecordingSettingsSchema])
async def get_all_streamer_recording_settings():
    try:
        with SessionLocal() as db:
            # Get all streamers first
            streamers = db.query(Streamer).all()
            
            # Get all existing recording settings
            existing_settings = db.query(StreamerRecordingSettings).all()
            
            # Create a dictionary for quick lookup
            settings_dict = {s.streamer_id: s for s in existing_settings}
            
            # Create or get settings for each streamer
            result = []
            for streamer in streamers:
                if streamer.id in settings_dict:
                    # Use existing settings
                    settings = settings_dict[streamer.id]
                else:
                    # Create default settings
                    settings = StreamerRecordingSettings(
                        streamer_id=streamer.id,
                        enabled=True
                    )
                    db.add(settings)
                  # Create response object
                try:
                    cleanup_policy = None
                    if hasattr(settings, 'cleanup_policy') and settings.cleanup_policy:
                        import json
                        cleanup_policy = CleanupPolicySchema.parse_obj(json.loads(settings.cleanup_policy))
                except Exception as e:
                    logger.warning(f"Error parsing cleanup policy: {e}")
                    cleanup_policy = None
                    
                result.append(StreamerRecordingSettingsSchema(
                    streamer_id=streamer.id,
                    username=streamer.username,
                    profile_image_url=unified_image_service.get_profile_image_url(
                        streamer.id, 
                        streamer.profile_image_url
                    ),
                    enabled=settings.enabled,
                    quality=settings.quality,
                    custom_filename=settings.custom_filename,
                    max_streams=settings.max_streams,
                    cleanup_policy=cleanup_policy
                ))
            
            db.commit()
            return result
    except Exception as e:
        logger.error(f"Error fetching streamer recording settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))@router.post("/streamers/{streamer_id}", response_model=StreamerRecordingSettingsSchema)
    
# async def update_streamer_recording_settings(
#     streamer_id: int, 
#     settings_data: StreamerRecordingSettingsSchema
# ):
#     try:
#         with SessionLocal() as db:
#             settings = db.query(StreamerRecordingSettings).filter_by(streamer_id=streamer_id).first()
#             if not settings:
#                 settings = StreamerRecordingSettings(streamer_id=streamer_id)
#                 db.add(settings)
            
#             settings.enabled = settings_data.enabled
#             settings.quality = settings_data.quality
#             settings.custom_filename = settings_data.custom_filename
            
#             db.commit()
            
#             streamer = db.query(Streamer).get(streamer_id)
            
#             return StreamerRecordingSettingsSchema(
#                 streamer_id=settings.streamer_id,
#                 username=streamer.username if streamer else None,
#                 enabled=settings.enabled,
#                 quality=settings.quality,
#                 custom_filename=settings.custom_filename
#             )
#     except Exception as e:
#         logger.error(f"Error updating streamer recording settings: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

@router.get("/active", response_model=List[ActiveRecordingSchema])
async def get_active_recordings():
    """Get all active recordings"""
    import time
    from sqlalchemy.exc import TimeoutError, OperationalError
    try:
        from app.utils.cache import app_cache
    except ImportError:
        # Fallback if cache module is not available
        class DummyCache:
            def delete(self, key): pass
            def get(self, key): return None
            def set(self, key, value, ttl=None): pass
        app_cache = DummyCache()
    
    # Check cache first (with short TTL to reduce database load)
    cache_key = "active_recordings"
    cached_result = app_cache.get(cache_key)
    if cached_result is not None:
        logger.debug(f"Returning {len(cached_result)} active recordings from cache")
        return cached_result
    
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            # Get active recordings directly from database instead of state manager
            # This ensures we only get recordings that are truly active
            result = []
            
            # Use a new session for database queries with proper error handling
            with SessionLocal() as db:
                # Optimized query with joins to reduce database round trips
                active_recordings = db.query(Recording).join(Stream).join(Streamer).filter(
                    Recording.status == "recording"
                ).options(
                    joinedload(Recording.stream).joinedload(Stream.streamer)
                ).all()
                
                for recording in active_recordings:
                    try:
                        # Stream and streamer info already loaded via joinedload
                        stream = recording.stream
                        if stream and stream.streamer:
                            # Calculate duration
                            duration = 0
                            if recording.start_time:
                                duration = int((datetime.now(timezone.utc) - recording.start_time).total_seconds())
                            
                            # Create schema object with all required fields
                            active_recording = ActiveRecordingSchema(
                                id=recording.id,
                                stream_id=recording.stream_id,
                                streamer_id=stream.streamer_id,
                                streamer_name=stream.streamer.username,
                                title=stream.title or '',
                                started_at=recording.start_time.isoformat() if recording.start_time else '',
                                file_path=recording.path or '',
                                status=recording.status,
                                duration=duration
                            )
                            result.append(active_recording)
                    except Exception as e:
                        logger.warning(f"Error processing active recording {recording.id}: {e}")
                        continue
            
            # Cache the result for a short time (2 seconds) to reduce database load
            app_cache.set(cache_key, result, ttl=2)
            # Store a longer-term fallback cache for emergencies
            app_cache.set(f"{cache_key}{FALLBACK_SUFFIX}", result, ttl=300)
            
            logger.info(f"Returning {len(result)} active recordings")
            return result
            
        except (TimeoutError, OperationalError) as e:
            if "QueuePool" in str(e) or "timeout" in str(e).lower():
                logger.warning(f"Database connection pool issue on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    logger.error(f"Database connection pool exhausted after {max_retries} attempts")
                    # Return cached result if available, even if expired
                    fallback_result = app_cache.get(f"{cache_key}{FALLBACK_SUFFIX}")
                    if fallback_result is not None:
                        logger.info(f"Returning fallback cached result with {len(fallback_result)} recordings")
                        return fallback_result
                    return []  # Return empty list instead of failing
            else:
                logger.error(f"Database error: {e}")
                return []
        except Exception as e:
            logger.error(f"Error fetching active recordings: {e}", exc_info=True)
            # Return empty list on error
            return []

@router.post("/stop/{streamer_id}")
async def stop_recording(streamer_id: int):
    """Manually stop an active recording"""
    try:
        # Get streamer info for notifications
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            streamer_name = streamer.username if streamer else f"Streamer {streamer_id}"
        
        # Log the stop request
        logging_service.log_recording_activity("STOP_REQUEST", f"Streamer {streamer_id}", "Manual stop requested via API")
        
        result = await get_recording_service().stop_recording_manual(streamer_id)
        if result:
            logging_service.log_recording_activity("STOP_SUCCESS", f"Streamer {streamer_id}", "Recording stopped successfully via API")
            
            # Send success toast notification
            await websocket_manager.send_toast_notification(
                toast_type="success",
                title=f"Recording Stopped - {streamer_name}",
                message="Recording stopped successfully!"
            )
            
            return {"status": "success", "message": "Recording stopped successfully"}
        else:
            logging_service.log_recording_activity("STOP_FAILED", f"Streamer {streamer_id}", "No active recording found", "warning")
            
            # Send warning toast notification
            await websocket_manager.send_toast_notification(
                toast_type="warning",
                title=f"Stop Recording - {streamer_name}",
                message="No active recording found to stop."
            )
            
            return {"status": "error", "message": "No active recording found"}
    except Exception as e:
        logging_service.log_recording_error(streamer_id, f"Streamer {streamer_id}", "API_STOP_ERROR", str(e))
        logger.error(f"Error stopping recording: {e}")
        
        # Send error toast notification
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                streamer_name = streamer.username if streamer else f"Streamer {streamer_id}"
                
            await websocket_manager.send_toast_notification(
                toast_type="error",
                title=f"Stop Recording - {streamer_name}",
                message=f"Failed to stop recording: {str(e)}"
            )
        except Exception as notification_error:
            logger.error(f"Failed to send error notification: {notification_error}")
        
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/streamers/{streamer_id}", response_model=StreamerRecordingSettingsSchema)
async def update_streamer_recording_settings(
    streamer_id: int,
    settings: StreamerRecordingSettingsSchema,
    db: Session = Depends(get_db)
):
    """Update recording settings for a specific streamer"""
    try:
        # Check if the streamer exists
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer with ID {streamer_id} not found")
          # Get or create streamer recording settings
        streamer_settings = db.query(StreamerRecordingSettings).filter(
            StreamerRecordingSettings.streamer_id == streamer_id
        ).first()
        
        if not streamer_settings:
            streamer_settings = StreamerRecordingSettings(streamer_id=streamer_id)
            db.add(streamer_settings)
        
        # Update settings
        old_enabled = streamer_settings.enabled if streamer_settings else False
        
        streamer_settings.enabled = settings.enabled
        if settings.quality is not None:
            old_quality = streamer_settings.quality
            streamer_settings.quality = settings.quality
            if old_quality != settings.quality:
                logging_service.log_configuration_change("quality", str(old_quality), str(settings.quality), streamer_id)
        if settings.custom_filename is not None:
            old_filename = streamer_settings.custom_filename
            streamer_settings.custom_filename = settings.custom_filename
            if old_filename != settings.custom_filename:
                logging_service.log_configuration_change("custom_filename", str(old_filename), str(settings.custom_filename), streamer_id)
        if settings.max_streams is not None:
            old_max_streams = streamer_settings.max_streams
            streamer_settings.max_streams = settings.max_streams
            if old_max_streams != settings.max_streams:
                logging_service.log_configuration_change("max_streams", str(old_max_streams), str(settings.max_streams), streamer_id)
        
        # Log the enabled/disabled change
        if old_enabled != settings.enabled:
            logging_service.log_configuration_change("recording_enabled", str(old_enabled), str(settings.enabled), streamer_id)
        
        # Update cleanup policy if provided
        if settings.cleanup_policy is not None:
            import json
            streamer_settings.cleanup_policy = json.dumps(settings.cleanup_policy.dict())
        
        db.commit()
          # Return updated settings with streamer info
        try:
            cleanup_policy = None
            if streamer_settings.cleanup_policy:
                import json
                cleanup_policy = CleanupPolicySchema.parse_obj(json.loads(streamer_settings.cleanup_policy))
        except Exception as e:
            logger.warning(f"Error parsing cleanup policy: {e}")
            cleanup_policy = None
            
        return StreamerRecordingSettingsSchema(
            streamer_id=streamer_settings.streamer_id,
            username=streamer.username,
            profile_image_url=unified_image_service.get_profile_image_url(
                streamer.id, 
                streamer.profile_image_url
            ),
            enabled=streamer_settings.enabled,
            quality=streamer_settings.quality,
            custom_filename=streamer_settings.custom_filename,
            max_streams=streamer_settings.max_streams,
            cleanup_policy=cleanup_policy
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating streamer recording settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/force-start/{streamer_id}")
async def force_start_recording(streamer_id: int):
    """Manually start a recording for an active stream"""
    try:
        # Get streamer info for notifications
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            streamer_name = streamer.username if streamer else f"Streamer {streamer_id}"
        
        # Log force start attempt
        logging_service.log_recording_activity("FORCE_START_REQUEST", f"Streamer {streamer_id}", "Manual force start requested via API")
        
        result = await get_recording_service().force_start_recording(streamer_id)
        if result:
            logging_service.log_recording_activity("FORCE_START_SUCCESS", f"Streamer {streamer_id}", "Force recording started successfully")
            
            # Send success toast notification
            await websocket_manager.send_force_recording_feedback(
                success=True,
                streamer_name=streamer_name,
                message="Recording started successfully!"
            )
            
            return {"status": "success", "message": "Recording started successfully"}
        else:
            # Provide more helpful error message
            logger.error(f"Failed to force start recording for streamer {streamer_id}. This could be because:")
            logger.error(f"1. The streamer is actually offline")
            logger.error(f"2. Streamlink cannot connect to the stream")
            logger.error(f"3. There are network connectivity issues")
            logger.error(f"4. The stream URL is not accessible")
            
            logging_service.log_recording_activity("FORCE_START_FAILED", f"Streamer {streamer_id}", "Force start failed - streamer may be offline or stream inaccessible", "warning")
            
            # Send error toast notification
            await websocket_manager.send_force_recording_feedback(
                success=False,
                streamer_name=streamer_name,
                message="Failed to start recording. Streamer may be offline or stream not accessible."
            )
            
            raise HTTPException(
                status_code=400, 
                detail="Failed to start recording. The streamer may be offline, or the stream may not be accessible. Check the logs for more details."
            )
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        logging_service.log_recording_error(streamer_id, f"Streamer {streamer_id}", "FORCE_START_ERROR", str(e))
        logger.error(f"Error force starting recording: {e}", exc_info=True)
        
        # Send error toast notification for unexpected errors
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                streamer_name = streamer.username if streamer else f"Streamer {streamer_id}"
                
            await websocket_manager.send_force_recording_feedback(
                success=False,
                streamer_name=streamer_name,
                message=f"Internal error: {str(e)}"
            )
        except Exception as notification_error:
            logger.error(f"Failed to send error notification: {notification_error}")
        
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



@router.post("/cleanup/{streamer_id}")
async def cleanup_old_recordings(streamer_id: int):
    """Manually clean up old recordings for a streamer"""
    try:
        # Log cleanup request
        logging_service.log_recording_activity("CLEANUP_REQUEST", f"Streamer {streamer_id}", "Manual cleanup requested via API")
        
        from app.services.system.cleanup_service import CleanupService
        deleted_count, deleted_paths = await CleanupService.cleanup_old_recordings(streamer_id)
        
        # Log cleanup results
        if deleted_count > 0:
            logging_service.log_file_operation("CLEANUP", f"{deleted_count} files", True, f"Deleted {deleted_count} old recordings")
        else:
            logging_service.log_recording_activity("CLEANUP_NO_FILES", f"Streamer {streamer_id}", "No files found to clean up")
        
        return {
            "status": "success", 
            "message": f"Cleaned up {deleted_count} recordings",
            "deleted_count": deleted_count,
            "deleted_paths": deleted_paths
        }
    except Exception as e:
        logging_service.log_recording_error(streamer_id, f"Streamer {streamer_id}", "CLEANUP_ERROR", str(e))
        logger.error(f"Error cleaning up recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup/{streamer_id}/custom", response_model=Dict)
async def run_custom_cleanup(streamer_id: int, policy: CleanupPolicySchema):
    """Run a custom cleanup with specified policy"""
    try:
        from app.services.system.cleanup_service import CleanupService
        
        # Convert pydantic model to dict
        policy_dict = policy.dict(exclude_unset=True)
        
        deleted_count, deleted_paths = await CleanupService.cleanup_old_recordings(
            streamer_id, 
            custom_policy=policy_dict
        )
        
        return {
            "status": "success", 
            "message": f"Cleaned up {deleted_count} recordings using custom policy",
            "deleted_count": deleted_count,
            "deleted_paths": deleted_paths
        }
    except Exception as e:
        logger.error(f"Error running custom cleanup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
        
@router.get("/storage/{streamer_id}", response_model=StorageUsageSchema)
async def get_storage_usage(streamer_id: int):
    """Get storage usage information for a streamer"""
    try:
        from app.services.system.cleanup_service import CleanupService
        usage = await CleanupService.get_storage_usage(streamer_id)
        return usage
    except Exception as e:
        logger.error(f"Error getting storage usage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/streamers/{streamer_id}/cleanup-policy", response_model=Dict)
async def update_streamer_cleanup_policy(
    streamer_id: int, 
    request_data: Dict, 
    db: Session = Depends(get_db)
):
    """Update cleanup policy for a specific streamer"""
    try:
        # Check if the streamer exists
        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer with ID {streamer_id} not found")
        
        # Get or create streamer recording settings
        streamer_settings = db.query(StreamerRecordingSettings).filter(
            StreamerRecordingSettings.streamer_id == streamer_id
        ).first()
        
        if not streamer_settings:
            streamer_settings = StreamerRecordingSettings(streamer_id=streamer_id)
            db.add(streamer_settings)
        
        # Handle the use_global_cleanup_policy flag
        use_global = request_data.get('use_global_cleanup_policy', False)
        streamer_settings.use_global_cleanup_policy = use_global
        
        if use_global:
            # Clear custom policy when using global
            streamer_settings.cleanup_policy = None
        else:
            # Set custom policy
            cleanup_policy = request_data.get('cleanup_policy')
            if cleanup_policy:
                import json
                # Validate policy using schema
                policy_schema = CleanupPolicySchema.parse_obj(cleanup_policy)
                streamer_settings.cleanup_policy = json.dumps(policy_schema.dict())
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Cleanup policy updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating streamer cleanup policy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/filename-presets")
async def get_filename_presets():
    """Get all available filename presets"""
    try:
        # Convert the backend dictionary format to frontend array format
        presets = []
        for key, template in FILENAME_PRESETS.items():
            presets.append({
                "value": key,
                "label": key.replace("_", " ").title(),
                "description": template
            })
        
        return {
            "status": "success",
            "data": presets
        }
    except Exception as e:
        logger.error(f"Error getting filename presets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
