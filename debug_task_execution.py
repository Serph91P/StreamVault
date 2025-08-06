#!/usr/bin/env python3
"""
Debug script to investigate task execution pipeline
Traces the complete flow from recovery task creation to handler execution
This script should be run INSIDE the Docker container
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

logger = logging.getLogger("debug_task_execution")

async def debug_single_recording():
    """Debug a single recording that should have failed post-processing"""
    try:
        logger.info("🔍 Starting single recording debug...")
        
        # Import modules (these should work in the container)
        from app.database import SessionLocal
        from app.models import Recording, Stream, Streamer
        from app.services.init.background_queue_init import get_background_queue_service
        from datetime import datetime, timedelta
        
        # Check for a specific failed recording
        with SessionLocal() as db:
            # Get recordings from the last 72 hours that need post-processing
            cutoff_time = datetime.now() - timedelta(hours=72)
            
            failed_recordings = db.query(Recording).join(Stream).join(Streamer).filter(
                Recording.status.in_(['completed', 'stopped']),
                Recording.start_time >= cutoff_time
            ).all()
            
            logger.info(f"Found {len(failed_recordings)} recent recordings")
            
            # Find the first one that has TS file but no MP4
            test_recording = None
            for recording in failed_recordings:
                if not recording.path:
                    continue
                    
                ts_path = Path(recording.path)
                mp4_path = ts_path.with_suffix('.mp4')
                
                if ts_path.exists() and not mp4_path.exists():
                    test_recording = recording
                    logger.info(f"✅ Found test recording: ID={recording.id}, streamer={recording.stream.streamer.username}")
                    logger.info(f"   TS file: {ts_path} (exists: {ts_path.exists()})")
                    if ts_path.exists():
                        file_size = ts_path.stat().st_size / 1024 / 1024
                        logger.info(f"   File size: {file_size:.1f} MB")
                    logger.info(f"   MP4 file: {mp4_path} (exists: {mp4_path.exists()})")
                    break
        
        if not test_recording:
            logger.warning("❌ No suitable test recording found")
            return False
        
        # Get queue service
        logger.info("� Getting background queue service...")
        queue_service = get_background_queue_service()
        
        # Check initial queue state
        initial_stats = await queue_service.get_queue_stats()
        logger.info(f"📊 Initial queue stats: {initial_stats}")
        
        # Now manually trigger post-processing for this recording
        logger.info(f"� Manually triggering post-processing for recording {test_recording.id}...")
        
        from app.services.init.background_queue_init import enqueue_recording_post_processing
        
        # Get the required parameters
        stream_id = test_recording.stream_id
        recording_id = test_recording.id
        ts_file_path = test_recording.path
        output_dir = str(Path(ts_file_path).parent)
        streamer_name = test_recording.stream.streamer.username
        started_at = test_recording.start_time.isoformat()
        
        logger.info(f"📋 Task parameters:")
        logger.info(f"   stream_id: {stream_id}")
        logger.info(f"   recording_id: {recording_id}")
        logger.info(f"   ts_file_path: {ts_file_path}")
        logger.info(f"   output_dir: {output_dir}")
        logger.info(f"   streamer_name: {streamer_name}")
        logger.info(f"   started_at: {started_at}")
        
        # Trigger the post-processing
        try:
            success = await enqueue_recording_post_processing(
                stream_id=stream_id,
                recording_id=recording_id,
                ts_file_path=ts_file_path,
                output_dir=output_dir,
                streamer_name=streamer_name,
                started_at=started_at,
                cleanup_ts_file=True
            )
            logger.info(f"✅ Post-processing enqueued: {success}")
        except Exception as e:
            logger.error(f"❌ Failed to enqueue post-processing: {e}", exc_info=True)
            return False
        
        # Wait a moment for tasks to be created
        await asyncio.sleep(2)
        
        # Check queue state after enqueueing
        after_stats = await queue_service.get_queue_stats()
        logger.info(f"📊 Queue stats after enqueueing: {after_stats}")
        
        # Monitor the queue for 30 seconds
        logger.info("👀 Monitoring queue for 30 seconds...")
        for i in range(30):
            await asyncio.sleep(1)
            current_stats = await queue_service.get_queue_stats()
            
            if current_stats['total_tasks'] > 0:
                logger.info(f"   [{i+1:2d}s] Tasks: total={current_stats['total_tasks']}, "
                          f"active={current_stats['active_tasks']}, "
                          f"pending={current_stats['pending_tasks']}, "
                          f"failed={current_stats['failed_tasks']}")
            elif i % 5 == 0:  # Log every 5 seconds if no tasks
                logger.info(f"   [{i+1:2d}s] No tasks in queue")
        
        # Final check - see if MP4 was created
        mp4_path = Path(test_recording.path).with_suffix('.mp4')
        logger.info(f"🎯 Final check - MP4 created: {mp4_path.exists()}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Debug script failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    result = asyncio.run(debug_single_recording())
    if result:
        print("✅ Debug completed successfully")
    else:
        print("❌ Debug failed")
        sys.exit(1)
