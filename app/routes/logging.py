from fastapi import APIRouter, HTTPException, Query, Response
import logging
from datetime import datetime

from app.services.system.logging_service import logging_service
from app.schemas.logging import LogsListSchema, LogFileSchema

router = APIRouter(prefix="/logging", tags=["logging"])
logger = logging.getLogger("streamvault")


@router.get("/files", response_model=LogsListSchema)
async def list_log_files():
    """List all available log files"""
    try:
        streamlink_logs = []
        ffmpeg_logs = []
        app_logs = []
        total_size = 0

        # Get streamlink logs
        if logging_service.streamlink_logs_dir.exists():
            for log_file in logging_service.streamlink_logs_dir.glob("*.log*"):
                if log_file.is_file():
                    stat = log_file.stat()
                    streamlink_logs.append(LogFileSchema(
                        filename=log_file.name,
                        size=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        type="streamlink"
                    ))
                    total_size += stat.st_size

        # Get FFmpeg logs
        if logging_service.ffmpeg_logs_dir.exists():
            for log_file in logging_service.ffmpeg_logs_dir.glob("*.log*"):
                if log_file.is_file():
                    stat = log_file.stat()
                    ffmpeg_logs.append(LogFileSchema(
                        filename=log_file.name,
                        size=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        type="ffmpeg"
                    ))
                    total_size += stat.st_size

        # Get app logs
        if logging_service.app_logs_dir.exists():
            for log_file in logging_service.app_logs_dir.glob("*.log*"):
                if log_file.is_file():
                    stat = log_file.stat()
                    app_logs.append(LogFileSchema(
                        filename=log_file.name,
                        size=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        type="app"
                    ))
                    total_size += stat.st_size

        # Sort by last modified (newest first)
        streamlink_logs.sort(key=lambda x: x.last_modified, reverse=True)
        ffmpeg_logs.sort(key=lambda x: x.last_modified, reverse=True)
        app_logs.sort(key=lambda x: x.last_modified, reverse=True)

        return LogsListSchema(
            streamlink_logs=streamlink_logs,
            ffmpeg_logs=ffmpeg_logs,
            app_logs=app_logs,
            total_size=total_size
        )

    except Exception as e:
        logger.error(f"Error listing log files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{log_type}/{filename}")
async def download_log_file(log_type: str, filename: str):
    """Download a specific log file"""
    try:
        # Validate log type
        if log_type not in ["streamlink", "ffmpeg", "app"]:
            raise HTTPException(status_code=400, detail="Invalid log type")

        # Get the appropriate directory
        if log_type == "streamlink":
            log_dir = logging_service.streamlink_logs_dir
        elif log_type == "ffmpeg":
            log_dir = logging_service.ffmpeg_logs_dir
        else:
            log_dir = logging_service.app_logs_dir

        # Security check: ensure filename doesn't contain path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        log_file_path = log_dir / filename

        if not log_file_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")

        # Read the file content
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        return Response(
            content=content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading log file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{log_type}/{filename}/tail")
async def tail_log_file(
    log_type: str,
    filename: str,
    lines: int = Query(100, description="Number of lines to return", ge=1, le=10000)
):
    """Get the last N lines of a log file"""
    try:
        # Validate log type
        if log_type not in ["streamlink", "ffmpeg", "app"]:
            raise HTTPException(status_code=400, detail="Invalid log type")

        # Get the appropriate directory
        if log_type == "streamlink":
            log_dir = logging_service.streamlink_logs_dir
        elif log_type == "ffmpeg":
            log_dir = logging_service.ffmpeg_logs_dir
        else:
            log_dir = logging_service.app_logs_dir

        # Security check: ensure filename doesn't contain path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        log_file_path = log_dir / filename

        if not log_file_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")

        # Read the last N lines
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        return {
            "filename": filename,
            "lines_requested": lines,
            "lines_returned": len(last_lines),
            "total_lines": len(all_lines),
            "content": "".join(last_lines)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tailing log file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{log_type}/{filename}")
async def delete_log_file(log_type: str, filename: str):
    """Delete a specific log file"""
    try:
        # Validate log type
        if log_type not in ["streamlink", "ffmpeg", "app"]:
            raise HTTPException(status_code=400, detail="Invalid log type")

        # Get the appropriate directory
        if log_type == "streamlink":
            log_dir = logging_service.streamlink_logs_dir
        elif log_type == "ffmpeg":
            log_dir = logging_service.ffmpeg_logs_dir
        else:
            log_dir = logging_service.app_logs_dir

        # Security check: ensure filename doesn't contain path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        log_file_path = log_dir / filename

        if not log_file_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")

        # Delete the file
        log_file_path.unlink()
        logger.info(f"Deleted log file: {log_file_path}")

        return {"status": "success", "message": f"Log file {filename} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting log file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_old_logs(days_to_keep: int = Query(30, description="Days of logs to keep", ge=1, le=365)):
    """Clean up log files older than specified days"""
    try:
        logging_service.cleanup_old_logs(days_to_keep)
        return {"status": "success", "message": f"Cleaned up logs older than {days_to_keep} days"}

    except Exception as e:
        logger.error(f"Error cleaning up logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_logging_stats():
    """Get logging statistics"""
    try:
        stats = {
            "streamlink": {"count": 0, "total_size": 0},
            "ffmpeg": {"count": 0, "total_size": 0},
            "app": {"count": 0, "total_size": 0}
        }

        # Count streamlink logs
        if logging_service.streamlink_logs_dir.exists():
            for log_file in logging_service.streamlink_logs_dir.glob("*.log*"):
                if log_file.is_file():
                    stats["streamlink"]["count"] += 1
                    stats["streamlink"]["total_size"] += log_file.stat().st_size

        # Count FFmpeg logs
        if logging_service.ffmpeg_logs_dir.exists():
            for log_file in logging_service.ffmpeg_logs_dir.glob("*.log*"):
                if log_file.is_file():
                    stats["ffmpeg"]["count"] += 1
                    stats["ffmpeg"]["total_size"] += log_file.stat().st_size

        # Count app logs
        if logging_service.app_logs_dir.exists():
            for log_file in logging_service.app_logs_dir.glob("*.log*"):
                if log_file.is_file():
                    stats["app"]["count"] += 1
                    stats["app"]["total_size"] += log_file.stat().st_size

        return stats

    except Exception as e:
        logger.error(f"Error getting logging stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
