"""
Startup initialization for background services
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from sqlalchemy.orm import Session
from app.config.settings import Settings
from app.database import SessionLocal
from app.services.core.session_maintenance import cleanup_expired_sessions
from app.utils.async_db_utils import run_in_thread_pool
from app.services.init.background_queue_init import (
    BackgroundQueueManager,
    shutdown_background_queue,
)
from app.services.background_queue_service import BackgroundQueueService
from app.config.constants import ASYNC_DELAYS
from app.services.system.supervisor import TaskSupervisor

logger = logging.getLogger("streamvault")
_background_supervisor: TaskSupervisor | None = None

if TYPE_CHECKING:
    from app.services.recording.recording_manager import RecordingManager


def get_recording_manager():
    from app.dependencies import get_recording_manager as resolve_recording_manager

    return resolve_recording_manager()


async def initialize_background_queue_with_fixes(
    *,
    queue_manager: BackgroundQueueManager | None = None,
    capture_checker: Callable[[int], Awaitable[bool | None]] | None = None,
):
    """Initialize background queue with production concurrency and auth fixes"""
    try:
        # Check if already initialized to prevent double initialization
        from app.services.init.background_queue_init import background_queue_manager

        if queue_manager is not None:
            if capture_checker is None:
                raise ValueError("An application queue requires its capture checker")
            background_queue_manager = queue_manager

        if background_queue_manager.is_initialized:
            logger.info(
                "✅ Background queue already initialized, skipping duplicate initialization"
            )
            return

        logger.info("Initializing background queue with production fixes...")

        # Check if we're in production environment (multiple streamers)
        import os

        enable_isolation = (
            os.getenv("STREAMVAULT_ENABLE_STREAMER_ISOLATION", "true").lower() == "true"
        )

        # Initialize with enhanced queue manager
        from app.services.init.background_queue_init import initialize_background_queue

        background_queue_manager.queue_service.capture_checker = (
            capture_checker
            if capture_checker is not None
            else get_recording_manager().is_capture_running
        )
        if queue_manager is None:
            await initialize_background_queue(
                enable_streamer_isolation=enable_isolation
            )
        else:
            await queue_manager.initialize(enable_streamer_isolation=enable_isolation)

        logger.info(
            f"✅ Background queue initialized with streamer isolation: {enable_isolation}"
        )

    except Exception as e:
        logger.error(f"❌ Failed to initialize background queue with fixes: {e}")
        raise


async def start_session_cleanup_service(
    supervisor: TaskSupervisor,
    session_factory: Callable[[], Session] = SessionLocal,
    settings: Settings | None = None,
):
    """Start session cleanup service for production authentication reliability"""
    try:
        logger.info("Starting session cleanup service...")

        # Run initial cleanup
        cleaned_count = await run_in_thread_pool(
            cleanup_expired_sessions, session_factory, settings
        )
        logger.info(
            f"✅ Session cleanup service started, cleaned {cleaned_count} expired sessions"
        )

        # Schedule periodic cleanup (every 6 hours)
        async def periodic_session_cleanup():
            while True:
                try:
                    await asyncio.sleep(ASYNC_DELAYS.SESSION_CLEANUP_INTERVAL)

                    cleaned_count = await run_in_thread_pool(
                        cleanup_expired_sessions, session_factory, settings
                    )
                    if cleaned_count > 0:
                        logger.info(
                            f"Periodic session cleanup: removed {cleaned_count} expired sessions"
                        )

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in periodic session cleanup: {e}")

        supervisor.create_task("periodic-session-cleanup", periodic_session_cleanup())

    except Exception as e:
        logger.error(f"❌ Failed to start session cleanup service: {e}")
        logger.warning(
            "⚠️ Session cleanup disabled, may cause auth issues in production"
        )


async def start_zombie_recording_cleanup_service(
    supervisor: TaskSupervisor,
    *,
    recording_manager: "RecordingManager | None" = None,
):
    """Run guarded physical-death cleanup initially and every five minutes."""
    try:
        logger.info("Starting zombie recording cleanup service...")

        async def cleanup() -> int:
            if recording_manager is None:
                return await _cleanup_zombie_recordings_now()
            return await _cleanup_zombie_recordings_now(
                recording_manager=recording_manager
            )

        # Run initial cleanup immediately at startup
        cleaned_count = await cleanup()
        logger.info(
            f"✅ Zombie recording cleanup service started, cleaned {cleaned_count} zombie recordings"
        )

        # Schedule periodic cleanup every 5 minutes for fast detection
        ZOMBIE_CLEANUP_INTERVAL = 5 * 60  # 5 minutes in seconds

        async def periodic_zombie_cleanup():
            while True:
                try:
                    await asyncio.sleep(ZOMBIE_CLEANUP_INTERVAL)

                    cleaned_count = await cleanup()
                    if cleaned_count > 0:
                        logger.info(
                            f"🧹 Periodic zombie cleanup: cleaned {cleaned_count} zombie recordings"
                        )

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in periodic zombie cleanup: {e}")

        supervisor.create_task("periodic-zombie-cleanup", periodic_zombie_cleanup())

    except Exception as e:
        logger.error(f"❌ Failed to start zombie recording cleanup service: {e}")
        logger.warning("⚠️ Zombie cleanup disabled, stale recordings may accumulate")


async def _cleanup_zombie_recordings_now(
    *, recording_manager: "RecordingManager | None" = None
) -> int:
    """Stop only positively dead captures under the owning admission transaction."""
    from datetime import datetime, timezone
    from app.models import Recording
    from app.services.recording.media_ownership import CaptureState, capture_state

    manager = (
        recording_manager
        if recording_manager is not None
        else await run_in_thread_pool(get_recording_manager)
    )
    processes = manager.process_manager
    snapshots = await processes.capture_process_snapshot()
    state = manager.orchestrator.state_manager
    memory = state.get_active_recordings()

    def stop_dead(db: Session) -> list[int]:
        stopped = []
        recordings = (
            db.query(Recording)
            .filter(Recording.status == "recording")
            .with_for_update()
            .all()
        )
        for recording in recordings:
            if (
                capture_state(
                    db, recording, snapshots.get(f"stream_{recording.stream_id}")
                )
                is not CaptureState.DEAD
            ):
                continue
            now = datetime.now(timezone.utc)
            recording.status = "stopped"
            recording.end_time = now
            if recording.start_time is not None:
                started = recording.start_time
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                recording.duration = int((now - started).total_seconds())
            stopped.append(recording.id)
        return stopped

    stopped = await processes.upstream_coordinator.run_capture_maintenance(stop_dead)
    for recording_id in stopped:
        if state.get_active_recording(recording_id) is memory.get(recording_id):
            state.remove_active_recording(recording_id)
    return len(stopped)


async def initialize_vapid_keys():
    """Initialize VAPID keys for push notifications at startup"""
    try:
        logger.info("Initializing VAPID keys for push notifications...")

        from app.config.settings import settings

        # Force VAPID key loading/generation by accessing them
        vapid_keys = settings.get_vapid_keys()

        if vapid_keys and vapid_keys["public_key"] and vapid_keys["private_key"]:
            logger.info("VAPID keys initialized successfully")
            logger.debug(f"Public key: {vapid_keys['public_key'][:20]}...")
        else:
            logger.warning(
                "VAPID keys could not be initialized - push notifications will be disabled"
            )

    except Exception as e:
        logger.error(f"Failed to initialize VAPID keys: {e}", exc_info=True)
        logger.warning("Push notifications will be disabled for this session")


async def initialize_background_services(
    supervisor: TaskSupervisor | None = None,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    settings: Settings | None = None,
    queue_manager: BackgroundQueueManager | None = None,
    capture_checker: Callable[[int], Awaitable[bool | None]] | None = None,
    recording_manager: "RecordingManager | None" = None,
):
    """Initialize all background services at startup with production fixes"""
    global _background_supervisor
    if supervisor is None:
        supervisor = TaskSupervisor("background-services")
        _background_supervisor = supervisor
    try:
        logger.info("Initializing background services with production fixes...")

        # Initialize VAPID keys for push notifications
        await initialize_vapid_keys()

        # Initialize background queue with production fixes
        if queue_manager is None:
            await initialize_background_queue_with_fixes()
            queue_ready = await verify_queue_readiness()
        else:
            await initialize_background_queue_with_fixes(
                queue_manager=queue_manager, capture_checker=capture_checker
            )
            queue_ready = await verify_queue_readiness(
                queue_service=queue_manager.queue_service
            )
        if not queue_ready:
            logger.warning("⚠️ Background queue not ready - skipping recovery for now")
            # Don't run recovery immediately, let it run later via API
        else:
            logger.info("✅ Background queue verified ready - proceeding with recovery")

            # CRITICAL: Recover active recordings FIRST (resume live streams)
            # This prevents unified recovery from processing recordings that are still live
            await recover_active_recordings()

            # UNIFIED RECOVERY: Only run AFTER active recordings are resumed
            # This ensures we only post-process recordings that are actually offline
            if queue_manager is None:
                await unified_recovery_scan()
            else:
                await unified_recovery_scan(queue_service=queue_manager.queue_service)

        # Initialize image sync service for automatic image downloads
        await initialize_image_sync_service()

        # Start session cleanup service for production auth reliability
        await start_session_cleanup_service(supervisor, session_factory, settings)

        # Start periodic zombie recording cleanup service
        if recording_manager is None:
            await start_zombie_recording_cleanup_service(supervisor)
        else:
            await start_zombie_recording_cleanup_service(
                supervisor, recording_manager=recording_manager
            )

        logger.info("Background services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize background services: {e}", exc_info=True)
        raise


async def verify_queue_readiness(
    *, queue_service: BackgroundQueueService | None = None
) -> bool:
    """Verify that the background queue is fully ready to accept tasks"""
    try:
        # Direct access to the queue manager through background queue service
        from app.services.init.background_queue_init import get_background_queue_service

        max_attempts = 3
        application_queue_service = queue_service
        for attempt in range(max_attempts):
            try:
                # Get the background queue service and check its status
                queue_service = (
                    application_queue_service
                    if application_queue_service is not None
                    else get_background_queue_service()
                )

                if not queue_service:
                    logger.debug(f"⚠️ Queue service not found on attempt {attempt + 1}")
                elif not queue_service.is_running:
                    logger.debug(
                        f"⚠️ Queue service not running on attempt {attempt + 1}"
                    )
                elif not queue_service.has_queue_manager():
                    logger.debug(
                        f"⚠️ Queue manager not available on attempt {attempt + 1}"
                    )
                elif not queue_service.is_queue_manager_running():
                    logger.debug(
                        f"⚠️ Queue manager not running on attempt {attempt + 1}"
                    )
                else:
                    # Check if we have at least one queue and it's active using proper abstraction
                    status = queue_service.get_queue_status()
                    if status:
                        # Check for streamer isolation mode (has 'streamers' field) or shared mode (has queue_size field) or active workers
                        has_queue_system = (
                            (
                                "streamers" in status
                                and isinstance(status["streamers"], dict)
                            )
                            or (
                                "queue_size" in status
                                and isinstance(status["queue_size"], int)
                                and status["queue_size"] >= 0
                            )
                            or (
                                "workers" in status
                                and status["workers"].get("total", 0) > 0
                            )
                        )
                        if has_queue_system:
                            logger.info(
                                f"✅ Queue readiness verified on attempt {attempt + 1}"
                            )
                            return True
                        else:
                            logger.debug(
                                f"⚠️ Queue manager running but no queue system detected on attempt {attempt + 1}: {status}"
                            )
                    else:
                        logger.debug(
                            f"⚠️ Queue manager running but status unavailable on attempt {attempt + 1}"
                        )

            except Exception as e:
                logger.debug(
                    f"⚠️ Queue readiness check failed on attempt {attempt + 1}: {e}"
                )

            # Always wait before retry (except on last attempt)
            if attempt < max_attempts - 1:
                await asyncio.sleep(ASYNC_DELAYS.SHORT_RETRY_DELAY)

        logger.warning(
            f"⚠️ Queue readiness verification failed after {max_attempts} attempts"
        )
        return False

    except Exception as e:
        logger.error(f"❌ Error verifying queue readiness: {e}")
        return False


async def unified_recovery_scan(*, queue_service: BackgroundQueueService | None = None):
    """Unified recovery scan - enqueued to background queue to prevent frontend blocking"""
    try:
        logger.info("🔄 Scheduling unified recovery scan in background queue...")

        from app.services.init.background_queue_init import get_background_queue_service

        # Get background queue service
        if queue_service is None:
            queue_service = get_background_queue_service()

        if not queue_service or not queue_service.is_running:
            logger.warning("⚠️ Background queue not running - skipping unified recovery")
            return

        # Enqueue recovery task instead of running synchronously
        # This prevents blocking the frontend during FFmpeg concatenation
        from app.services.background_queue_service import TaskPriority

        task_id = await queue_service.enqueue_task(
            task_type="unified_recovery",
            payload={"max_age_hours": 72, "dry_run": False},
            priority=TaskPriority.LOW,
            max_retries=1,
        )

        if task_id:
            logger.info(
                f"✅ Unified recovery enqueued (task_id={task_id}) - will run in background"
            )
        else:
            logger.warning("⚠️ Failed to enqueue unified recovery - will retry later")

    except Exception as e:
        logger.error(f"❌ Failed to schedule unified recovery: {e}", exc_info=True)
        # Don't raise - this is not critical for startup


async def cleanup_zombie_recordings():
    """Clean up zombie/stale recordings from database on startup with smart recovery

    Recordings are considered zombies if:
    - They are marked as 'recording' status in the database
    - But the application was restarted (no actual Streamlink process running)

    Smart Recovery Logic:
    1. Check if streamer is still live via Twitch API
    2. If still live → Resume recording (prevent data loss)
    3. If offline → Mark as stopped and trigger post-processing

    This prevents false recording endings on app restarts while streams are still live.
    """
    try:
        logger.info(
            "🧹 Cleaning up zombie recordings from database with smart recovery..."
        )

        from app.database import SessionLocal
        from app.models import Recording, Stream, TwitchUpstreamLease
        from app.services.streamer_service import StreamerService
        from app.services.communication.websocket_manager import websocket_manager
        from app.events.handler_registry import EventHandlerRegistry
        from app.config.settings import settings

        # Initialize event registry with required dependencies
        event_handler_registry = EventHandlerRegistry(
            connection_manager=websocket_manager, settings=settings
        )
        from datetime import datetime, timezone
        from sqlalchemy.orm import joinedload

        with SessionLocal() as db:
            # Initialize services with required dependencies
            streamer_service = StreamerService(
                db, websocket_manager, event_handler_registry
            )
            recording_manager = get_recording_manager()
            # Find all recordings with 'recording' status (eager load relationships)
            zombie_recordings = (
                db.query(Recording)
                .options(joinedload(Recording.stream).joinedload(Stream.streamer))
                .filter(Recording.status == "recording")
                .all()
            )

            if not zombie_recordings:
                logger.info("✅ No zombie recordings found")
                return

            cleaned_count = 0
            resumed_count = 0

            for recording in zombie_recordings:
                try:
                    # Get streamer information through relationships
                    if not recording.stream or not recording.stream.streamer:
                        logger.warning(
                            f"⚠️ Recording {recording.id} has no associated streamer - marking as stopped"
                        )
                        recording.status = "stopped"
                        recording.end_time = datetime.now(timezone.utc)
                        cleaned_count += 1
                        continue

                    streamer = recording.stream.streamer
                    stream = recording.stream

                    # Check if streamer is still live via Twitch API
                    logger.info(
                        f"🔍 Checking if {streamer.username} (twitch_id={streamer.twitch_id}) is still live..."
                    )

                    try:
                        is_still_live = (
                            await streamer_service.check_streamer_live_status(
                                streamer.twitch_id
                            )
                        )
                    except Exception as api_error:
                        logger.error(
                            f"❌ Failed to check live status for {streamer.username}: {api_error}"
                        )
                        logger.warning(
                            f"⏳ Deferring zombie recording cleanup for {streamer.username} "
                            "because live status could not be verified"
                        )
                        continue

                    if is_still_live:
                        # Streamer is STILL LIVE - Resume recording!
                        logger.info(
                            f"🔄 RESUMING recording for {streamer.username}: "
                            f"Stream still live after app restart (recording_id={recording.id}, stream_id={stream.id})"
                        )

                        # CRITICAL: Find the existing segments directory to resume into
                        # This ensures all segments end up in the same directory for later concatenation
                        resume_segments_dir = None

                        # Try to find segments directory from StreamMetadata
                        try:
                            from app.models import StreamMetadata

                            metadata = (
                                db.query(StreamMetadata)
                                .filter(StreamMetadata.stream_id == stream.id)
                                .first()
                            )

                            if metadata and metadata.segments_dir_path:
                                from pathlib import Path

                                if Path(metadata.segments_dir_path).exists():
                                    resume_segments_dir = metadata.segments_dir_path
                                    logger.info(
                                        f"📂 Found segments directory from metadata: {resume_segments_dir}"
                                    )
                        except Exception as e:
                            logger.debug(
                                f"Could not get segments dir from metadata: {e}"
                            )

                        # Fallback: Try to derive from recording path
                        if not resume_segments_dir and recording.path:
                            from pathlib import Path

                            potential_dir = Path(recording.path).with_suffix(
                                ""
                            ).parent / (Path(recording.path).stem + "_segments")
                            if potential_dir.exists():
                                resume_segments_dir = str(potential_dir)
                                logger.info(
                                    f"📂 Found segments directory from recording path: {resume_segments_dir}"
                                )

                        try:
                            # Resume recording through the process-scoped manager.
                            # Pass resume_segments_dir to continue in the same segments folder
                            if recording_manager.is_stream_active(stream.id):
                                logger.info(
                                    "Recording for stream %s is already locally active; "
                                    "preserving its database state",
                                    stream.id,
                                )
                                continue
                            recovery_generation = (
                                db.query(TwitchUpstreamLease.generation)
                                .filter(
                                    TwitchUpstreamLease.channel_key
                                    == streamer.twitch_id,
                                    TwitchUpstreamLease.recording_id == recording.id,
                                )
                                .scalar()
                            )
                            if recovery_generation is None:
                                logger.warning(
                                    "No persisted upstream generation for recording %s; "
                                    "deferring recovery",
                                    recording.id,
                                )
                                continue
                            resumed_recording_id = (
                                await recording_manager.start_recording(
                                    stream_id=stream.id,
                                    streamer_id=streamer.id,
                                    force_mode=True,
                                    resume_segments_dir=resume_segments_dir,
                                    recovery_generation=recovery_generation,
                                )
                            )
                            if not resumed_recording_id:
                                logger.error(
                                    f"❌ Failed to resume recording for {streamer.username}"
                                )
                                continue

                            now_utc = datetime.now(timezone.utc)
                            recording.status = "stopped"
                            recording.end_time = now_utc
                            if recording.start_time:
                                start_time = recording.start_time
                                if start_time.tzinfo is None:
                                    start_time = start_time.replace(tzinfo=timezone.utc)
                                recording.duration = int(
                                    (now_utc - start_time).total_seconds()
                                )
                            db.commit()
                            resumed_count += 1
                            if resume_segments_dir:
                                logger.info(
                                    f"✅ Successfully resumed recording for {streamer.username} in existing segments folder"
                                )
                            else:
                                logger.info(
                                    f"✅ Successfully started new recording for {streamer.username} (no existing segments found)"
                                )
                        except Exception as resume_error:
                            logger.error(
                                f"❌ Failed to resume recording for {streamer.username}: {resume_error}"
                            )
                    else:
                        # Streamer is OFFLINE - Mark as stopped
                        logger.info(
                            f"🛑 Streamer {streamer.username} is offline - marking recording as stopped "
                            f"(recording_id={recording.id}, stream_id={stream.id})"
                        )

                        # CRITICAL: Use timezone-aware datetime to match database timestamps
                        now_utc = datetime.now(timezone.utc)

                        # Calculate duration if available
                        duration = None
                        if recording.start_time:
                            # Ensure end_time is timezone-aware
                            end_time = recording.end_time or now_utc

                            # Both datetimes must be timezone-aware for subtraction
                            if recording.start_time.tzinfo is None:
                                from datetime import timezone as tz

                                start_time_aware = recording.start_time.replace(
                                    tzinfo=tz.utc
                                )
                            else:
                                start_time_aware = recording.start_time

                            duration = int(
                                (end_time - start_time_aware).total_seconds()
                            )

                        # Mark as stopped (not failed, because the recording may have been successful)
                        recording.status = "stopped"
                        recording.end_time = recording.end_time or now_utc
                        if duration:
                            recording.duration_seconds = duration

                        # Also mark stream as ended
                        if stream.ended_at is None:
                            stream.ended_at = now_utc
                            logger.info(f"📝 Marked stream {stream.id} as ended")

                        cleaned_count += 1

                        logger.info(
                            f"🧹 Cleaned zombie recording {recording.id}: "
                            f"streamer={streamer.username}, "
                            f"started={recording.start_time}, "
                            f"duration={duration}s"
                        )

                except Exception as e:
                    logger.error(
                        f"❌ Failed to process zombie recording {recording.id}: {e}",
                        exc_info=True,
                    )
                    continue

            db.commit()
            logger.info(
                f"✅ Zombie recording cleanup completed: "
                f"resumed={resumed_count}, stopped={cleaned_count}, total_processed={resumed_count + cleaned_count}"
            )

    except Exception as e:
        logger.error(f"❌ Failed to cleanup zombie recordings: {e}", exc_info=True)
        # Don't raise - this is not critical for startup


async def recover_active_recordings():
    """Recover active recordings from persistent state"""
    try:
        logger.info("Recovering active recordings from persistent state...")

        # First, clean up zombie recordings from previous session
        await cleanup_zombie_recordings()

        recording_manager = get_recording_manager()

        await recording_manager.startup_reconcile()

        logger.info("Active recordings recovery completed")

    except Exception as e:
        logger.error(f"Failed to recover active recordings: {e}", exc_info=True)
        # Don't raise - this is not critical for startup


async def initialize_image_sync_service():
    """Initialize automatic image sync service"""
    try:
        logger.info("Initializing automatic image sync service...")

        from app.services.images.auto_image_sync_service import auto_image_sync_service
        from app.services.unified_image_service import unified_image_service

        # Start the background sync worker
        await auto_image_sync_service.start_sync_worker()

        # Perform initial sync of all existing categories and streamers
        await auto_image_sync_service.sync_all_existing_categories()
        await auto_image_sync_service.sync_all_existing_streamers()

        # IMPORTANT: Sync all profile images to convert Twitch URLs to local paths
        logger.info(
            "Starting profile image sync to convert Twitch URLs to local paths..."
        )
        profile_stats = await unified_image_service.sync_all_profile_images()
        logger.info(f"Profile image sync completed: {profile_stats}")

        logger.info("Image sync service initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize image sync service: {e}", exc_info=True)
        # Don't raise - this is not critical for startup


async def shutdown_background_services(
    supervisor: TaskSupervisor | None = None,
    *,
    queue_manager: BackgroundQueueManager | None = None,
):
    """Shutdown all background services"""
    try:
        logger.info("Shutting down background services...")

        global _background_supervisor
        target = supervisor if supervisor is not None else _background_supervisor
        if target is not None:
            await target.shutdown()
            if target is _background_supervisor:
                _background_supervisor = None

        # Shutdown image sync service
        from app.services.images.auto_image_sync_service import auto_image_sync_service

        await auto_image_sync_service.stop_sync_worker()

        # Shutdown background queue
        if queue_manager is None:
            await shutdown_background_queue()
        else:
            await queue_manager.shutdown()

        logger.info("Background services shut down successfully")

    except Exception as e:
        logger.error(f"Failed to shutdown background services: {e}", exc_info=True)
        raise
