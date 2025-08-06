"""
Simple Recovery Service

Creates simple metadata_generation tasks without dependencies.
These work reliably compared to complex dependency chains.
"""

import logging
from typing import Dict, Any, List, TYPE_CHECKING
from datetime import datetime, timezone
from pathlib import Path

if TYPE_CHECKING:
    from ..services.recording.unified_recovery_service import UnifiedRecoveryService

logger = logging.getLogger("streamvault")


async def run_simple_reliable_recovery() -> Dict[str, Any]:
    """
    Performs simple, reliable recovery.
    
    Uses only single metadata_generation tasks without dependencies,
    as these are more reliable than complex chains.
    """
    results = {
        "start_time": datetime.now(timezone.utc).isoformat(),
        "simple_recovery": None,
        "total_recoveries": 0,
        "success": False
    }
    
    try:
        logger.info("🔧 Starting simple reliable recovery...")
        
        # Find failed recordings with Unified Recovery Service
        from ..services.recording.unified_recovery_service import get_unified_recovery_service
        unified_service = await get_unified_recovery_service()
        
        # Run only scan (dry_run=True) to find failed recordings
        unified_stats = await unified_service.comprehensive_recovery_scan(
            max_age_hours=72, 
            dry_run=True  # Only scan, don't create complex chains
        )
        
        failed_count = unified_stats.failed_post_processing
        logger.info(f"🔍 Found {failed_count} failed post-processing recordings")
        
        if failed_count > 0:
            # Use the scan results to create full post-processing chains
            recovery_triggered = await create_full_recovery_chains(unified_service)
            
            results["simple_recovery"] = {
                "success": True,
                "failed_found": failed_count,
                "recovery_triggered": recovery_triggered,
                "method": "full_post_processing_chains"
            }
            results["total_recoveries"] = recovery_triggered
            
            logger.info(f"✅ Simple recovery: {recovery_triggered} metadata_generation tasks created")
        else:
            results["simple_recovery"] = {
                "success": True,
                "failed_found": 0,
                "recovery_triggered": 0,
                "method": "full_post_processing_chains"
            }
            logger.info("ℹ️ No failed recordings found")
        
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = True
        
        logger.info(f"🎉 Simple recovery completed: {results['total_recoveries']} full post-processing chains created")
        return results
        
    except Exception as e:
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"❌ Simple recovery failed: {e}")
        return results


async def create_full_recovery_chains(unified_service: "UnifiedRecoveryService") -> int:
    """
    Creates full post-processing chains for failed recordings.
    
    Uses the proper enqueue_recording_post_processing to trigger complete chains
    with mp4_remux, chapters_generation, etc. - not just metadata.
    
    Args:
        unified_service: The unified recovery service instance
        
    Returns:
        Number of post-processing chains created.
    """
    from ..services.init.background_queue_init import enqueue_recording_post_processing
    from ..database import SessionLocal
    from ..models import Recording, Stream
    
    recovery_count = 0
    
    try:
        # The scan doesn't return individual recordings, so we need to find them ourselves
        # But we'll do it safely without complex joins
        db = SessionLocal()
        try:
            # Get all recordings that have a path but completed
            recordings = db.query(Recording).filter(
                Recording.path.isnot(None),
                Recording.status == 'completed'
            ).all()
            
            for recording in recordings:
                try:
                    if not recording.path:
                        continue
                        
                    # Check if TS exists but MP4 is missing
                    recording_path = Path(recording.path)
                    if not recording_path.exists():
                        continue
                        
                    # Check MP4
                    mp4_path = recording_path.parent / f"{recording_path.stem}.mp4"
                    if mp4_path.exists():
                        continue  # MP4 already exists
                        
                    # Get stream information for full post-processing
                    stream = db.query(Stream).filter(Stream.id == recording.stream_id).first()
                    if not stream:
                        logger.warning(f"⚠️ Stream {recording.stream_id} not found for recording {recording.id}")
                        continue
                        
                    # Get streamer name
                    streamer_name = stream.streamer.username if stream.streamer else f"stream_{stream.id}"
                    
                    # Validate that we have the required start_time
                    if not recording.start_time:
                        logger.warning(f"⚠️ Recording {recording.id} has no start_time; cannot trigger post-processing")
                        continue
                        
                    started_at = recording.start_time.isoformat()
                    output_dir = str(recording_path.parent)
                    
                    logger.info(f"🔍 Creating full post-processing chain for recording {recording.id}: {recording.path}")
                    
                    # Trigger full post-processing chain (NOT just metadata!)
                    success = await enqueue_recording_post_processing(
                        stream_id=recording.stream_id,
                        recording_id=recording.id,
                        ts_file_path=str(recording.path),
                        output_dir=output_dir,
                        streamer_name=streamer_name,
                        started_at=started_at,
                        cleanup_ts_file=True  # Clean up TS after successful MP4 creation
                    )
                    
                    if success:
                        recovery_count += 1
                        logger.info(f"✅ Created full post-processing chain for recording {recording.id}")
                    else:
                        logger.warning(f"⚠️ Failed to create post-processing chain for recording {recording.id}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to create recovery chain for recording {recording.id}: {e}")
                    continue
                    
        finally:
            db.close()
                    
    except Exception as e:
        logger.error(f"❌ Failed to create full recovery chains: {e}")
        
    return recovery_count
