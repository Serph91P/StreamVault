#!/usr/bin/env python3
"""
Manual Queue Service Starter
This script manually starts the queue service to debug why it's not running
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Configure logging for detailed debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("manual_queue_start")

async def start_queue_service():
    """Manually start the queue service and debug why it fails"""
    try:
        logger.info("🔧 Manually starting queue service...")
        
        # Import the queue service
        from app.services.init.background_queue_init import get_background_queue_service
        
        # Get the service instance
        queue_service = get_background_queue_service()
        
        # Check initial state
        initial_stats = await queue_service.get_queue_stats()
        logger.info(f"📊 Initial queue stats: {initial_stats}")
        
        # Try to start the service manually
        logger.info("🚀 Starting queue service...")
        await queue_service.start()
        
        # Check state after start
        after_stats = await queue_service.get_queue_stats()
        logger.info(f"📊 Queue stats after start: {after_stats}")
        
        # Check if workers are running
        if after_stats['is_running']:
            logger.info("✅ Queue service is now running!")
        else:
            logger.error("❌ Queue service failed to start!")
            
        # Test a simple task
        logger.info("🧪 Testing task creation...")
        
        # Import models
        from app.database import SessionLocal
        from app.models import Recording
        
        # Find a test recording
        with SessionLocal() as db:
            test_recording = db.query(Recording).filter(
                Recording.status.in_(['completed', 'stopped'])
            ).first()
            
            if test_recording:
                logger.info(f"Found test recording: {test_recording.id}")
                
                # Try to manually enqueue post-processing
                from app.services.init.background_queue_init import enqueue_recording_post_processing
                
                success = await enqueue_recording_post_processing(
                    stream_id=test_recording.stream_id,
                    recording_id=test_recording.id,
                    ts_file_path=test_recording.path,
                    output_dir=str(Path(test_recording.path).parent),
                    streamer_name=test_recording.stream.streamer.username,
                    started_at=test_recording.start_time.isoformat(),
                    cleanup_ts_file=False  # Don't cleanup for test
                )
                
                logger.info(f"Task enqueue result: {success}")
                
                # Monitor for 10 seconds
                for i in range(10):
                    await asyncio.sleep(1)
                    current_stats = await queue_service.get_queue_stats()
                    logger.info(f"[{i+1:2d}s] Queue stats: {current_stats}")
                    
                    if current_stats['total_tasks'] > 0:
                        logger.info(f"✅ Tasks are being processed!")
                        break
                else:
                    logger.warning("⚠️ No tasks appeared in queue")
            else:
                logger.warning("No test recording found")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to start queue service: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    result = asyncio.run(start_queue_service())
    if result:
        print("✅ Queue service debugging completed")
    else:
        print("❌ Queue service debugging failed")
        sys.exit(1)
