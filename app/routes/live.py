"""
Live Streaming API Routes

Provides endpoints for starting, stopping, and serving live HLS streams.

Endpoints:
    POST /api/live/start/{streamer_name}  - Start a live stream
    DELETE /api/live/stop/{session_id}     - Stop a live stream
    GET /api/live/status/{session_id}      - Get stream status
    GET /api/live/stream/{session_id}/playlist.m3u8  - HLS playlist
    GET /api/live/stream/{session_id}/{segment}      - HLS segment
"""

import logging
import os
from pathlib import Path

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Request,
    Response,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Streamer, User
from app.services.live_streaming_service import live_streaming_service

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api/live", tags=["live"])


@router.post("/start/{streamer_name}")
async def start_live_stream(
    streamer_name: str,
    request: Request,
    quality: str = "best",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start a live streaming session for a streamer.

    Args:
        streamer_name: Twitch username
        quality: Stream quality (best, 1080p60, 720p60, etc.)

    Returns:
        {"session_id": str, "playlist_url": str, "streamer_name": str}
    """
    try:
        # Verify streamer exists
        streamer = db.query(Streamer).filter(Streamer.username == streamer_name).first()
        if not streamer:
            raise HTTPException(status_code=404, detail=f"Streamer '{streamer_name}' not found")

        # Start the streaming service if not already running
        await live_streaming_service.start()

        # Start stream
        user_id = str(current_user.id) if current_user else None
        session_id = await live_streaming_service.start_stream(
            streamer_name=streamer_name,
            quality=quality,
            user_id=user_id,
        )

        playlist_url = f"/api/live/stream/{session_id}/playlist.m3u8"

        logger.info(f"[LIVE] Stream started by user {user_id}: {session_id} ({streamer_name})")

        return {
            "success": True,
            "session_id": session_id,
            "streamer_name": streamer_name,
            "quality": quality,
            "playlist_url": playlist_url,
            "message": "Stream started successfully",
        }

    except RuntimeError as e:
        logger.warning(f"[LIVE] Failed to start stream for {streamer_name}: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.error(f"[LIVE] Error starting stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start stream: {e}")


@router.delete("/stop/{session_id}")
async def stop_live_stream(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Stop a live streaming session.

    Args:
        session_id: The streaming session ID

    Returns:
        {"success": bool, "message": str}
    """
    try:
        # Verify ownership (optional - can skip for simplicity)
        session = live_streaming_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found or already stopped")

        success = await live_streaming_service.stop_stream(session_id)

        if success:
            return {
                "success": True,
                "message": f"Stream session {session_id} stopped successfully",
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LIVE] Error stopping stream: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop stream: {e}")


@router.get("/status/{session_id}")
async def get_stream_status(session_id: str):
    """
    Get the status of a live streaming session.

    Returns:
        {"session_id": str, "streamer_name": str, "is_active": bool, ...}
    """
    status = live_streaming_service.get_session_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail="Session not found")
    return status


@router.get("/stream/{session_id}/playlist.m3u8")
async def get_hls_playlist(session_id: str):
    """
    Serve the HLS playlist (.m3u8) for a live stream.

    This is the entry point for the video player.
    """
    try:
        session = live_streaming_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Stream session not found")

        playlist_path = session.playlist_path

        # Wait a moment for playlist to be created
        if not playlist_path.exists():
            import asyncio
            await asyncio.sleep(0.5)

        if not playlist_path.exists():
            raise HTTPException(status_code=503, detail="Stream not ready yet, retry shortly")

        # Update access time
        session.touch()

        # Serve with appropriate HLS headers
        return FileResponse(
            path=str(playlist_path),
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LIVE] Error serving playlist: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve playlist")


@router.get("/stream/{session_id}/{segment_name}")
async def get_hls_segment(session_id: str, segment_name: str):
    """
    Serve an HLS segment (.ts file) for a live stream.

    Args:
        session_id: The streaming session ID
        segment_name: Segment filename (e.g., segment_000.ts)
    """
    try:
        session = live_streaming_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Stream session not found")

        segment_path = session.output_dir / segment_name

        if not segment_path.exists():
            raise HTTPException(status_code=404, detail="Segment not found")

        # Update access time
        session.touch()

        return FileResponse(
            path=str(segment_path),
            media_type="video/mp2t",
            headers={
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LIVE] Error serving segment: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve segment")


@router.get("/active")
async def get_active_streams(current_user: User = Depends(get_current_user)):
    """
    Get all active live streams for the current user.

    Returns:
        {"streams": [{"session_id", "streamer_name", "quality", "playlist_url", ...}]}
    """
    try:
        user_id = str(current_user.id) if current_user else None
        streams = []

        for session_id, session in live_streaming_service.sessions.items():
            if session.user_id == user_id or user_id is None:
                streams.append({
                    "session_id": session.session_id,
                    "streamer_name": session.streamer_name,
                    "quality": session.quality,
                    "playlist_url": f"/api/live/stream/{session_id}/playlist.m3u8",
                    "is_active": session.is_active,
                    "created_at": session.created_at.isoformat(),
                })

        return {"streams": streams}

    except Exception as e:
        logger.error(f"[LIVE] Error getting active streams: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active streams")
