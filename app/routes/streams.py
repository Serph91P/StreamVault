from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Stream, StreamMetadata, Recording, StreamEvent, ActiveRecordingState
from app.services.background_queue_service import background_queue_service
from app.utils.security import validate_path_security
import logging
import os
from pathlib import Path

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/streams", tags=["streams"])


@router.delete("/{stream_id}")
async def delete_stream(request: Request, stream_id: int, db: Session = Depends(get_db)):
    """Delete a specific stream and all associated metadata.
    
    IMPORTANT: Uses the same safe deletion logic as cleanup_service:
    - tvshow.nfo is NEVER deleted (belongs to streamer, not stream)
    - season.nfo is only deleted if this is the LAST stream in that season
    - Empty season folders are cleaned up after deletion
    """
    logger.info(f"Request {request.method} {request.url.path}")

    try:
        # Check if the stream exists
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            raise HTTPException(status_code=404, detail=f"Stream with ID {stream_id} not found")

        # Collect all metadata files that need to be deleted
        files_to_delete = []
        directories_to_check = set()

        # Get metadata for this stream
        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream.id).first()

        # Get the base directory for this recording (for later cleanup)
        recording_dir = None
        if stream.recording_path:
            recording_dir = os.path.dirname(stream.recording_path)
            if recording_dir and os.path.exists(recording_dir):
                directories_to_check.add(recording_dir)
        elif metadata and metadata.nfo_path:
            recording_dir = os.path.dirname(metadata.nfo_path)
            if recording_dir and os.path.exists(recording_dir):
                directories_to_check.add(recording_dir)

        if metadata:
            # Per-stream files (unique to this stream, safe to delete)
            # These are the same files handled by cleanup_service
            per_stream_attrs = [
                "thumbnail_path",
                "json_path",
                "nfo_path",  # Episode-specific NFO (not tvshow.nfo!)
                "chapters_vtt_path",
                "chapters_srt_path",
                "chapters_ffmpeg_path",
                "chapters_xml_path",
            ]
            
            for attr in per_stream_attrs:
                path = getattr(metadata, attr, None)
                if path:
                    try:
                        validated_path = validate_path_security(path, "delete")
                        files_to_delete.append(validated_path)
                    except HTTPException as e:
                        logger.warning(f"🚨 SECURITY: Skipping invalid metadata path {path}: {e.detail}")
                        continue

            # SHARED FILES HANDLING (same logic as cleanup_service):
            # - tvshow.nfo: NEVER delete during stream deletion (belongs to streamer)
            # - season.nfo: Only delete if this is the LAST stream in that season
            
            if metadata.tvshow_nfo_path:
                logger.debug(f"Preserving tvshow.nfo (belongs to streamer, not stream): {metadata.tvshow_nfo_path}")
            
            if metadata.season_nfo_path and os.path.exists(metadata.season_nfo_path):
                # Check if other streams exist in the same season directory
                season_dir = os.path.dirname(metadata.season_nfo_path)
                other_streams_in_season = (
                    db.query(Stream)
                    .join(StreamMetadata)
                    .filter(
                        Stream.streamer_id == stream.streamer_id,
                        Stream.id != stream.id,
                        StreamMetadata.season_nfo_path.like(f"{season_dir}%"),
                    )
                    .count()
                )
                if other_streams_in_season == 0:
                    try:
                        validated_path = validate_path_security(metadata.season_nfo_path, "delete")
                        files_to_delete.append(validated_path)
                        logger.debug(f"Last stream in season, will delete season.nfo: {metadata.season_nfo_path}")
                    except HTTPException as e:
                        logger.warning(f"🚨 SECURITY: Skipping invalid season.nfo path: {e.detail}")
                else:
                    logger.debug(f"Keeping shared season.nfo ({other_streams_in_season} other streams in season)")
            
            # Handle segments directory from metadata
            if metadata.segments_dir_path and os.path.exists(metadata.segments_dir_path):
                try:
                    validated_segments = validate_path_security(metadata.segments_dir_path, "access")
                    files_to_delete.append(validated_segments)
                except HTTPException:
                    pass

            # Delete metadata record (foreign key constraint)
            db.delete(metadata)

        # Check for recordings associated with this stream and collect their paths
        recordings = db.query(Recording).filter(Recording.stream_id == stream.id).all()
        for recording in recordings:
            if recording.path:
                try:
                    validated_path = validate_path_security(recording.path, "delete")
                    files_to_delete.append(validated_path)

                    file_path_obj = Path(validated_path)

                    # Check for .ts version if we have .mp4
                    if file_path_obj.suffix == ".mp4":
                        ts_version = file_path_obj.with_suffix(".ts")
                        if ts_version.exists():
                            try:
                                validated_ts = validate_path_security(str(ts_version), "delete")
                                files_to_delete.append(validated_ts)
                            except HTTPException:
                                pass

                    # Check for .mp4 version if we have .ts
                    elif file_path_obj.suffix == ".ts":
                        mp4_version = file_path_obj.with_suffix(".mp4")
                        if mp4_version.exists():
                            try:
                                validated_mp4 = validate_path_security(str(mp4_version), "delete")
                                files_to_delete.append(validated_mp4)
                            except HTTPException:
                                pass

                    # Check for segment directories (fallback pattern matching)
                    segments_dir = file_path_obj.parent / f"{file_path_obj.stem}_segments"
                    if segments_dir.exists() and segments_dir.is_dir():
                        try:
                            validated_segments = validate_path_security(str(segments_dir), "access")
                            files_to_delete.append(validated_segments)
                        except HTTPException:
                            pass

                except HTTPException as e:
                    logger.warning(f"🚨 SECURITY: Skipping invalid recording path {recording.path}: {e.detail}")
                    continue

            # Delete recording record
            db.delete(recording)

        # Also check the stream's recording_path
        if stream.recording_path:
            try:
                validated_stream_path = validate_path_security(stream.recording_path, "delete")
                files_to_delete.append(validated_stream_path)

                stream_file = Path(validated_stream_path)

                # Check for .ts version if we have .mp4
                if stream_file.suffix == ".mp4":
                    ts_version = stream_file.with_suffix(".ts")
                    if ts_version.exists():
                        try:
                            validated_ts = validate_path_security(str(ts_version), "delete")
                            files_to_delete.append(validated_ts)
                        except HTTPException:
                            pass

                # Check for .mp4 version if we have .ts
                elif stream_file.suffix == ".ts":
                    mp4_version = stream_file.with_suffix(".mp4")
                    if mp4_version.exists():
                        try:
                            validated_mp4 = validate_path_security(str(mp4_version), "delete")
                            files_to_delete.append(validated_mp4)
                        except HTTPException:
                            pass

                # Check for segment directories
                segments_dir = stream_file.parent / f"{stream_file.stem}_segments"
                if segments_dir.exists() and segments_dir.is_dir():
                    try:
                        validated_segments = validate_path_security(str(segments_dir), "access")
                        files_to_delete.append(validated_segments)
                    except HTTPException:
                        pass

            except HTTPException as e:
                logger.warning(
                    f"🚨 SECURITY: Skipping invalid stream recording path {stream.recording_path}: {e.detail}"
                )

        # Delete all stream events for this stream
        db.query(StreamEvent).filter(StreamEvent.stream_id == stream.id).delete()

        # Delete active recording state for this stream
        db.query(ActiveRecordingState).filter(ActiveRecordingState.stream_id == stream.id).delete()

        # Delete the stream record itself
        db.delete(stream)

        # Commit all database deletions
        db.commit()

        # Schedule file deletion in background (includes empty directory cleanup)
        if files_to_delete:
            # Remove duplicates while preserving order
            unique_files = list(dict.fromkeys(files_to_delete))

            background_queue = background_queue_service
            await background_queue.enqueue_task(
                "cleanup",
                {
                    "cleanup_paths": unique_files,
                    "stream_id": stream_id,
                    "directories_to_check": list(directories_to_check),
                },
            )

        return {
            "success": True,
            "message": f"Stream {stream_id} deleted successfully",
            "deleted_files_count": len(unique_files) if files_to_delete else 0,
        }

    except Exception as e:
        logger.error(f"Error deleting stream {stream_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete stream. Please try again.")
