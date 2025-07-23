"""
Startup initialization for background services
"""
import logging
from app.services.init.background_queue_init import initialize_background_queue, shutdown_background_queue

logger = logging.getLogger("streamvault")

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
    """Initialize all background services at startup"""
    try:
        logger.info("Initializing background services...")
        
        # Initialize VAPID keys for push notifications
        await initialize_vapid_keys()
        
        # Initialize background queue
        await initialize_background_queue()
        
        # Initialize image sync service for automatic image downloads
        await initialize_image_sync_service()
        
        # Recover active recordings from persistence
        await recover_active_recordings()
        
        # Recover orphaned recordings (unfinished post-processing jobs)
        await recover_orphaned_recordings()
        
        # Start automatic recording database fix service
        await start_recording_auto_fix_service()
        
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
        
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        
        # Get orphaned recovery service
        recovery_service = await get_orphaned_recovery_service()
        
        # First get statistics
        stats = await recovery_service.get_orphaned_statistics(max_age_hours=48)
        
        if stats.get("total_orphaned", 0) > 0:
            logger.info(f"Found {stats['total_orphaned']} orphaned recordings ({stats['total_size_gb']} GB)")
            
            # Trigger recovery for orphaned recordings
            result = await recovery_service.scan_and_recover_orphaned_recordings(
                max_age_hours=48,  # Only process recordings from last 48 hours
                dry_run=False
            )
            
            if result["recovery_triggered"] > 0:
                logger.info(f"Triggered post-processing for {result['recovery_triggered']} orphaned recordings")
            else:
                logger.info("No orphaned recordings required processing")
        else:
            logger.info("No orphaned recordings found")
        
    except Exception as e:
        logger.error(f"Failed to recover orphaned recordings: {e}", exc_info=True)
        # Don't raise - this is not critical for startup


async def initialize_image_sync_service():
    """Initialize automatic image sync service"""
    try:
        logger.info("Initializing automatic image sync service...")
        
        from app.services.images.auto_image_sync_service import auto_image_sync_service
        
        # Start the background sync worker
        await auto_image_sync_service.start_sync_worker()
        
        # Perform initial sync of all existing categories and streamers
        await auto_image_sync_service.sync_all_existing_categories()
        await auto_image_sync_service.sync_all_existing_streamers()
        
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
