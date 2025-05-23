from fastapi import APIRouter, HTTPException, Depends
from app.database import SessionLocal, get_db
from app.models import RecordingSettings, StreamerRecordingSettings, Streamer
from app.schemas.recording import RecordingSettingsSchema, StreamerRecordingSettingsSchema, ActiveRecordingSchema
from app.schemas.recording import CleanupPolicySchema, StorageUsageSchema
from app.services.recording_service import RecordingService
from sqlalchemy.orm import Session, joinedload
import logging
import json
from typing import List, Dict

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/api/recording",
    tags=["recording"]
)

recording_service = RecordingService()

@router.get("/settings", response_model=RecordingSettingsSchema)
async def get_recording_settings():
    try:
        with SessionLocal() as db:
            settings = db.query(RecordingSettings).first()            if not settings:
                # Initialize with default values
                settings = RecordingSettings(
                    enabled=True,
                    output_directory="/recordings",
                    filename_template="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
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
              # Update fields
            existing_settings.enabled = settings_data.enabled
            existing_settings.output_directory = settings_data.output_directory
            existing_settings.filename_template = settings_data.filename_template
            existing_settings.default_quality = settings_data.default_quality
            existing_settings.use_chapters = settings_data.use_chapters
            
            # Füge das neue Feld hinzu
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
            
            return existing_settings
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
                    profile_image_url=streamer.profile_image_url,
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
    try:
        return await recording_service.get_active_recordings()
    except Exception as e:
        logger.error(f"Error fetching active recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop/{streamer_id}")
async def stop_recording(streamer_id: int):
    """Manually stop an active recording"""
    try:
        result = await recording_service.stop_recording(streamer_id)
        if result:
            return {"status": "success", "message": "Recording stopped successfully"}
        else:
            return {"status": "error", "message": "No active recording found"}
    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
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
        streamer_settings.enabled = settings.enabled
        if settings.quality is not None:
            streamer_settings.quality = settings.quality
        if settings.custom_filename is not None:
            streamer_settings.custom_filename = settings.custom_filename
        if settings.max_streams is not None:
            streamer_settings.max_streams = settings.max_streams
        
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
            profile_image_url=streamer.profile_image_url,
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
    
@router.post("/force/{streamer_id}")
async def force_start_recording(streamer_id: int):
    """Manuell eine Aufnahme für einen aktiven Stream starten"""
    try:
        result = await recording_service.force_start_recording(streamer_id)
        if result:
            return {"status": "success", "message": "Recording started successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to start recording. Streamer might not be live.")
    except Exception as e:
        logger.error(f"Error force starting recording: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/force-offline/{streamer_id}")
async def force_start_offline_recording(streamer_id: int):
    """Manuell eine Aufnahme für einen Stream starten, auch wenn das online Event nicht erkannt wurde"""
    try:
        result = await recording_service.force_start_recording_offline(streamer_id)
        if result:
            return {"status": "success", "message": "Recording started successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to start recording. Check logs for details.")
    except Exception as e:
        logger.error(f"Error force starting offline recording: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup/{streamer_id}")
async def cleanup_old_recordings(streamer_id: int):
    """Manually clean up old recordings for a streamer"""
    try:
        from app.services.cleanup_service import CleanupService
        deleted_count, deleted_paths = await CleanupService.cleanup_old_recordings(streamer_id)
        
        return {
            "status": "success", 
            "message": f"Cleaned up {deleted_count} recordings",
            "deleted_count": deleted_count,
            "deleted_paths": deleted_paths
        }
    except Exception as e:
        logger.error(f"Error cleaning up recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup/{streamer_id}/custom", response_model=Dict)
async def run_custom_cleanup(streamer_id: int, policy: CleanupPolicySchema):
    """Run a custom cleanup with specified policy"""
    try:
        from app.services.cleanup_service import CleanupService
        
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
        from app.services.cleanup_service import CleanupService
        usage = await CleanupService.get_storage_usage(streamer_id)
        return usage
    except Exception as e:
        logger.error(f"Error getting storage usage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/streamers/{streamer_id}/cleanup-policy", response_model=Dict)
async def update_streamer_cleanup_policy(streamer_id: int, policy: CleanupPolicySchema, db: Session = Depends(get_db)):
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
        
        # Convert policy to JSON string and store it
        import json
        streamer_settings.cleanup_policy = json.dumps(policy.dict())
        
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
