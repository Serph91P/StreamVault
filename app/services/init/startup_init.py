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
        
        # Initialize image sync service for automatic image downloads
        await initialize_image_sync_service()
        
        # Recover active recordings from persistence
        await recover_active_recordings()
        
        # Initialize failed recording recovery service BEFORE orphaned recovery
        await initialize_failed_recording_recovery()
        
        # Recover orphaned recordings (unfinished post-processing jobs)
        await recover_orphaned_recordings()
        
        # Start automatic recording database fix service
        await start_recording_auto_fix_service()
        
        # Start session cleanup service for production auth reliability
        await start_session_cleanup_service()
        
        logger.info("Background services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize background services: {e}", exc_info=True)
        raise

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

async def recover_orphaned_recordings():
    """Recover orphaned .ts files that need post-processing"""
    try:
        logger.info("Starting orphaned recordings recovery scan...")
        
        # PRODUCTION FIX: Check if too many orphaned checks are already running
        try:
            from app.services.background_queue_service import get_background_queue_service
            queue_service = get_background_queue_service()
            if queue_service:
                active_tasks = queue_service.get_active_tasks()
                orphaned_check_count = sum(1 for task in active_tasks.values() 
                                         if task.task_type == 'orphaned_recovery_check')
                
                if orphaned_check_count > 0:
                    logger.info(f"🔍 STARTUP_ORPHANED_SKIP: {orphaned_check_count} orphaned checks already running, skipping startup recovery")
                    return
        except Exception as e:
            logger.debug(f"Could not check active tasks: {e}")
        
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        
        # Get orphaned recovery service
        recovery_service = await get_orphaned_recovery_service()
        
        # First get statistics
        stats = await recovery_service.get_orphaned_statistics(max_age_hours=48)
        
        if stats.get("total_orphaned", 0) > 0:
            logger.info(f"Found {stats['total_orphaned']} orphaned recordings ({stats['total_size_gb']} GB)")
            
            # PRODUCTION FIX: Limit startup recovery to prevent queue flooding
            if stats["total_orphaned"] > 10:
                logger.warning(f"🔍 STARTUP_ORPHANED_LIMIT: Too many orphaned recordings ({stats['total_orphaned']}), limiting to background processing")
                return
            
            # Trigger recovery for orphaned recordings with timeout
            import asyncio
            try:
                result = await asyncio.wait_for(
                    recovery_service.scan_and_recover_orphaned_recordings(
                        max_age_hours=48,  # Only process recordings from last 48 hours
                        dry_run=False
                    ),
                    timeout=60.0  # 1 minute timeout for startup
                )
                
                if result["recovery_triggered"] > 0:
                    logger.info(f"Triggered post-processing for {result['recovery_triggered']} orphaned recordings")
                else:
                    logger.info("No orphaned recordings required processing")
            except asyncio.TimeoutError:
                logger.warning("🔍 STARTUP_ORPHANED_TIMEOUT: Orphaned recovery timed out at startup, will retry in background")
        else:
            logger.info("No orphaned recordings found")
        
    except Exception as e:
        logger.error(f"Failed to recover orphaned recordings: {e}", exc_info=True)
        # Don't raise - this is not critical for startup


async def initialize_failed_recording_recovery():
    """Initialize automatic failed recording recovery service"""
    try:
        logger.info("🔧 Initializing failed recording recovery service...")
        
        from app.services.recording.failed_recording_recovery_service import get_failed_recovery_service
        
        # Start the failed recording recovery service
        recovery_service = await get_failed_recovery_service()
        
        logger.info("🔧 Failed recording recovery service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize failed recording recovery service: {e}", exc_info=True)
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

async def start_recording_auto_fix_service():
    """Start automatic recording database fix service"""
    try:
        logger.info("Starting automatic recording database fix service...")
        
        from app.services.recording.recording_auto_fix_service import recording_auto_fix_service
        
        # Start the auto-fix service
        await recording_auto_fix_service.start()
        
        logger.info("Recording auto-fix service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start recording auto-fix service: {e}", exc_info=True)
        # Don't raise - this is not critical for startup

async def shutdown_background_services():
    """Shutdown all background services"""
    try:
        logger.info("Shutting down background services...")
        
        # Shutdown recording auto-fix service
        try:
            from app.services.recording.recording_auto_fix_service import recording_auto_fix_service
            await recording_auto_fix_service.stop()
        except Exception as e:
            logger.error(f"Error shutting down recording auto-fix service: {e}")
        
        # Shutdown image sync service
        from app.services.images.auto_image_sync_service import auto_image_sync_service
        await auto_image_sync_service.stop_sync_worker()
        
        # Shutdown background queue
        await shutdown_background_queue()
        
        logger.info("Background services shut down successfully")
        
    except Exception as e:
        logger.error(f"Failed to shutdown background services: {e}", exc_info=True)
        raise
