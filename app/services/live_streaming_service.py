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
import secrets
import signal
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

from app.database import SessionLocal
from app.services.proxy.proxy_health_service import proxy_health_service
from app.services.system.twitch_token_service import TwitchTokenService
from app.services.twitch_upstream_coordinator import (
    AUTHENTICATED_TWITCH_ACCOUNT,
    TwitchUpstreamConflict,
    twitch_upstream_coordinator,
)
from app.utils.security import sanitize_proxy_url_for_logging
from app.utils.streamlink_utils import _add_proxy_settings

logger = logging.getLogger("streamvault")


@dataclass(frozen=True)
class LiveStreamStartResult:
    session_id: str
    idempotent: bool


class TwitchUpstreamStopForbidden(PermissionError):
    pass


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
        channel_key: Optional[str] = None,
        enhanced_quality: bool = False,
        lease_generation: Optional[int] = None,
        process_group_id: Optional[int] = None,
        process_started_at: Optional[datetime] = None,
        process_start_fingerprint: Optional[str] = None,
        ffmpeg_process_group_id: Optional[int] = None,
        ffmpeg_process_start_fingerprint: Optional[str] = None,
    ):
        self.session_id = session_id
        self.streamer_name = streamer_name
        self.quality = quality
        self.streamlink_process = streamlink_process
        self.ffmpeg_process = ffmpeg_process
        self.output_dir = output_dir
        self.user_id = user_id
        self.channel_key = channel_key
        self.enhanced_quality = enhanced_quality
        self.lease_generation = lease_generation
        self.process_group_id = process_group_id
        self.process_started_at = process_started_at
        self.process_start_fingerprint = process_start_fingerprint
        self.ffmpeg_process_group_id = ffmpeg_process_group_id
        self.ffmpeg_process_start_fingerprint = ffmpeg_process_start_fingerprint
        self.playback_token = secrets.token_urlsafe(32)
        self.created_at = datetime.utcnow()
        self.last_accessed = datetime.utcnow()
        self.is_active = True

    def touch(self):
        """Update last accessed timestamp"""
        self.last_accessed = datetime.utcnow()

    @property
    def playlist_path(self) -> Path:
        return self.output_dir / "playlist.m3u8"

    def validate_playback_token(self, token: Optional[str]) -> bool:
        """Validate the bearer token used by native HLS/video requests."""
        return bool(token) and secrets.compare_digest(token, self.playback_token)

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

    def __init__(self, coordinator=None, output_root=None):
        self.sessions: Dict[str, LiveStreamSession] = {}
        self.user_sessions: Dict[str, Set[str]] = {}  # user_id -> set of session_ids
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._coordinator = coordinator or twitch_upstream_coordinator
        self._output_root = Path(output_root or "/tmp/streamvault-live")
        self._pending_starts: Dict[tuple, asyncio.Future] = {}

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
            try:
                await self.stop_stream(session_id)
            except PermissionError:
                logger.warning(
                    "[LIVE] Session %s was fenced during shutdown", session_id
                )

        logger.info("Live streaming service stopped")

    async def start_stream(
        self,
        streamer_name: str,
        channel_key: Optional[str] = None,
        quality: str = "best",
        supported_codecs: str = "h264",
        user_id: Optional[str] = None,
        enhanced_quality: bool = False,
        replace_existing: bool = False,
    ) -> LiveStreamStartResult:
        channel_key = channel_key or streamer_name.strip().casefold()
        owner_user_id = int(user_id) if user_id is not None else None
        auth_key = AUTHENTICATED_TWITCH_ACCOUNT if enhanced_quality else None
        start_key = (channel_key, owner_user_id, auth_key)

        async with self._lock:
            pending = self._pending_starts.get(start_key)
            is_owner = pending is None
            if pending is None:
                pending = asyncio.get_running_loop().create_future()
                pending.add_done_callback(
                    lambda done: None if done.cancelled() else done.exception()
                )
                self._pending_starts[start_key] = pending

        if not is_owner:
            result = await asyncio.shield(pending)
            return LiveStreamStartResult(result.session_id, True)

        try:
            result = await self._start_stream_once(
                streamer_name=streamer_name,
                channel_key=channel_key,
                quality=quality,
                supported_codecs=supported_codecs,
                user_id=user_id,
                enhanced_quality=enhanced_quality,
                replace_existing=replace_existing,
            )
        except BaseException as error:
            if isinstance(error, asyncio.CancelledError):
                pending.cancel()
            else:
                pending.set_exception(error)
            raise
        else:
            pending.set_result(result)
            return result
        finally:
            async with self._lock:
                if self._pending_starts.get(start_key) is pending:
                    self._pending_starts.pop(start_key)

    async def _start_stream_once(
        self,
        streamer_name: str,
        channel_key: Optional[str] = None,
        quality: str = "best",
        supported_codecs: str = "h264",
        user_id: Optional[str] = None,
        enhanced_quality: bool = False,
        replace_existing: bool = False,
    ) -> LiveStreamStartResult:
        """
        Start a new live streaming session.

        Args:
            streamer_name: Twitch username to stream
            quality: Stream quality (best, 1080p, 720p, etc.)
            supported_codecs: Comma-separated Twitch codecs supported by the player
            user_id: Optional user ID for session tracking
            replace_existing: Stop an existing live session for the same user/streamer

        Returns:
            session_id: Unique identifier for this streaming session

        Raises:
            RuntimeError: If max concurrent streams reached or stream start fails
        """
        # Verify FFmpeg is available before starting anything
        ffmpeg_bin = os.environ.get("FFMPEG_PATH") or "ffmpeg"
        if shutil.which(ffmpeg_bin) is None:
            raise RuntimeError(
                f"FFmpeg not found at '{ffmpeg_bin}'. Live streaming unavailable."
            )

        # Generate unique session ID
        session_id = str(uuid.uuid4())[:8]
        channel_key = channel_key or streamer_name.strip().casefold()
        auth_key = AUTHENTICATED_TWITCH_ACCOUNT if enhanced_quality else None
        reservation = await self._coordinator.reserve(
            channel_key=channel_key,
            auth_key=auth_key,
            purpose="LIVE",
            owner_user_id=int(user_id) if user_id is not None else None,
            live_session_id=session_id,
        )
        if reservation.live_session_id != session_id:
            existing = self.sessions.get(reservation.live_session_id)
            if existing and existing.is_active:
                return LiveStreamStartResult(existing.session_id, True)
            raise TwitchUpstreamConflict(
                "twitch_upstream_channel_conflict",
                "active_live_session_not_local",
                channel_key,
            )

        # Create output directory for HLS segments
        output_dir = self._output_root / session_id

        streamlink_process = None
        streamlink_identity = None
        ffmpeg_process = None
        ffmpeg_identity = None
        active_lease = None
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            # Get fresh OAuth token and proxy settings
            streamlink_cmd = await self._build_streamlink_command(
                streamer_name,
                quality,
                supported_codecs=supported_codecs,
                enhanced_quality=enhanced_quality,
            )

            # Build FFmpeg HLS command
            ffmpeg_cmd = self._build_ffmpeg_command(output_dir)

            logger.info(
                f"[LIVE] Starting stream session {session_id} for {streamer_name} "
                f"(quality: {quality}, codecs: "
                f"{self._normalize_supported_codecs(supported_codecs)})"
            )

            # Start FFmpeg first (reads from stdin)
            ffmpeg_process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            identity_task = asyncio.create_task(
                self._coordinator.inspect_process_identity(ffmpeg_process.pid)
            )
            try:
                ffmpeg_identity = await asyncio.shield(identity_task)
            except asyncio.CancelledError:
                ffmpeg_identity = await identity_task
                raise

            # Start Streamlink with stdout captured
            streamlink_process = await asyncio.create_subprocess_exec(
                *streamlink_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            identity_task = asyncio.create_task(
                self._coordinator.inspect_process_identity(streamlink_process.pid)
            )
            try:
                streamlink_identity = await asyncio.shield(identity_task)
            except asyncio.CancelledError:
                streamlink_identity = await identity_task
                raise
            activation = asyncio.create_task(
                self._coordinator.activate(
                    channel_key=channel_key,
                    generation=reservation.generation,
                    process_pid=streamlink_process.pid,
                    process_group_id=streamlink_identity.process_group_id,
                    process_started_at=streamlink_identity.started_at,
                    process_start_fingerprint=streamlink_identity.fingerprint,
                )
            )
            try:
                active_lease = await asyncio.shield(activation)
            except asyncio.CancelledError:
                active_lease = await activation
                raise

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
                channel_key=channel_key,
                enhanced_quality=enhanced_quality,
                lease_generation=reservation.generation,
                process_group_id=getattr(
                    active_lease,
                    "process_group_id",
                    streamlink_identity.process_group_id,
                ),
                process_started_at=getattr(
                    active_lease,
                    "process_started_at",
                    streamlink_identity.started_at,
                ),
                process_start_fingerprint=getattr(
                    active_lease,
                    "process_start_fingerprint",
                    streamlink_identity.fingerprint,
                ),
                ffmpeg_process_group_id=ffmpeg_identity.process_group_id,
                ffmpeg_process_start_fingerprint=ffmpeg_identity.fingerprint,
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
            return LiveStreamStartResult(session_id, False)

        except BaseException:
            authorized = active_lease is None
            if active_lease is not None:
                try:
                    await self._coordinator.assert_stop_authorized(
                        channel_key=channel_key,
                        generation=reservation.generation,
                        process_pid=streamlink_process.pid,
                        process_group_id=getattr(
                            active_lease,
                            "process_group_id",
                            streamlink_identity.process_group_id,
                        ),
                        process_start_fingerprint=getattr(
                            active_lease, "process_start_fingerprint", ""
                        ),
                        expected_purpose="LIVE",
                        requesting_owner_user_id=(
                            int(user_id) if user_id is not None else None
                        ),
                    )
                    authorized = True
                except PermissionError:
                    authorized = False
            streamlink_reaped = False
            if authorized:
                streamlink_reaped = await self._reap_process(
                    streamlink_process,
                    process_group_id=(
                        getattr(
                            active_lease,
                            "process_group_id",
                            streamlink_identity.process_group_id,
                        )
                        if active_lease is not None
                        else getattr(streamlink_identity, "process_group_id", None)
                    ),
                    process_start_fingerprint=(
                        getattr(
                            active_lease,
                            "process_start_fingerprint",
                            streamlink_identity.fingerprint,
                        )
                        if active_lease is not None
                        else getattr(streamlink_identity, "fingerprint", None)
                    ),
                )
            ffmpeg_reaped = await self._reap_process(
                ffmpeg_process,
                process_group_id=(
                    ffmpeg_identity.process_group_id
                    if ffmpeg_identity is not None
                    else None
                ),
                process_start_fingerprint=(
                    ffmpeg_identity.fingerprint if ffmpeg_identity is not None else None
                ),
            )
            if streamlink_reaped and ffmpeg_reaped:
                await self._coordinator.release(
                    channel_key=channel_key,
                    generation=reservation.generation,
                    reason="live_start_failed",
                )
            shutil.rmtree(output_dir, ignore_errors=True)
            raise

    async def _stop_existing_user_streams(
        self, user_id: str, streamer_name: str
    ) -> None:
        """Stop older sessions for the same user and streamer before replacement."""
        async with self._lock:
            session_ids = [
                session_id
                for session_id, session in self.sessions.items()
                if session.is_active
                and session.user_id == user_id
                and session.streamer_name.lower() == streamer_name.lower()
            ]

        for session_id in session_ids:
            logger.info(
                "[LIVE] Replacing existing session %s for user %s (%s)",
                session_id,
                user_id,
                streamer_name,
            )
            await self.stop_stream(session_id)

    async def _wait_for_playlist(self, playlist_path: Path, timeout: int = 15) -> bool:
        """Poll until the HLS playlist file exists or timeout is reached."""
        logger.info(f"[LIVE] Waiting for HLS playlist to appear: {playlist_path}")
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if playlist_path.exists() and playlist_path.stat().st_size > 0:
                elapsed = timeout - (deadline - asyncio.get_event_loop().time())
                logger.info(f"[LIVE] HLS playlist ready after {elapsed:.1f}s")
                return True
            await asyncio.sleep(0.5)
        logger.warning(
            f"[LIVE] HLS playlist did not appear within {timeout}s: {playlist_path}"
        )
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
                # Drain stderr without copying upstream URLs, headers, or credentials
                # into application diagnostics.
        except Exception as error:
            logger.debug(
                "[LIVE][%s] stderr logger ended (%s)", name, type(error).__name__
            )

    async def stop_stream(
        self, session_id: str, requesting_user_id: Optional[str] = None
    ) -> bool:
        """
        Stop a live streaming session and cleanup resources.

        Args:
            session_id: The session to stop

        Returns:
            True if session was stopped, False if not found
        """
        return await self._stop_session(
            session_id, requesting_user_id=requesting_user_id
        )

    async def _stop_monitored_session(
        self,
        session_id: str,
        monitored_session: LiveStreamSession,
        *,
        leader_exited: bool,
    ) -> bool:
        return await self._stop_session(
            session_id,
            monitored_session=monitored_session,
            leader_exited=leader_exited,
        )

    async def _stop_session(
        self,
        session_id: str,
        requesting_user_id: Optional[str] = None,
        monitored_session: Optional[LiveStreamSession] = None,
        leader_exited: bool = False,
    ) -> bool:
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session or not session.is_active:
                return False
            if monitored_session is not None and session is not monitored_session:
                return False
            if requesting_user_id is not None and session.user_id != requesting_user_id:
                raise TwitchUpstreamStopForbidden("not_lease_owner")
            session.is_active = False

        try:
            if session.lease_generation is not None:
                owner_user_id = (
                    int(
                        requesting_user_id
                        if requesting_user_id is not None
                        else session.user_id
                    )
                    if (requesting_user_id is not None or session.user_id is not None)
                    else None
                )
                authorization = {
                    "channel_key": session.channel_key,
                    "generation": session.lease_generation,
                    "process_pid": session.streamlink_process.pid,
                    "process_group_id": session.process_group_id,
                    "process_start_fingerprint": session.process_start_fingerprint,
                    "expected_purpose": "LIVE",
                    "requesting_owner_user_id": owner_user_id,
                }
                if leader_exited:
                    if (
                        monitored_session is None
                        or session.streamlink_process.returncode is None
                    ):
                        raise PermissionError("leader has not exited")
                    await self._coordinator.assert_exited_process_cleanup_authorized(
                        **authorization,
                        expected_live_session_id=session_id,
                    )
                else:
                    await self._coordinator.assert_stop_authorized(**authorization)
        except PermissionError as error:
            session.is_active = True
            raise TwitchUpstreamStopForbidden("not_lease_owner") from error
        except BaseException:
            session.is_active = True
            raise

        logger.info(f"[LIVE] Stopping session {session_id} ({session.streamer_name})")

        streamlink_reaped = await self._reap_process(
            session.streamlink_process,
            process_group_id=session.process_group_id,
            process_start_fingerprint=session.process_start_fingerprint,
        )
        ffmpeg_reaped = await self._reap_process(
            session.ffmpeg_process,
            process_group_id=session.ffmpeg_process_group_id,
            process_start_fingerprint=session.ffmpeg_process_start_fingerprint,
        )
        if not streamlink_reaped or not ffmpeg_reaped:
            session.is_active = True
            raise TwitchUpstreamStopForbidden("process_identity_changed")

        if session.lease_generation is not None:
            await self._coordinator.release(
                channel_key=session.channel_key,
                generation=session.lease_generation,
                reason="live_stopped",
            )

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

    async def _reap_process(
        self,
        process,
        *,
        process_group_id=None,
        process_start_fingerprint=None,
    ) -> bool:
        if not process or process.returncode is not None:
            return True

        if process_group_id is None or not process_start_fingerprint:
            return False
        if not await self._process_identity_matches(
            process.pid,
            process_group_id,
            process_start_fingerprint,
        ):
            return False

        try:
            os.killpg(process_group_id, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                if not await self._process_identity_matches(
                    process.pid,
                    process_group_id,
                    process_start_fingerprint,
                ):
                    return False
                os.killpg(process_group_id, signal.SIGKILL)
                await process.wait()
            return process.returncode is not None
        except ProcessLookupError:
            if process.returncode is not None:
                await process.wait()
                return True
            return False
        except asyncio.CancelledError:
            raise
        except Exception:
            return False

    async def _process_identity_matches(
        self,
        process_pid,
        process_group_id,
        process_start_fingerprint,
    ) -> bool:
        try:
            identity = await self._coordinator.inspect_process_identity(process_pid)
        except Exception:
            return False
        return (
            identity.pid,
            identity.process_group_id,
            identity.fingerprint,
        ) == (process_pid, process_group_id, process_start_fingerprint)

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

    @staticmethod
    def _normalize_supported_codecs(supported_codecs: str) -> str:
        """Normalize live-player codec list to Streamlink's supported Twitch codecs."""
        allowed = {"h264", "h265", "av1"}
        codecs = []
        for codec in (supported_codecs or "h264").split(","):
            normalized = codec.strip().lower()
            if normalized in allowed and normalized not in codecs:
                codecs.append(normalized)

        # Compatibility-first fallback: never let recording config leak into live
        # playback implicitly. HEVC/AV1 must be requested by the browser/player.
        return ",".join(codecs) if codecs else "h264"

    async def _build_streamlink_command(
        self,
        streamer_name: str,
        quality: str,
        supported_codecs: str = "h264",
        enhanced_quality: bool = False,
    ) -> list:
        """Build Streamlink command for live streaming (no file output)"""
        normalized_codecs = self._normalize_supported_codecs(supported_codecs)
        cmd = [
            "streamlink",
            "--config",
            "/app/config/streamlink/config.twitch",
            f"twitch.tv/{streamer_name}",
            quality,
            "--stdout",  # Output to stdout instead of file
            # Live playback must use the codecs the current browser/player pipeline
            # can actually decode. Recordings may still use the global codec config.
            f"--twitch-supported-codecs={normalized_codecs}",
        ]

        with SessionLocal() as db:
            if enhanced_quality:
                token_service = TwitchTokenService(db)
                oauth_token = await token_service.get_valid_access_token()
                if oauth_token:
                    token_header = f"Authorization=OAuth {oauth_token.strip()}"
                    cmd.append(f"--twitch-api-header={token_header}")
                    logger.debug("[LIVE] Using OAuth token for enhanced stream")

            # Get proxy settings from health service
            try:
                proxy_url = await proxy_health_service.get_best_proxy()
                if proxy_url:
                    proxy_settings = {"http": proxy_url, "https": proxy_url}
                    cmd = _add_proxy_settings(cmd, proxy_settings, force_mode=False)
                    logger.debug(
                        "[LIVE] Using proxy: %s",
                        sanitize_proxy_url_for_logging(proxy_url),
                    )
            except Exception:
                logger.warning("[LIVE] Could not get proxy")

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
        except Exception as error:
            logger.error("[LIVE] Stream pipe ended (%s)", type(error).__name__)

    async def _monitor_session(self, session_id: str):
        """Monitor a session and auto-cleanup if processes die"""
        try:
            session = self.sessions.get(session_id)
            if not session:
                return

            # Wait for either process to exit
            while session.is_active:
                if session.lease_generation is not None:
                    heartbeat_ok = await self._coordinator.heartbeat(
                        channel_key=session.channel_key,
                        generation=session.lease_generation,
                    )
                    if not heartbeat_ok:
                        session.is_active = False
                        break
                # Check if processes are still running
                streamlink_done = session.streamlink_process.returncode is not None
                ffmpeg_done = session.ffmpeg_process.returncode is not None

                if streamlink_done or ffmpeg_done:
                    logger.info(
                        f"[LIVE] Process exited for session {session_id}, "
                        f"cleaning up..."
                    )
                    await self._stop_monitored_session(
                        session_id,
                        session,
                        leader_exited=streamlink_done,
                    )
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
