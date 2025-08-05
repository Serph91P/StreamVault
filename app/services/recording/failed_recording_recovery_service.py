"""
Failed Recording Recovery Service

Automatically detects and recovers failed recordings by finding their segment files
and triggering segment concatenation.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import Recording, Stream, Streamer

logger = logging.getLogger("streamvault")


class FailedRecordingRecoveryService:
    """Service for automatically recovering failed recordings"""
    
    def __init__(self):
        self.check_interval_minutes = 30  # Check every 30 minutes
        self.max_age_hours = 48  # Only process recordings younger than 48 hours
        self.is_running = False
        self.background_task = None
    
    async def start(self):
        """Start the automatic recovery service"""
        if self.is_running:
            logger.debug("Failed recording recovery service already running")
            return
            
        logger.info("🔧 Starting failed recording recovery service...")
        self.is_running = True
        
        # Run initial recovery on startup
        await self.scan_and_recover_failed_recordings()
        
        # Start background task
        self.background_task = asyncio.create_task(self._background_loop())
        logger.info("🔧 Failed recording recovery service started successfully")
    
    async def stop(self):
        """Stop the automatic recovery service"""
        if not self.is_running:
            return
            
        logger.info("🔧 Stopping failed recording recovery service...")
        self.is_running = False
        
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
            self.background_task = None
        
        logger.info("🔧 Failed recording recovery service stopped")
    
    async def _background_loop(self):
        """Background loop for periodic recovery checks"""
        try:
            while self.is_running:
                try:
                    await asyncio.sleep(self.check_interval_minutes * 60)
                    
                    if not self.is_running:
                        break
                    
                    logger.debug("🔧 Running periodic failed recording recovery check...")
                    await self.scan_and_recover_failed_recordings()
                    
                except Exception as e:
                    logger.error(f"Error in failed recording recovery loop: {e}", exc_info=True)
                    # Wait a bit before retrying
                    await asyncio.sleep(60)
                    
        except asyncio.CancelledError:
            logger.debug("🔧 Failed recording recovery background loop cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in failed recording recovery loop: {e}", exc_info=True)
    
    async def scan_and_recover_failed_recordings(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Scan for failed recordings and attempt recovery
        
        Args:
            dry_run: If True, only return what would be recovered without doing it
        
        Returns:
            Dictionary with recovery statistics
        """
        logger.info(f"🔧 FAILED_RECOVERY_SCAN_START: dry_run={dry_run}")
        
        result = {
            "scanned_recordings": 0,
            "failed_found": 0,
            "recoverable_found": 0,
            "recovery_triggered": 0,
            "recovery_failed": 0,
            "skipped_no_segments": 0,
            "details": [],
            "errors": []
        }
        
        try:
            with SessionLocal() as db:
                # Find failed recordings from the last 48 hours
                cutoff = datetime.utcnow() - timedelta(hours=self.max_age_hours)
                
                failed_recordings = (
                    db.query(Recording)
                    .join(Stream)
                    .join(Streamer)
                    .filter(Recording.status == 'failed')
                    .filter(Recording.created_at >= cutoff)
                    .all()
                )
                
                result["scanned_recordings"] = len(failed_recordings)
                logger.info(f"🔧 Found {len(failed_recordings)} failed recordings to check")
                
                for recording in failed_recordings:
                    try:
                        result["failed_found"] += 1
                        
                        # Look for segment files
                        segment_info = await self._find_segment_files(recording)
                        
                        recovery_info = {
                            "recording_id": recording.id,
                            "streamer_name": recording.stream.streamer.username if recording.stream and recording.stream.streamer else "Unknown",
                            "original_path": recording.path,
                            "segments_found": len(segment_info["segments"]),
                            "segments_dir": segment_info["segments_dir"],
                            "recovery_triggered": False,
                            "error": None
                        }
                        
                        if not segment_info["segments"]:
                            result["skipped_no_segments"] += 1
                            recovery_info["error"] = "No segment files found"
                            logger.debug(f"🔧 No segments found for recording {recording.id}")
                        else:
                            result["recoverable_found"] += 1
                            logger.info(f"🔧 Found {len(segment_info['segments'])} segments for recording {recording.id}")
                            
                            if not dry_run:
                                # Trigger segment concatenation
                                success = await self._trigger_segment_concatenation(recording, segment_info, db)
                                
                                if success:
                                    result["recovery_triggered"] += 1
                                    recovery_info["recovery_triggered"] = True
                                    logger.info(f"✅ Recovery triggered for recording {recording.id}")
                                else:
                                    result["recovery_failed"] += 1
                                    recovery_info["error"] = "Failed to trigger segment concatenation"
                                    logger.error(f"❌ Failed to trigger recovery for recording {recording.id}")
                            else:
                                # Dry run - count as triggered
                                result["recovery_triggered"] += 1
                                recovery_info["recovery_triggered"] = True
                        
                        result["details"].append(recovery_info)
                        
                    except Exception as e:
                        result["recovery_failed"] += 1
                        result["errors"].append(f"Recording {recording.id}: {str(e)}")
                        logger.error(f"Error processing failed recording {recording.id}: {e}", exc_info=True)
        
        except Exception as e:
            result["errors"].append(f"Scan failed: {str(e)}")
            logger.error(f"Failed recording recovery scan failed: {e}", exc_info=True)
        
        logger.info(f"🔧 FAILED_RECOVERY_SCAN_COMPLETE: triggered={result['recovery_triggered']}, failed={result['recovery_failed']}")
        return result
    
    async def _find_segment_files(self, recording: Recording) -> Dict[str, Any]:
        """Find segment files for a failed recording"""
        segments = []
        segments_dir = None
        
        if not recording.path:
            return {"segments": segments, "segments_dir": segments_dir}
        
        # Construct expected segment directory path
        original_path = Path(recording.path)
        expected_segments_dir = original_path.parent / f"{original_path.stem}_segments"
        
        if expected_segments_dir.exists() and expected_segments_dir.is_dir():
            segments_dir = str(expected_segments_dir)
            
            # Find all .ts files in the segment directory
            for segment_file in expected_segments_dir.glob("*.ts"):
                if segment_file.is_file() and segment_file.stat().st_size > 0:
                    segments.append(str(segment_file))
            
            # Sort segments to maintain order
            segments.sort()
        
        return {"segments": segments, "segments_dir": segments_dir}
    
    async def _trigger_segment_concatenation(self, recording: Recording, segment_info: Dict[str, Any], db) -> bool:
        """Trigger segment concatenation for a failed recording"""
        try:
            from app.services.background_queue_service import background_queue_service
            
            # Update recording status to prevent double-processing
            recording.status = 'post_processing'
            recording.updated_at = datetime.utcnow()
            db.commit()
            
            # Prepare task data for segment concatenation
            output_path = recording.path  # Use original recording path as output
            
            task_data = {
                "recording_id": recording.id,
                "segment_files": segment_info["segments"],
                "output_path": output_path,
                "streamer_name": recording.stream.streamer.username if recording.stream and recording.stream.streamer else "Unknown",
                "stream_id": recording.stream_id,
                "started_at": recording.created_at.isoformat() if recording.created_at else datetime.utcnow().isoformat()
            }
            
            # Enqueue segment concatenation task
            task_id = await background_queue_service.enqueue_task(
                task_type="segment_concatenation",
                task_data=task_data,
                streamer_name=task_data["streamer_name"],
                priority="HIGH"
            )
            
            logger.info(f"🔧 SEGMENT_CONCATENATION_QUEUED: task_id={task_id}, recording_id={recording.id}")
            return True
            
        except Exception as e:
            # Revert status on error
            try:
                recording.status = 'failed'
                db.commit()
            except:
                pass
            
            logger.error(f"Failed to trigger segment concatenation for recording {recording.id}: {e}")
            return False
    
    async def recover_specific_recording(self, recording_id: int) -> Dict[str, Any]:
        """Manually trigger recovery for a specific recording"""
        try:
            with SessionLocal() as db:
                recording = db.query(Recording).filter(Recording.id == recording_id).first()
                if not recording:
                    return {
                        "success": False,
                        "error": f"Recording {recording_id} not found"
                    }
                
                if recording.status != 'failed':
                    return {
                        "success": False,
                        "error": f"Recording {recording_id} is not in failed status (current: {recording.status})"
                    }
                
                # Find segments
                segment_info = await self._find_segment_files(recording)
                
                if not segment_info["segments"]:
                    return {
                        "success": False,
                        "error": "No segment files found for this recording"
                    }
                
                # Trigger recovery
                success = await self._trigger_segment_concatenation(recording, segment_info, db)
                
                if success:
                    return {
                        "success": True,
                        "message": f"Recovery triggered for recording {recording_id}",
                        "segments_found": len(segment_info["segments"]),
                        "segments_dir": segment_info["segments_dir"]
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to trigger segment concatenation"
                    }
                    
        except Exception as e:
            logger.error(f"Error recovering recording {recording_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }


# Global service instance
_failed_recovery_service = None


async def get_failed_recovery_service() -> FailedRecordingRecoveryService:
    """Get or create the failed recovery service instance"""
    global _failed_recovery_service
    
    if _failed_recovery_service is None:
        _failed_recovery_service = FailedRecordingRecoveryService()
        await _failed_recovery_service.start()
    
    return _failed_recovery_service


async def stop_failed_recovery_service():
    """Stop the failed recovery service"""
    global _failed_recovery_service
    
    if _failed_recovery_service:
        await _failed_recovery_service.stop()
        _failed_recovery_service = None
