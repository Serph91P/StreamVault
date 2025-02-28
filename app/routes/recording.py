from fastapi import APIRouter, HTTPException, Depends
from app.database import SessionLocal, get_db
from app.models import RecordingSettings, StreamerRecordingSettings, Streamer
from app.schemas.recording import RecordingSettingsSchema, StreamerRecordingSettingsSchema, ActiveRecordingSchema
from app.services.recording_service import RecordingService
from sqlalchemy.orm import Session, joinedload
import logging
from typing import List

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
            settings = db.query(RecordingSettings).first()
            if not settings:
                # Initialize with default values
                settings = RecordingSettings(
                    enabled=True,
                    output_directory="/recordings",
                    filename_template="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
                    default_quality="best",
                    use_chapters=True,
                    max_concurrent_recordings=3
                )
                db.add(settings)
                db.commit()
                db.refresh(settings)
            return settings
    except Exception as e:
        logger.error(f"Error fetching recording settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/settings", response_model=RecordingSettingsSchema)
async def update_recording_settings(settings_data: RecordingSettingsSchema):
    try:
        with SessionLocal() as db:
            settings = db.query(RecordingSettings).first()
            if not settings:
                settings = RecordingSettings()
                db.add(settings)
            
            settings.enabled = settings_data.enabled
            settings.output_directory = settings_data.output_directory
            settings.filename_template = settings_data.filename_template
            settings.default_quality = settings_data.default_quality
            settings.use_chapters = settings_data.use_chapters
            settings.max_concurrent_recordings = settings_data.max_concurrent_recordings
            
            db.commit()
            
            return settings
    except Exception as e:
        logger.error(f"Error updating recording settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/streamers", response_model=List[StreamerRecordingSettingsSchema])
async def get_all_streamer_recording_settings():
    try:
        with SessionLocal() as db:
            settings = db.query(StreamerRecordingSettings).join(Streamer).options(
                joinedload(StreamerRecordingSettings.streamer)
            ).all()
            
            return [
                StreamerRecordingSettingsSchema(
                    streamer_id=s.streamer_id,
                    username=s.streamer.username,
                    profile_image_url=s.streamer.profile_image_url,  # Added profile image
                    enabled=s.enabled,
                    quality=s.quality,
                    custom_filename=s.custom_filename
                )
                for s in settings
            ]
    except Exception as e:
        logger.error(f"Error fetching streamer recording settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/streamers/{streamer_id}", response_model=StreamerRecordingSettingsSchema)
async def update_streamer_recording_settings(
    streamer_id: int, 
    settings_data: StreamerRecordingSettingsSchema
):
    try:
        with SessionLocal() as db:
            settings = db.query(StreamerRecordingSettings).filter_by(streamer_id=streamer_id).first()
            if not settings:
                settings = StreamerRecordingSettings(streamer_id=streamer_id)
                db.add(settings)
            
            settings.enabled = settings_data.enabled
            settings.quality = settings_data.quality
            settings.custom_filename = settings_data.custom_filename
            
            db.commit()
            
            streamer = db.query(Streamer).get(streamer_id)
            
            return StreamerRecordingSettingsSchema(
                streamer_id=settings.streamer_id,
                username=streamer.username if streamer else None,
                enabled=settings.enabled,
                quality=settings.quality,
                custom_filename=settings.custom_filename
            )
    except Exception as e:
        logger.error(f"Error updating streamer recording settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active", response_model=List[ActiveRecordingSchema])
async def get_active_recordings():
    try:
        return await recording_service.get_active_recordings()
    except Exception as e:
        logger.error(f"Error fetching active recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test/{streamer_id}")
async def test_recording(streamer_id: int):
    """Test recording for a specific streamer"""
    try:
        with SessionLocal() as db:
            streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if not streamer:
                raise HTTPException(status_code=404, detail="Streamer not found")
                
            # Simulate a stream online event
            result = await recording_service.start_recording(streamer_id, {
                "id": f"test_{streamer_id}",
                "broadcaster_user_id": streamer.twitch_id,
                "broadcaster_user_name": streamer.username,
                "started_at": datetime.now().isoformat(),
                "title": streamer.title or "Test Stream",
                "category_name": streamer.category_name or "Test Category",
                "language": streamer.language or "en"
            })
            
            if result:
                return {"status": "success", "message": f"Test recording started for {streamer.username}"}
            else:
                return {"status": "error", "message": "Failed to start test recording"}
    except Exception as e:
        logger.error(f"Error starting test recording: {e}")
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
