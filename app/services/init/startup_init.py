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
        
        logger.info("Background services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize background services: {e}", exc_info=True)
        raise

async def shutdown_background_services():
    """Shutdown all background services"""
    try:
        logger.info("Shutting down background services...")
        
        # Shutdown background queue
        await shutdown_background_queue()
        
        logger.info("Background services shut down successfully")
        
    except Exception as e:
        logger.error(f"Failed to shutdown background services: {e}", exc_info=True)
        raise
