"""
Startup initialization for background services
"""

import asyncio
import logging
from app.services.init.background_queue_init import initialize_background_queue, shutdown_background_queue

logger = logging.getLogger("streamvault")

async def initialize_background_queue_with_fixes():
    """Initialize background queue with production concurrency and auth fixes"""
    try:
        logger.info("Initializing background queue with production fixes...")
        
        # Check if we're in production environment (multiple streamers)
        import os
        enable_isolation = os.getenv('STREAMVAULT_ENABLE_STREAMER_ISOLATION', 'true').lower() == 'true'
        
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
                    await asyncio.sleep(6 * 3600)  # 6 hours
                    
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
        
        if vapid_keys and vapid_keys['public_key'] and vapid_keys['private_key']:
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
        await asyncio.sleep(5)  # Give queue workers time to start
        
        # Verify queue is responsive before proceeding
        queue_ready = await verify_queue_readiness()
        if not queue_ready:
            logger.warning("⚠️ Background queue not ready - skipping unified recovery for now")
            # Don't run recovery immediately, let it run later via API
        else:
            logger.info("✅ Background queue verified ready - proceeding with recovery")
            # UNIFIED RECOVERY: Only run after queue is fully ready
            await unified_recovery_scan()
        
        # Initialize image sync service for automatic image downloads
        await initialize_image_sync_service()
        
        # Recover active recordings from persistence
        await recover_active_recordings()
        
        # Start session cleanup service for production auth reliability
        await start_session_cleanup_service()
        
        logger.info("Background services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize background services: {e}", exc_info=True)
        raise

async def verify_queue_readiness() -> bool:
    """Verify that the background queue is fully ready to accept tasks"""
    try:
        # Direct access to the queue manager instead of HTTP API call
        from app.services.init.background_queue_init import get_task_queue_manager
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Get the queue manager directly
                queue_manager = get_task_queue_manager()
                
                if not queue_manager:
                    logger.debug(f"⚠️ Queue manager not found on attempt {attempt + 1}")
                elif not queue_manager.is_running:
                    logger.debug(f"⚠️ Queue manager not running on attempt {attempt + 1}")
                else:
                    # Check if we have at least one queue and it's active
                    status = queue_manager.get_status()
                    if status and 'queues' in status and len(status['queues']) > 0:
                        logger.info(f"✅ Queue readiness verified on attempt {attempt + 1} - Direct access to queue manager")
                        return True
                    else:
                        logger.debug(f"⚠️ Queue manager running but no active queues on attempt {attempt + 1}")
                    
            except Exception as e:
                logger.debug(f"⚠️ Queue readiness check failed on attempt {attempt + 1}: {e}")
            
            # Always wait before retry (except on last attempt)
            if attempt < max_attempts - 1:
                await asyncio.sleep(2)  # Wait before retry
        
        logger.warning(f"⚠️ Queue readiness verification failed after {max_attempts} attempts")
        return False
        
    except Exception as e:
        logger.error(f"❌ Error verifying queue readiness: {e}")
        return False

async def unified_recovery_scan():
    """Unified recovery scan replacing multiple overlapping services"""
    try:
        logger.info("🔄 Starting unified recovery scan...")
        
        from app.services.recording.unified_recovery_service import get_unified_recovery_service
        
        # Get the unified recovery service
        recovery_service = await get_unified_recovery_service()
        
        # Run comprehensive recovery scan
        stats = await recovery_service.comprehensive_recovery_scan(
            max_age_hours=72,  # Process recordings from last 3 days
            dry_run=False
        )
        
        logger.info(f"🔄 Unified recovery completed: "
                   f"orphaned_segments={stats.orphaned_segments}, "
                   f"failed_post_processing={stats.failed_post_processing}, "
                   f"recovered={stats.recovered_recordings}, "
                   f"triggered_pp={stats.triggered_post_processing}, "
                   f"size={stats.total_size_gb:.1f}GB")
        
    except Exception as e:
        logger.error(f"❌ Unified recovery scan failed: {e}", exc_info=True)
        # Don't raise - this is not critical for startup


async def recover_active_recordings():
    """Recover active recordings from persistent state"""
    try:
        logger.info("Recovering active recordings from persistent state...")
        
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
