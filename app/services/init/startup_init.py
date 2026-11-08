"""
Startup initialization for background services
"""

import asyncio
import logging
from typing import TYPE_CHECKING
from sqlalchemy.orm import Session
from app.utils.async_db_utils import run_in_thread_pool
from app.services.init.background_queue_init import shutdown_background_queue
from app.config.constants import ASYNC_DELAYS
from app.services.system.supervisor import TaskSupervisor

logger = logging.getLogger("streamvault")
_background_supervisor: TaskSupervisor | None = None
if TYPE_CHECKING:
    from app.services.recording.recording_manager import RecordingManager


def get_recording_manager():
    from app.dependencies import get_recording_manager as resolve_recording_manager

    return resolve_recording_manager()


async def initialize_background_queue_with_fixes():
    """Initialize background queue with production concurrency and auth fixes"""
    try:
        # Check if already initialized to prevent double initialization
        from app.services.init.background_queue_init import background_queue_manager

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
            get_recording_manager().is_capture_running
        )
        await initialize_background_queue(enable_streamer_isolation=enable_isolation)

        logger.info(
            f"✅ Background queue initialized with streamer isolation: {enable_isolation}"
        )

    except Exception as e:
        logger.error(f"❌ Failed to initialize background queue with fixes: {e}")
        raise


async def start_session_cleanup_service(supervisor: TaskSupervisor):
    """Start session cleanup service for production authentication reliability"""
    try:
        logger.info("Starting session cleanup service...")

        # Run initial cleanup
        from app.database import SessionLocal
        from app.services.core.auth_service import AuthService

        db = SessionLocal()
        try:
            auth_service = AuthService(db)
            cleaned_count = await auth_service.cleanup_expired_sessions()
            logger.info(
                f"✅ Session cleanup service started, cleaned {cleaned_count} expired sessions"
            )
        finally:
            db.close()

        # Schedule periodic cleanup (every 6 hours)
        async def periodic_session_cleanup():
            while True:
                try:
                    await asyncio.sleep(ASYNC_DELAYS.SESSION_CLEANUP_INTERVAL)

                    db = SessionLocal()
                    try:
                        auth_service = AuthService(db)
                        cleaned_count = await auth_service.cleanup_expired_sessions()
                        if cleaned_count > 0:
                            logger.info(
                                f"Periodic session cleanup: removed {cleaned_count} expired sessions"
                            )
                    finally:
                        db.close()

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


async def start_zombie_recording_cleanup_service(supervisor: TaskSupervisor):
    """Start periodic zombie recording cleanup service.

    This service runs every 5 minutes to detect and clean up recordings that are
    stuck in 'recording' status but have no active Streamlink process.

    This is essential for production reliability after app restarts/updates.

    Detection Logic:
    1. If recording has no active Streamlink process AND is older than 30 minutes → Zombie
    2. If recording has no active process AND streamer is offline → Zombie (regardless of age)
    """
    try:
        logger.info("Starting zombie recording cleanup service...")

        # Run initial cleanup immediately at startup
        cleaned_count = await _cleanup_zombie_recordings_now()
        logger.info(
            f"✅ Zombie recording cleanup service started, cleaned {cleaned_count} zombie recordings"
        )

        # Schedule periodic cleanup every 5 minutes for fast detection
        ZOMBIE_CLEANUP_INTERVAL = 5 * 60  # 5 minutes in seconds

        async def periodic_zombie_cleanup():
            while True:
                try:
                    await asyncio.sleep(ZOMBIE_CLEANUP_INTERVAL)

                    cleaned_count = await _cleanup_zombie_recordings_now()
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
    state = manager.orchestrator.state_manager
    memory = state.get_active_recordings()
    cursor = total = 0
    while True:
        snapshots = await processes.capture_process_snapshot()

        def stop_dead(db: Session) -> tuple[int, list[int]]:
            stopped = []
            recordings = (
                db.query(Recording)
                .filter(
                    Recording.status == "recording",
                    Recording.id > cursor,
                )
                .order_by(Recording.id)
                .limit(100)
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
            return (recordings[-1].id if recordings else cursor), stopped

        (
            next_cursor,
            stopped,
        ) = await processes.upstream_coordinator.run_capture_maintenance(stop_dead)
        if next_cursor == cursor:
            break
        cursor = next_cursor
        total += len(stopped)
        for recording_id in stopped:
            if state.get_active_recording(recording_id) is memory.get(recording_id):
                state.remove_active_recording(recording_id)
        await asyncio.sleep(0)
    return total


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
        await initialize_background_queue_with_fixes()

        # Verify queue readiness directly; do not hide startup ordering behind a delay.
        queue_ready = await verify_queue_readiness()
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
            await unified_recovery_scan()

        # Initialize image sync service for automatic image downloads
        await initialize_image_sync_service()

        # Start session cleanup service for production auth reliability
        await start_session_cleanup_service(supervisor)

        # Start periodic zombie recording cleanup service
        await start_zombie_recording_cleanup_service(supervisor)

        logger.info("Background services initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize background services: {e}", exc_info=True)
        raise


async def verify_queue_readiness() -> bool:
    """Verify that the background queue is fully ready to accept tasks"""
    try:
        # Direct access to the queue manager through background queue service
        from app.services.init.background_queue_init import get_background_queue_service

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Get the background queue service and check its status
                queue_service = get_background_queue_service()

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


async def unified_recovery_scan():
    """Unified recovery scan - enqueued to background queue to prevent frontend blocking"""
    try:
        logger.info("🔄 Scheduling unified recovery scan in background queue...")

        from app.services.init.background_queue_init import get_background_queue_service

        # Get background queue service
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
    """Recover only physically dead captures using short, fenced transactions."""
    try:
        from app.database import SessionLocal
        from app.services.api.twitch_api import twitch_api
        from app.services.recording.startup_recovery import recover_startup_recordings

        await recover_startup_recordings(
            session_factory=SessionLocal,
            recording_manager=get_recording_manager(),
            twitch_service=twitch_api,
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


async def shutdown_background_services():
    """Shutdown all background services"""
    try:
        logger.info("Shutting down background services...")

        global _background_supervisor
        if _background_supervisor is not None:
            await _background_supervisor.shutdown()
            _background_supervisor = None

        # Shutdown image sync service
        from app.services.images.auto_image_sync_service import auto_image_sync_service

        await auto_image_sync_service.stop_sync_worker()

        # Shutdown background queue
        await shutdown_background_queue()

        logger.info("Background services shut down successfully")

    except Exception as e:
        logger.error(f"Failed to shutdown background services: {e}", exc_info=True)
        raise
