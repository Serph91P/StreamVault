import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bootstrap.settings import resolve_app_settings
from app.dependencies import get_db, require_scopes
from app.models import (
    ActiveRecordingState,
    Recording,
    Stream,
    StreamEvent,
    StreamMetadata,
)
from app.services.recording.recording_cleanup import CleanupRefused, delete_stream_files

logger = logging.getLogger("streamvault")
router = APIRouter(prefix="/api/streams", tags=["streams"])


def delete_catalog_stream(
    request: Request, db: Session, stream_id: int, *, streamer_id: int | None = None
) -> dict:
    try:
        if db.get_bind().dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        statement = select(Stream).where(Stream.id == stream_id).with_for_update()
        if streamer_id is not None:
            statement = statement.where(Stream.streamer_id == streamer_id)
        stream = db.scalar(statement)
        if stream is None:
            raise HTTPException(status_code=404, detail="Stream not found")

        # This explicit request owns the delete authority. No queued path list can
        # outlive the catalog proof or acquire authority over final media.
        root = Path(resolve_app_settings(request.app).RECORDING_DIRECTORY)
        removed = delete_stream_files(db, root, stream.id)
        for model in (StreamEvent, ActiveRecordingState, StreamMetadata, Recording):
            db.query(model).filter(model.stream_id == stream.id).delete()
        db.delete(stream)
        db.commit()
        result = {
            "success": True,
            "message": f"Stream {stream_id} deleted successfully",
            "deleted_files_count": len(removed),
        }
        if streamer_id is not None:
            result["deleted_files"] = [str(path) for path in removed]
        return result
    except HTTPException:
        raise
    except (CleanupRefused, OSError) as error:
        db.rollback()
        logger.warning(
            "Recording files for stream %s could not be safely removed", stream_id
        )
        raise HTTPException(
            status_code=409, detail="Recording files could not be safely removed"
        ) from error
    except Exception as error:
        db.rollback()
        logger.exception("Error deleting stream %s", stream_id)
        raise HTTPException(
            status_code=500, detail="Failed to delete stream. Please try again."
        ) from error


@router.delete(
    "/{stream_id}", dependencies=[Depends(require_scopes("recording:write"))]
)
def delete_stream(request: Request, stream_id: int, db: Session = Depends(get_db)):
    """Permanently delete this stream and its exclusively owned files."""
    return delete_catalog_stream(request, db, stream_id)
