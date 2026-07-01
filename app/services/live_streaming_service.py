"""
Live Streaming Service for StreamVault.

Enables direct live streaming from Twitch to the browser via HLS.
Uses Streamlink -> FFmpeg -> HLS segments pipeline.

Architecture:
    1. User clicks "Watch Live" on a streamer card
    2. Backend starts Streamlink with --stdout (no file output)
    3. FFmpeg reads MPEG-TS from stdin and generates HLS segments
    4. Segments are served via FastAPI static file endpoints
    5. Browser plays via hls.js or native HLS support

Features:
    - Automatic Twitch OAuth token injection (via TwitchTokenService)
    - Dynamic proxy selection (via ProxyHealthService)
    - H.265/AV1 codec support when token is available
    - Auto-cleanup on stop or timeout
    - Concurrent stream limiting (per user + global)
"""

import asyncio
import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

from app.database import SessionLocal
from app.services.proxy.proxy_health_service import proxy_health_service
from app.services.system.twitch_token_service import TwitchTokenService
from app.utils.streamlink_utils import _add_proxy_settings

logger = logging.getLogger("streamvault")


class LiveStreamSession:
    """Represents an active live streaming session"""

    def __init__(
        self,
        session_id: str,
        streamer_name: str,
        quality: str,
        streamlink_process: asyncio.subprocess.Process,
        ffmpeg_process: asyncio.subprocess.Process,
        output_dir: Path,
        user_id: Optional[str] = None,
    ):
        self.session_id = session_id
        self.streamer_name = streamer_name
        self.quality = quality
        self.streamlink_process = streamlink_process
        self.ffmpeg_process = ffmpeg_process
        self.output_dir = output_dir
        self.user_id = user_id
        self.created_at = datetime.utcnow()
        self.last_accessed = datetime.utcnow()
        self.is_active = True

    def touch(self):
        """Update last accessed timestamp"""
        self.last_accessed = datetime.utcnow()

    @property
    def playlist_path(self) -> Path:
        return self.output_dir / "playlist.m3u8"

    def is_expired(self, timeout_seconds: int = 60) -> bool:
        """Check if session has timed out due to inactivity"""
        return (
            datetime.utcnow() - self.last_accessed
        ).total_seconds() > timeout_seconds


class LiveStreamingService:
    """Service for managing live streaming sessions"""

    # Session timeout - auto-cleanup after X seconds of inactivity
    SESSION_TIMEOUT_SECONDS = 60

    # Global maximum concurrent live streams
    MAX_CONCURRENT_STREAMS = 5

    # Segment duration in seconds for HLS
    HLS_SEGMENT_DURATION = 2

    # Playlist window size (number of segments)
    HLS_LIST_SIZE = 10

    def __init__(self):
        self.sessions: Dict[str, LiveStreamSession] = {}
        self.user_sessions: Dict[str, Set[str]] = {}  # user_id -> set of session_ids
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the background cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Live streaming cleanup task started")

    async def stop(self):
        """Stop all active streams and cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Stop all active sessions
        async with self._lock:
            session_ids = list(self.sessions.keys())

        for session_id in session_ids:
            await self.stop_stream(session_id)

        logger.info("Live streaming service stopped")

    async def start_stream(
        self,
        streamer_name: str,
        quality: str = "best",
        user_id: Optional[str] = None,
    ) -> str:
        """
        Start a new live streaming session.

        Args:
            streamer_name: Twitch username to stream
            quality: Stream quality (best, 1080p, 720p, etc.)
            user_id: Optional user ID for session tracking

        Returns:
            session_id: Unique identifier for this streaming session

        Raises:
            RuntimeError: If max concurrent streams reached or stream start fails
        """
        async with self._lock:
            # Check global concurrent limit
            active_count = sum(1 for s in self.sessions.values() if s.is_active)
            if active_count >= self.MAX_CONCURRENT_STREAMS:
                raise RuntimeError(
                    f"Maximum concurrent streams reached"
                    f" ({self.MAX_CONCURRENT_STREAMS})."
                    " Please stop another stream first."
                )

            # Limit per-user concurrent streams
            if user_id:
                user_stream_count = len(self.user_sessions.get(user_id, set()))
                if user_stream_count >= 2:
                    raise RuntimeError(
                        "Maximum 2 concurrent streams per user."
                        " Please stop another stream first."
                    )

        # Verify FFmpeg is available before starting anything
        ffmpeg_bin = os.environ.get("FFMPEG_PATH") or "ffmpeg"
        if shutil.which(ffmpeg_bin) is None:
            raise RuntimeError(
                f"FFmpeg not found at '{ffmpeg_bin}'. Live streaming unavailable."
            )

        # Generate unique session ID
        session_id = str(uuid.uuid4())[:8]

        # Create output directory for HLS segments
        output_dir = Path(f"/tmp/streamvault-live/{session_id}")
        output_dir.mkdir(parents=True, exist_ok=True)

        streamlink_process = None
        ffmpeg_process = None
        try:
            # Get fresh OAuth token and proxy settings
            streamlink_cmd = await self._build_streamlink_command(
                streamer_name, quality
            )

            # Build FFmpeg HLS command
            ffmpeg_cmd = self._build_ffmpeg_command(output_dir)

            logger.info(
                f"[LIVE] Starting stream session {session_id} for {streamer_name} "
                f"(quality: {quality})"
            )

            # Start FFmpeg first (reads from stdin)
            ffmpeg_process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )

            # Start Streamlink with stdout captured
            streamlink_process = await asyncio.create_subprocess_exec(
                *streamlink_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Start background stderr loggers so we can diagnose failures
            asyncio.create_task(
                self._log_stderr(streamlink_process, f"streamlink-{session_id}")
            )
            asyncio.create_task(
                self._log_stderr(ffmpeg_process, f"ffmpeg-{session_id}")
            )

            # Start piping data from streamlink stdout -> ffmpeg stdin
            asyncio.create_task(
                self._pipe_streamlink_to_ffmpeg(streamlink_process, ffmpeg_process)
            )

            # Wait for the HLS playlist to appear (with timeout)
            playlist_path = output_dir / "playlist.m3u8"
            playlist_ready = await self._wait_for_playlist(playlist_path, timeout=15)

            if not playlist_ready:
                # Check if processes already died
                sl_code = streamlink_process.returncode
                ff_code = ffmpeg_process.returncode
                if sl_code is not None or ff_code is not None:
                    raise RuntimeError(
                        f"Streamlink/FFmpeg exited early (sl={sl_code}, ff={ff_code}). "
                        "Streamer may be offline or stream is geo-blocked."
                    )
                raise RuntimeError(
                    "HLS playlist did not appear within timeout. "
                    "Streamer may be offline or stream is not accessible."
                )

            # Create session
            session = LiveStreamSession(
                session_id=session_id,
                streamer_name=streamer_name,
                quality=quality,
                streamlink_process=streamlink_process,
                ffmpeg_process=ffmpeg_process,
                output_dir=output_dir,
                user_id=user_id,
            )

            async with self._lock:
                self.sessions[session_id] = session
                if user_id:
                    if user_id not in self.user_sessions:
                        self.user_sessions[user_id] = set()
                    self.user_sessions[user_id].add(session_id)

            # Start background monitoring
            asyncio.create_task(self._monitor_session(session_id))

            logger.info(f"[LIVE] Session {session_id} started successfully")
            return session_id

        except Exception:
            # Cleanup on any failure
            if streamlink_process and streamlink_process.returncode is None:
                streamlink_process.kill()
            if ffmpeg_process and ffmpeg_process.returncode is None:
                ffmpeg_process.kill()
            shutil.rmtree(output_dir, ignore_errors=True)
            raise

    async def _wait_for_playlist(self, playlist_path: Path, timeout: int = 15) -> bool:
        """Poll until the HLS playlist file exists or timeout is reached."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if playlist_path.exists() and playlist_path.stat().st_size > 0:
                return True
            await asyncio.sleep(0.5)
        return False

    async def _log_stderr(
        self,
        process: asyncio.subprocess.Process,
        name: str,
    ):
        """Read stderr from a subprocess and log it for diagnostics."""
        if not process.stderr:
            return
        try:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    logger.debug(f"[LIVE][{name}] {text}")
        except Exception as e:
            logger.debug(f"[LIVE][{name}] stderr logger ended: {e}")

    async def stop_stream(self, session_id: str) -> bool:
        """
        Stop a live streaming session and cleanup resources.

        Args:
            session_id: The session to stop

        Returns:
            True if session was stopped, False if not found
        """
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False

        logger.info(f"[LIVE] Stopping session {session_id} ({session.streamer_name})")

        # Mark as inactive
        session.is_active = False

        # Terminate processes gracefully
        for proc, name in [
            (session.streamlink_process, "streamlink"),
            (session.ffmpeg_process, "ffmpeg"),
        ]:
            if proc and proc.returncode is None:
                try:
                    proc.terminate()
                    # Wait up to 5 seconds for graceful shutdown
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"[LIVE] {name} process did not terminate"
                            " gracefully, killing..."
                        )
                        proc.kill()
                        await proc.wait()
                except Exception as e:
                    logger.error(f"[LIVE] Error stopping {name}: {e}")

        # Cleanup files
        try:
            if session.output_dir.exists():
                shutil.rmtree(session.output_dir, ignore_errors=True)
                logger.debug(f"[LIVE] Cleaned up output directory for {session_id}")
        except Exception as e:
            logger.error(f"[LIVE] Error cleaning up session {session_id}: {e}")

        # Remove from tracking
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
            if session.user_id and session.user_id in self.user_sessions:
                self.user_sessions[session.user_id].discard(session_id)

        logger.info(f"[LIVE] Session {session_id} stopped and cleaned up")
        return True

    def get_session(self, session_id: str) -> Optional[LiveStreamSession]:
        """Get a session by ID and update its access time"""
        session = self.sessions.get(session_id)
        if session and session.is_active:
            session.touch()
            return session
        return None

    def get_session_status(self, session_id: str) -> Optional[dict]:
        """Get current status of a streaming session"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "streamer_name": session.streamer_name,
            "quality": session.quality,
            "is_active": session.is_active,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "playlist_url": f"/api/live/stream/{session_id}/playlist.m3u8",
        }

    async def _build_streamlink_command(self, streamer_name: str, quality: str) -> list:
        """Build Streamlink command for live streaming (no file output)"""
        cmd = [
            "streamlink",
            "--config",
            "/app/config/streamlink/config.twitch",
            f"twitch.tv/{streamer_name}",
            quality,
            "--stdout",  # Output to stdout instead of file
        ]

        # Get fresh OAuth token
        with SessionLocal() as db:
            token_service = TwitchTokenService(db)
            oauth_token = await token_service.get_valid_access_token()

            if oauth_token:
                token_header = f"Authorization=OAuth {oauth_token.strip()}"
                cmd.append(f"--twitch-api-header={token_header}")
                logger.debug("[LIVE] Using OAuth token for stream")

            # Get proxy settings from health service
            try:
                proxy_url = await proxy_health_service.get_best_proxy()
                if proxy_url:
                    proxy_settings = {"http": proxy_url, "https": proxy_url}
                    cmd = _add_proxy_settings(cmd, proxy_settings, force_mode=False)
                    logger.debug(f"[LIVE] Using proxy: {proxy_url}")
            except Exception as e:
                logger.warning(f"[LIVE] Could not get proxy: {e}")

        return cmd

    def _build_ffmpeg_command(self, output_dir: Path) -> list:
        """Build FFmpeg command for HLS generation from stdin"""
        ffmpeg_bin = os.environ.get("FFMPEG_PATH") or "ffmpeg"

        playlist_path = output_dir / "playlist.m3u8"

        return [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "-",  # Read from stdin
            "-c",
            "copy",  # Copy streams without re-encoding
            "-f",
            "hls",
            "-hls_time",
            str(self.HLS_SEGMENT_DURATION),
            "-hls_list_size",
            str(self.HLS_LIST_SIZE),
            "-hls_flags",
            "delete_segments+omit_endlist",
            "-hls_segment_filename",
            str(output_dir / "segment_%03d.ts"),
            str(playlist_path),
        ]

    async def _pipe_streamlink_to_ffmpeg(
        self,
        streamlink_process: asyncio.subprocess.Process,
        ffmpeg_process: asyncio.subprocess.Process,
    ):
        """Pipe data from Streamlink stdout to FFmpeg stdin"""
        try:
            if streamlink_process.stdout and ffmpeg_process.stdin:
                while True:
                    chunk = await streamlink_process.stdout.read(65536)
                    if not chunk:
                        break
                    ffmpeg_process.stdin.write(chunk)
                    await ffmpeg_process.stdin.drain()
                ffmpeg_process.stdin.close()
        except Exception as e:
            logger.error(f"[LIVE] Error piping streamlink to ffmpeg: {e}")

    async def _monitor_session(self, session_id: str):
        """Monitor a session and auto-cleanup if processes die"""
        try:
            session = self.sessions.get(session_id)
            if not session:
                return

            # Wait for either process to exit
            while session.is_active:
                # Check if processes are still running
                streamlink_done = session.streamlink_process.returncode is not None
                ffmpeg_done = session.ffmpeg_process.returncode is not None

                if streamlink_done or ffmpeg_done:
                    logger.info(
                        f"[LIVE] Process exited for session {session_id}, "
                        f"cleaning up..."
                    )
                    await self.stop_stream(session_id)
                    break

                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"[LIVE] Error monitoring session {session_id}: {e}")
            await self.stop_stream(session_id)

    async def _cleanup_loop(self):
        """Background task to cleanup expired/inactive sessions"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                expired_sessions = []
                async with self._lock:
                    for session_id, session in self.sessions.items():
                        if session.is_expired(self.SESSION_TIMEOUT_SECONDS):
                            expired_sessions.append(session_id)

                for session_id in expired_sessions:
                    logger.info(
                        f"[LIVE] Session {session_id} expired due to inactivity"
                    )
                    await self.stop_stream(session_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[LIVE] Error in cleanup loop: {e}")


# Global service instance
live_streaming_service = LiveStreamingService()
