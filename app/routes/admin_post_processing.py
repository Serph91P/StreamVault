"""
Admin endpoints for manual post-processing management
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
import logging
import os
from pydantic import BaseModel

logger = logging.getLogger("streamvault.admin.post_processing")

# Get recordings directory from environment or use default
RECORDINGS_ROOT = os.environ.get("RECORDING_DIRECTORY", "/srv/recordings")

router = APIRouter(prefix="/post-processing", tags=["admin", "post-processing"])

class PostProcessingRetryRequest(BaseModel):
    recording_ids: List[int]
    dry_run: bool = False

class PostProcessingStatsResponse(BaseModel):
    orphaned_recordings: int
    orphaned_segments: int
    total_size_gb: float
    by_streamer: Dict[str, Any]

class PostProcessingRetryResponse(BaseModel):
    success: bool
    message: str
    recovery_triggered: int
    recovery_failed: int
    segments_cleaned: int
    details: List[Dict[str, Any]]
    errors: List[str]

@router.get("/stats", response_model=PostProcessingStatsResponse)
async def get_orphaned_recordings_stats(
    max_age_hours: int = Query(48, description="Maximum age in hours for orphaned recordings")
) -> PostProcessingStatsResponse:
    """
    🔍 Get Statistics of Orphaned Recordings
    Shows .ts files and segment directories that need post-processing
    """
    try:
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        
        logger.info(f"📊 ADMIN_POST_PROCESSING_STATS: Getting stats for max_age={max_age_hours}h")
        
        recovery_service = await get_orphaned_recovery_service()
        stats = await recovery_service.get_orphaned_statistics(max_age_hours=max_age_hours)
        
        # Ensure by_streamer is always a dict (compatibility wrapper may return None)
        by_streamer = stats.get("by_streamer")
        if by_streamer is None or not isinstance(by_streamer, dict):
            by_streamer = {}
        
        return PostProcessingStatsResponse(
            orphaned_recordings=stats.get("total_orphaned", 0),
            orphaned_segments=stats.get("total_orphaned_segments", 0),
            total_size_gb=stats.get("total_size_gb", 0.0),
            by_streamer=by_streamer
        )
        
    except Exception as e:
        logger.error(f"Error getting orphaned recordings stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@router.post("/retry-all", response_model=PostProcessingRetryResponse)
async def retry_all_failed_post_processing(
    max_age_hours: int = Query(48, description="Maximum age in hours for orphaned recordings"),
    dry_run: bool = Query(False, description="If true, only show what would be processed"),
    cleanup_segments: bool = Query(True, description="Also cleanup orphaned segment directories")
) -> PostProcessingRetryResponse:
    """
    🔄 Retry Post-Processing for All Failed Recordings
    Finds all .ts files without corresponding .mp4 files and restarts post-processing
    """
    try:
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        
        logger.info(f"🔄 ADMIN_RETRY_ALL_POST_PROCESSING: max_age={max_age_hours}h, dry_run={dry_run}, cleanup_segments={cleanup_segments}")
        
        recovery_service = await get_orphaned_recovery_service()
        result = await recovery_service.scan_and_recover_orphaned_recordings(
            max_age_hours=max_age_hours,
            dry_run=dry_run,
            cleanup_segments=cleanup_segments
        )
        
        logger.info(f"🔄 ADMIN_RETRY_ALL_RESULT: triggered={result['recovery_triggered']}, failed={result['recovery_failed']}")
        
        return PostProcessingRetryResponse(
            success=True,
            message=f"{'Would process' if dry_run else 'Processed'} {result['recovery_triggered']} recordings",
            recovery_triggered=result.get("recovery_triggered", 0),
            recovery_failed=result.get("recovery_failed", 0),
            segments_cleaned=result.get("segments_cleaned", 0),
            details=result.get("orphaned_recordings", []),
            errors=result.get("errors", [])
        )
        
    except Exception as e:
        logger.error(f"Error retrying post-processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retry post-processing: {str(e)}")

@router.post("/retry-specific", response_model=PostProcessingRetryResponse)
async def retry_specific_recordings(
    request: PostProcessingRetryRequest
) -> PostProcessingRetryResponse:
    """
    🎯 Retry Post-Processing for Specific Recordings
    Manually restart post-processing for selected recording IDs
    """
    try:
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        from app.database import SessionLocal
        from app.models import Recording
        
        logger.info(f"🎯 ADMIN_RETRY_SPECIFIC: recording_ids={request.recording_ids}, dry_run={request.dry_run}")
        
        recovery_service = await get_orphaned_recovery_service()
        
        result = {
            "recovery_triggered": 0,
            "recovery_failed": 0,
            "segments_cleaned": 0,
            "details": [],
            "errors": []
        }
        
        with SessionLocal() as db:
            for recording_id in request.recording_ids:
                try:
                    # Get the recording
                    recording = db.query(Recording).filter(Recording.id == recording_id).first()
                    if not recording:
                        result["errors"].append(f"Recording {recording_id} not found")
                        continue
                    
                    # Validate the recording
                    validation = await recovery_service._validate_orphaned_recording(recording)
                    if not validation["valid"]:
                        result["errors"].append(f"Recording {recording_id}: {validation['reason']}")
                        continue
                    
                    recording_info = {
                        "recording_id": recording_id,
                        "streamer_name": recording.stream.streamer.username if recording.stream and recording.stream.streamer else "Unknown",
                        "file_path": recording.path,
                        "recovery_triggered": False,
                        "error": None
                    }
                    
                    if not request.dry_run:
                        # Trigger recovery
                        success = await recovery_service._trigger_orphaned_recovery(recording, db)
                        if success:
                            result["recovery_triggered"] += 1
                            recording_info["recovery_triggered"] = True
                            logger.info(f"✅ Triggered recovery for recording {recording_id}")
                        else:
                            result["recovery_failed"] += 1
                            recording_info["error"] = "Failed to trigger recovery"
                            logger.error(f"❌ Failed to trigger recovery for recording {recording_id}")
                    else:
                        result["recovery_triggered"] += 1  # Count for dry run
                        recording_info["recovery_triggered"] = True
                    
                    result["details"].append(recording_info)
                    
                except Exception as e:
                    result["recovery_failed"] += 1
                    result["errors"].append(f"Recording {recording_id}: {str(e)}")
                    logger.error(f"Error processing recording {recording_id}: {e}", exc_info=True)
        
        message = f"{'Would trigger' if request.dry_run else 'Triggered'} recovery for {result['recovery_triggered']} recordings"
        if result["recovery_failed"] > 0:
            message += f", {result['recovery_failed']} failed"
        
        return PostProcessingRetryResponse(
            success=True,
            message=message,
            recovery_triggered=result["recovery_triggered"],
            recovery_failed=result["recovery_failed"],
            segments_cleaned=result["segments_cleaned"],
            details=result["details"],
            errors=result["errors"]
        )
        
    except Exception as e:
        logger.error(f"Error retrying specific recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retry specific recordings: {str(e)}")

@router.post("/cleanup-segments")
async def cleanup_orphaned_segments(
    max_age_hours: int = Query(48, description="Maximum age in hours for orphaned segments"),
    dry_run: bool = Query(False, description="If true, only show what would be cleaned")
) -> Dict[str, Any]:
    """
    🧹 Cleanup Orphaned Segment Directories
    Remove segment directories that have no corresponding .mp4 file
    """
    try:
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        from app.database import SessionLocal
        
        logger.info(f"🧹 ADMIN_CLEANUP_SEGMENTS: max_age={max_age_hours}h, dry_run={dry_run}")
        
        recovery_service = await get_orphaned_recovery_service()
        
        result = {
            "segments_cleaned": 0,
            "segments_cleanup_failed": 0,
            "segments_cleaned_list": [],
            "errors": []
        }
        
        with SessionLocal() as db:
            await recovery_service._cleanup_orphaned_segments(db, max_age_hours, dry_run, result)
        
        logger.info(f"🧹 ADMIN_CLEANUP_SEGMENTS_RESULT: cleaned={result['segments_cleaned']}, failed={result['segments_cleanup_failed']}")
        
        message = f"{'Would clean' if dry_run else 'Cleaned'} {result['segments_cleaned']} orphaned segment directories"
        if result["segments_cleanup_failed"] > 0:
            message += f", {result['segments_cleanup_failed']} failed"
        
        return {
            "success": True,
            "message": message,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error cleaning orphaned segments: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cleanup segments: {str(e)}")

@router.post("/cleanup-orphaned-files")
async def cleanup_orphaned_files() -> Dict[str, Any]:
    """
    🧹 Cleanup Orphaned Files
    Remove broken symlinks, 0-byte files, and empty segment directories
    
    Security: Uses configured RECORDING_DIRECTORY, no user input accepted
    """
    try:
        from app.services.system.cleanup_service import cleanup_service
        
        # SECURITY: Pass None to use configured directory (safest approach)
        # This prevents any possibility of path traversal attacks
        logger.info(f"🧹 ADMIN_CLEANUP_ORPHANED_FILES: Using configured RECORDING_DIRECTORY")
        
        cleaned_count, cleaned_paths = await cleanup_service.cleanup_orphaned_files(None)
        
        logger.info(f"🧹 ADMIN_CLEANUP_ORPHANED_FILES_RESULT: cleaned={cleaned_count} items")
        
        return {
            "success": True,
            "message": f"Cleaned {cleaned_count} orphaned files",
            "data": {
                "cleaned_count": cleaned_count,
                "cleaned_paths": cleaned_paths[:100]  # Limit to first 100 for response size
            }
        }
        
    except Exception as e:
        logger.error(f"Error cleaning orphaned files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cleanup orphaned files: {str(e)}")

@router.get("/orphaned-list")
async def get_orphaned_recordings_list(
    max_age_hours: int = Query(48, description="Maximum age in hours for orphaned recordings"),
    limit: int = Query(50, description="Maximum number of recordings to return")
) -> Dict[str, Any]:
    """
    📋 Get List of Orphaned Recordings
    Returns detailed list of recordings that need post-processing
    """
    try:
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        from app.database import SessionLocal
        
        logger.info(f"📋 ADMIN_ORPHANED_LIST: max_age={max_age_hours}h, limit={limit}")
        
        recovery_service = await get_orphaned_recovery_service()
        
        with SessionLocal() as db:
            orphaned_recordings = await recovery_service._find_orphaned_recordings(db, max_age_hours)
            
            # Limit the results and add validation info
            limited_recordings = orphaned_recordings[:limit]
            
            recordings_info = []
            for recording in limited_recordings:
                validation = await recovery_service._validate_orphaned_recording(recording)
                
                recording_info = {
                    "recording_id": recording.id,
                    "streamer_name": recording.stream.streamer.username if recording.stream and recording.stream.streamer else "Unknown",
                    "stream_title": recording.stream.title if recording.stream else "Unknown",
                    "file_path": recording.path,
                    "created_at": recording.created_at.isoformat() if recording.created_at else None,
                    "status": recording.status,
                    "file_size_mb": validation.get("file_size", 0) / (1024*1024) if validation.get("file_size") else 0,
                    "file_age_hours": validation.get("file_age_seconds", 0) / 3600 if validation.get("file_age_seconds") else 0,
                    "valid_for_recovery": validation["valid"],
                    "validation_reason": validation.get("reason") if not validation["valid"] else None
                }
                
                recordings_info.append(recording_info)
        
        return {
            "success": True,
            "total_found": len(orphaned_recordings),
            "total_returned": len(recordings_info),
            "recordings": recordings_info
        }
        
    except Exception as e:
        logger.error(f"Error getting orphaned recordings list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get orphaned list: {str(e)}")

@router.post("/enqueue-manual")
async def enqueue_manual_post_processing(
    recording_id: int,
    ts_file_path: str,
    streamer_name: str,
    stream_id: Optional[int] = None,
    force: bool = Query(False, description="Force processing even if MP4 exists")
) -> Dict[str, Any]:
    """
    ⚡ Manually Enqueue Post-Processing
    Directly enqueue post-processing tasks for a specific file
    """
    try:
        from app.services.init.background_queue_init import enqueue_recording_post_processing
        from pathlib import Path
        from datetime import datetime
        import os
        
        logger.info(f"⚡ ADMIN_MANUAL_ENQUEUE: recording_id={recording_id}, file={ts_file_path}")
        
        # Validate and secure the file path
        normalized_path = os.path.normpath(os.path.join(RECORDINGS_ROOT, ts_file_path))
        if not normalized_path.startswith(RECORDINGS_ROOT):
            raise HTTPException(status_code=400, detail="Invalid file path: outside allowed directory")
        
        # Validate file exists
        if not Path(normalized_path).exists():
            raise HTTPException(status_code=400, detail=f"File not found: {ts_file_path}")
        
        # Check if MP4 already exists (unless forced)
        mp4_path = normalized_path.replace('.ts', '.mp4')
        if Path(mp4_path).exists() and not force:
            raise HTTPException(status_code=400, detail=f"MP4 already exists: {mp4_path}. Use force=true to override.")
        
        # Prepare parameters
        output_dir = os.path.dirname(normalized_path)
        started_at = datetime.now().isoformat()
        
        # Validate stream_id is provided
        if stream_id is None:
            raise HTTPException(status_code=400, detail="stream_id is required and cannot be derived from recording_id")
        
        # Enqueue post-processing
        task_ids = await enqueue_recording_post_processing(
            stream_id=stream_id,
            recording_id=recording_id,
            ts_file_path=normalized_path,
            output_dir=output_dir,
            streamer_name=streamer_name,
            started_at=started_at,
            cleanup_ts_file=True
        )
        
        logger.info(f"⚡ ADMIN_MANUAL_ENQUEUE_SUCCESS: recording_id={recording_id}, task_ids={task_ids}")
        
        return {
            "success": True,
            "message": f"Post-processing enqueued for recording {recording_id}",
            "recording_id": recording_id,
            "task_ids": task_ids,
            "ts_file_path": ts_file_path,
            "mp4_output_path": mp4_path
        }
        
    except Exception as e:
        logger.error(f"Error enqueuing manual post-processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to enqueue post-processing: {str(e)}")
