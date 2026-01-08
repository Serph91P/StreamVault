"""
Startup initialization for background services
"""

import asyncio
import logging
from app.services.init.background_queue_init import shutdown_background_queue
from app.config.constants import ASYNC_DELAYS

logger = logging.getLogger("streamvault")


async def initialize_background_queue_with_fixes():
    """Initialize background queue with production concurrency and auth fixes"""
    try:
        # Check if already initialized to prevent double initialization
        from app.services.init.background_queue_init import background_queue_manager

        if background_queue_manager.is_initialized:
            logger.info("✅ Background queue already initialized, skipping duplicate initialization")
            return

        logger.info("Initializing background queue with production fixes...")

        # Check if we're in production environment (multiple streamers)
        import os

        enable_isolation = os.getenv("STREAMVAULT_ENABLE_STREAMER_ISOLATION", "true").lower() == "true"

        # Initialize with enhanced queue manager
        from app.services.init.background_queue_init import initialize_background_queue

        await initialize_background_queue(enable_streamer_isolation=enable_isolation)

        logger.info(f"✅ Background queue initialized with streamer isolation: {enable_isolation}")

    except Exception as e:
        logger.error(f"❌ Failed to initialize background queue with fixes: {e}")
        raise


async def start_session_cleanup_service():
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
            logger.info(f"✅ Session cleanup service started, cleaned {cleaned_count} expired sessions")
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
                            logger.info(f"Periodic session cleanup: removed {cleaned_count} expired sessions")
                    finally:
                        db.close()

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in periodic session cleanup: {e}")

        # Start cleanup task
        asyncio.create_task(periodic_session_cleanup())

    except Exception as e:
        logger.error(f"❌ Failed to start session cleanup service: {e}")
        logger.warning("⚠️ Session cleanup disabled, may cause auth issues in production")


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
            logger.warning("VAPID keys could not be initialized - push notifications will be disabled")

    except Exception as e:
        logger.error(f"Failed to initialize VAPID keys: {e}", exc_info=True)
        logger.warning("Push notifications will be disabled for this session")


async def initialize_background_services():
    """Initialize all background services at startup with production fixes"""
    try:
        logger.info("Initializing background services with production fixes...")

        # Initialize VAPID keys for push notifications
        await initialize_vapid_keys()

        # Initialize background queue with production fixes
        await initialize_background_queue_with_fixes()

        # CRITICAL: Wait for queue workers to be fully ready before recovery
        logger.info("⏳ Waiting for background queue workers to be fully ready...")
        await asyncio.sleep(ASYNC_DELAYS.QUEUE_WORKER_START_DELAY)

        # Verify queue is responsive before proceeding
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
        await start_session_cleanup_service()

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
                    logger.debug(f"⚠️ Queue service not running on attempt {attempt + 1}")
                elif not queue_service.has_queue_manager():
                    logger.debug(f"⚠️ Queue manager not available on attempt {attempt + 1}")
                elif not queue_service.is_queue_manager_running():
                    logger.debug(f"⚠️ Queue manager not running on attempt {attempt + 1}")
                else:
                    # Check if we have at least one queue and it's active using proper abstraction
                    status = queue_service.get_queue_status()
                    if status:
                        # Check for streamer isolation mode (has 'streamers' field) or shared mode (has queue_size field) or active workers
                        has_queue_system = (
                            ("streamers" in status and isinstance(status["streamers"], dict))
                            or (
                                "queue_size" in status
                                and isinstance(status["queue_size"], int)
                                and status["queue_size"] >= 0
                            )
                            or ("workers" in status and status["workers"].get("total", 0) > 0)
                        )
                        if has_queue_system:
                            logger.info(f"✅ Queue readiness verified on attempt {attempt + 1}")
                            return True
                        else:
                            logger.debug(
                                f"⚠️ Queue manager running but no queue system detected on attempt {attempt + 1}: {status}"
                            )
                    else:
                        logger.debug(f"⚠️ Queue manager running but status unavailable on attempt {attempt + 1}")

            except Exception as e:
                logger.debug(f"⚠️ Queue readiness check failed on attempt {attempt + 1}: {e}")

            # Always wait before retry (except on last attempt)
            if attempt < max_attempts - 1:
                await asyncio.sleep(ASYNC_DELAYS.SHORT_RETRY_DELAY)

        logger.warning(f"⚠️ Queue readiness verification failed after {max_attempts} attempts")
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
            logger.info(f"✅ Unified recovery enqueued (task_id={task_id}) - will run in background")
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
        logger.info("🧹 Cleaning up zombie recordings from database with smart recovery...")

        from app.database import SessionLocal
        from app.models import Recording, Stream
        from app.services.streamer_service import StreamerService
        from app.services.recording.recording_service import RecordingService
        from app.services.communication.websocket_manager import websocket_manager
        from app.events.handler_registry import EventHandlerRegistry
        from app.config.settings import settings

        # Initialize event registry with required dependencies
        event_handler_registry = EventHandlerRegistry(connection_manager=websocket_manager, settings=settings)
        from datetime import datetime, timezone
        from sqlalchemy.orm import joinedload

        with SessionLocal() as db:
            # Initialize services with required dependencies
            streamer_service = StreamerService(db, websocket_manager, event_handler_registry)
            recording_service = RecordingService()
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
                        logger.warning(f"⚠️ Recording {recording.id} has no associated streamer - marking as stopped")
                        recording.status = "stopped"
                        recording.end_time = datetime.now(timezone.utc)
                        cleaned_count += 1
                        continue

                    streamer = recording.stream.streamer
                    stream = recording.stream

                    # Check if streamer is still live via Twitch API
                    logger.info(f"🔍 Checking if {streamer.username} (twitch_id={streamer.twitch_id}) is still live...")

                    try:
                        is_still_live = await streamer_service.check_streamer_live_status(streamer.twitch_id)
                    except Exception as api_error:
                        logger.error(f"❌ Failed to check live status for {streamer.username}: {api_error}")
                        # On API error, conservatively mark as stopped to avoid leaving zombie state
                        is_still_live = False

                    if is_still_live:
                        # Streamer is STILL LIVE - Resume recording!
                        logger.info(
                            f"🔄 RESUMING recording for {streamer.username}: "
                            f"Stream still live after app restart (recording_id={recording.id}, stream_id={stream.id})"
                        )

                        try:
                            # Resume recording through RecordingService
                            await recording_service.start_recording(
                                stream_id=stream.id,
                                streamer_id=streamer.id,
                                force_mode=True,  # Force resume even if recording "exists"
                            )
                            resumed_count += 1
                            logger.info(f"✅ Successfully resumed recording for {streamer.username}")
                        except Exception as resume_error:
                            logger.error(f"❌ Failed to resume recording for {streamer.username}: {resume_error}")
                            # Fallback: Mark as stopped if resume fails
                            recording.status = "stopped"
                            recording.end_time = datetime.now(timezone.utc)
                            cleaned_count += 1
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

                                start_time_aware = recording.start_time.replace(tzinfo=tz.utc)
                            else:
                                start_time_aware = recording.start_time

                            duration = int((end_time - start_time_aware).total_seconds())

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
                    logger.error(f"❌ Failed to process zombie recording {recording.id}: {e}", exc_info=True)
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

        from app.services.recording.recording_service import RecordingService

        # Get singleton instance
        recording_service = RecordingService()

        # Recover active recordings
        await recording_service.recover_active_recordings_from_persistence()

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
        logger.info("Starting profile image sync to convert Twitch URLs to local paths...")
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

        # Shutdown image sync service
        from app.services.images.auto_image_sync_service import auto_image_sync_service

        await auto_image_sync_service.stop_sync_worker()

        # Shutdown background queue
        await shutdown_background_queue()

        logger.info("Background services shut down successfully")

    except Exception as e:
        logger.error(f"Failed to shutdown background services: {e}", exc_info=True)
        raise
