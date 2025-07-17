from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Stream, StreamMetadata, Recording, StreamEvent, ActiveRecordingState
from app.services.system.background_queue_service import get_background_queue_service
import logging

logger = logging.getLogger("streamvault")

router = APIRouter(
    prefix="/api/streams",
    tags=["streams"]
)

@router.delete("/{stream_id}")
async def delete_stream(
    request: Request,
    stream_id: int,
    db: Session = Depends(get_db)
):
    """Delete a specific stream and all associated metadata"""
    logger.info(f"Request {request.method} {request.url.path}")
    
    try:
        # Check if the stream exists
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            raise HTTPException(status_code=404, detail=f"Stream with ID {stream_id} not found")
        
        # Collect all metadata files that need to be deleted
        files_to_delete = []
        
        # Get metadata for this stream
        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream.id).first()
        
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
        
        # Commit all database deletions
        db.commit()
        
        # Schedule file deletion in background
        if files_to_delete:
            background_queue = get_background_queue_service()
            await background_queue.add_task(
                "cleanup",
                {
                    "cleanup_paths": files_to_delete,
                    "stream_id": stream_id
                },
                priority=3
            )
        
        return {
            "success": True,
            "message": f"Stream {stream_id} deleted successfully",
            "deleted_files_count": len(files_to_delete)
        }
        
    except Exception as e:
        logger.error(f"Error deleting stream {stream_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete stream. Please try again.")
