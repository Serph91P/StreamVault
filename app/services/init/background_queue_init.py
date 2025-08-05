"""
Background Queue Initialization
Sets up the background queue service with task handlers and dependency management
"""
import logging
import asyncio
from typing import Optional

from app.services.background_queue_service import background_queue_service
from app.services.processing.post_processing_task_handlers import post_processing_task_handlers

logger = logging.getLogger("streamvault")

# Backward compatibility alias - will be set after class definition
BackgroundQueueInit = None

class BackgroundQueueManager:
    """Manager for background queue initialization and lifecycle"""
    
    def __init__(self):
        self.is_initialized = False
        self.queue_service = background_queue_service
        self.task_handlers = post_processing_task_handlers
    
    async def initialize(self, enable_streamer_isolation: bool = True):
        """Initialize the background queue service with task handlers and production fixes"""
        if self.is_initialized:
            logger.debug("Background queue already initialized, skipping...")
            return
        
        if self.queue_service.is_running:
            logger.info("Background queue service is already running")
            self.is_initialized = True
            return
        
        logger.info(f"Initializing background queue service with production fixes (isolation: {enable_streamer_isolation})...")
        
        # Configure queue service with production fixes
        if hasattr(self.queue_service, 'queue_manager'):
            # Set streamer isolation on the queue manager
            self.queue_service.queue_manager.enable_streamer_isolation = enable_streamer_isolation
            if enable_streamer_isolation:
                logger.info("✅ Enabled streamer isolation for production concurrency fix")
        
        # Register task handlers
        self.queue_service.register_task_handler(
            'metadata_generation', 
            self.task_handlers.handle_metadata_generation
        )
        
        self.queue_service.register_task_handler(
            'chapters_generation',
            self.task_handlers.handle_chapters_generation
        )
        
        self.queue_service.register_task_handler(
            'mp4_remux',
            self.task_handlers.handle_mp4_remux
        )
        
        self.queue_service.register_task_handler(
            'mp4_validation',
            self.task_handlers.handle_mp4_validation
        )
        
        self.queue_service.register_task_handler(
            'thumbnail_generation',
            self.task_handlers.handle_thumbnail_generation
        )
        
        self.queue_service.register_task_handler(
            'cleanup',
            self.task_handlers.handle_cleanup
        )
        
        # Register orphaned recovery handler
        from app.services.recording.orphaned_recovery_tasks import handle_orphaned_recovery_check
        self.queue_service.register_task_handler(
            'orphaned_recovery_check',
            handle_orphaned_recovery_check
        )
        
        # Register segment concatenation handler
        from app.services.recording.segment_concatenation_task import handle_segment_concatenation
        self.queue_service.register_task_handler(
            'segment_concatenation',
            handle_segment_concatenation
        )
        
        # Start the queue service
        await self.queue_service.start()
        
        # Start automatic recovery service for production reliability
        try:
            from app.services.automatic_queue_recovery_service import get_recovery_service
            recovery_service = get_recovery_service()
            await recovery_service.start()
            logger.info("✅ Automatic queue recovery service started for production reliability")
        except Exception as e:
            logger.error(f"Failed to start automatic recovery service: {e}")
        
        self.is_initialized = True
        logger.info("✅ Background queue service initialized successfully with production fixes")
    
    async def shutdown(self):
        """Shutdown the background queue service"""
        if not self.is_initialized:
            return
        
        logger.info("Shutting down background queue service...")
        
        # Stop automatic recovery service first
        try:
            from app.services.automatic_queue_recovery_service import get_recovery_service
            recovery_service = get_recovery_service()
            await recovery_service.stop()
            logger.info("✅ Automatic queue recovery service stopped")
        except Exception as e:
            logger.error(f"Error stopping automatic recovery service: {e}")
        
        # Stop the queue service
        await self.queue_service.stop()
        
        # Clean up task handlers
        await self.task_handlers.cleanup()
        
        self.is_initialized = False
        logger.info("Background queue service shut down successfully")
    
    def get_queue_service(self):
        """Get the background queue service instance"""
        return self.queue_service
    
    def is_running(self) -> bool:
        """Check if the background queue service is running"""
        return self.is_initialized and self.queue_service.is_running

# Global instance
background_queue_manager = BackgroundQueueManager()

# Convenience functions
async def initialize_background_queue(enable_streamer_isolation: bool = True):
    """Initialize the background queue service with production fixes"""
    await background_queue_manager.initialize(enable_streamer_isolation=enable_streamer_isolation)

async def shutdown_background_queue():
    """Shutdown the background queue service"""
    await background_queue_manager.shutdown()

def get_background_queue_service():
    """Get the background queue service instance"""
    return background_queue_manager.get_queue_service()

# For backward compatibility
async def enqueue_recording_post_processing(
    stream_id: int,
    recording_id: int,
    ts_file_path: str,
    output_dir: str,
    streamer_name: str,
    started_at: str,
    cleanup_ts_file: bool = True
):
    """Enqueue a complete post-processing chain for a recording"""
    queue_service = get_background_queue_service()
    return await queue_service.enqueue_recording_post_processing(
        stream_id=stream_id,
        recording_id=recording_id,
        ts_file_path=ts_file_path,
        output_dir=output_dir,
        streamer_name=streamer_name,
        started_at=started_at,
        cleanup_ts_file=cleanup_ts_file
    )

async def enqueue_metadata_generation(
    stream_id: int,
    recording_id: int,
    mp4_file_path: str,
    output_dir: str,
    streamer_name: str,
    started_at: str
):
    """Enqueue metadata generation for an existing MP4 file"""
    queue_service = get_background_queue_service()
    return await queue_service.enqueue_metadata_generation(
        stream_id=stream_id,
        recording_id=recording_id,
        mp4_file_path=mp4_file_path,
        output_dir=output_dir,
        streamer_name=streamer_name,
        started_at=started_at
    )

async def enqueue_thumbnail_generation(
    stream_id: int,
    recording_id: int,
    mp4_file_path: str,
    output_dir: str,
    streamer_name: str,
    started_at: str
):
    """Enqueue thumbnail generation"""
    queue_service = get_background_queue_service()
    return await queue_service.enqueue_thumbnail_generation(
        stream_id=stream_id,
        recording_id=recording_id,
        mp4_file_path=mp4_file_path,
        output_dir=output_dir,
        streamer_name=streamer_name,
        started_at=started_at
    )

async def get_stream_task_status(stream_id: int):
    """Get the status of all tasks for a stream"""
    queue_service = get_background_queue_service()
    return await queue_service.get_stream_task_status(stream_id)

async def cancel_stream_tasks(stream_id: int):
    """Cancel all tasks for a stream"""
    queue_service = get_background_queue_service()
    return await queue_service.cancel_stream_tasks(stream_id)

# Set backward compatibility alias
BackgroundQueueInit = BackgroundQueueManager
