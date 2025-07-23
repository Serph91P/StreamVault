"""
Recording Auto-Fix Service

Automatically detects and fixes common recording issues:
1. Incorrect recording_path fields in database
2. Orphaned recording database entries running too long
3. Missing recording availability detection

This service runs automatically on startup and periodically in the background.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from app.database import SessionLocal
from app.models import Stream, Recording, Streamer

logger = logging.getLogger("streamvault")


class RecordingAutoFixService:
    """Automatically detects and fixes recording database inconsistencies"""
    
    def __init__(self):
        self.is_running = False
        self.background_task = None
        self.check_interval_minutes = 30  # Check every 30 minutes
        self.orphaned_max_hours = 24  # Max recording time before considering orphaned
        
    async def start(self):
        """Start the auto-fix service"""
        if self.is_running:
            logger.debug("Recording auto-fix service already running")
            return
            
        logger.info("Starting recording auto-fix service...")
        self.is_running = True
        
        # Run initial fixes on startup
        await self.run_initial_fixes()
        
        # Start background task
        self.background_task = asyncio.create_task(self._background_loop())
        logger.info("Recording auto-fix service started successfully")
    
    async def stop(self):
        """Stop the auto-fix service"""
        if not self.is_running:
            return
            
        logger.info("Stopping recording auto-fix service...")
        self.is_running = False
        
        if self.background_task:
            self.background_task.cancel()
            try:
                await self.background_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Recording auto-fix service stopped")
    
    async def run_initial_fixes(self):
        """Run initial fixes on startup"""
        try:
            logger.info("Running initial recording database fixes...")
            
            # Fix recording paths
            path_results = await self.auto_fix_recording_paths()
            logger.info(f"Fixed {path_results['fixed']} recording paths")
            
            # Clean orphaned recordings
            orphan_results = await self.auto_cleanup_orphaned_recordings()
            logger.info(f"Cleaned {orphan_results['cleaned']} orphaned recording entries")
            
            logger.info("Initial recording fixes completed successfully")
            
        except Exception as e:
            logger.error(f"Error during initial recording fixes: {e}", exc_info=True)
    
    async def _background_loop(self):
        """Background loop for periodic fixes"""
        try:
            while self.is_running:
                try:
                    await asyncio.sleep(self.check_interval_minutes * 60)
                    
                    if not self.is_running:
                        break
                    
                    logger.debug("Running periodic recording database maintenance...")
                    
                    # Run periodic fixes
                    await self.auto_fix_recording_paths()
                    await self.auto_cleanup_orphaned_recordings()
                    
                except Exception as e:
                    logger.error(f"Error in recording auto-fix background loop: {e}", exc_info=True)
                    # Wait a bit before retrying
                    await asyncio.sleep(60)
                    
        except asyncio.CancelledError:
            logger.debug("Recording auto-fix background loop cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in recording auto-fix background loop: {e}", exc_info=True)
    
    async def auto_fix_recording_paths(self) -> Dict[str, Any]:
        """Automatically fix recording_path fields based on actual file existence"""
        results = {
            "checked": 0,
            "fixed": 0,
            "errors": 0
        }
        
        try:
            with SessionLocal() as db:
                # Get all streams with potential recording files
                streams = db.query(Stream).filter(
                    Stream.ended_at.isnot(None)  # Only completed streams
                ).all()
                
                for stream in streams:
                    results["checked"] += 1
                    
                    try:
                        fixed = await self._fix_single_stream_path(stream, db)
                        if fixed:
                            results["fixed"] += 1
                            
                    except Exception as e:
                        logger.debug(f"Error fixing stream {stream.id} path: {e}")
                        results["errors"] += 1
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error in auto_fix_recording_paths: {e}", exc_info=True)
            results["errors"] += 1
        
        if results["fixed"] > 0:
            logger.info(f"Auto-fixed {results['fixed']} recording paths")
        
        return results
    
    async def _fix_single_stream_path(self, stream: Stream, db) -> bool:
        """Fix recording path for a single stream"""
        try:
            # Check if recording_path exists and is correct
            has_file = False
            correct_path = None
            
            # Look for recording file in expected location
            recordings_base = Path("/recordings")
            if not recordings_base.exists():
                return False
                
            # Get streamer info
            streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
            if not streamer:
                return False
                
            streamer_dir = recordings_base / streamer.username
            if not streamer_dir.exists():
                return False
            
            # Look for .ts or .mp4 files that could be this stream
            potential_files = []
            
            # Look for files around the stream time
            if stream.started_at:
                stream_date = stream.started_at.date()
                
                # Search for video files
                for ext in ['.ts', '.mp4']:
                    for recording_file in streamer_dir.rglob(f"*{ext}"):
                        try:
                            file_date = datetime.fromtimestamp(recording_file.stat().st_mtime).date()
                            if file_date == stream_date:
                                potential_files.append(recording_file)
                        except Exception:
                            continue
            
            # If we found files, use the most likely one
            if potential_files:
                # Prefer .mp4 over .ts
                mp4_files = [f for f in potential_files if f.suffix == '.mp4']
                if mp4_files:
                    correct_path = str(mp4_files[0])
                    has_file = True
                else:
                    correct_path = str(potential_files[0])
                    has_file = True
            
            # Determine if we need to update
            needs_update = False
            
            if has_file and not stream.recording_path:
                # File exists but recording_path is empty
                needs_update = True
            elif has_file and stream.recording_path and not Path(stream.recording_path).exists():
                # recording_path set but file doesn't exist at that path
                needs_update = True
            elif not has_file and stream.recording_path:
                # recording_path set but no file exists
                correct_path = None
                needs_update = True
            
            if needs_update:
                old_path = stream.recording_path
                stream.recording_path = correct_path
                logger.debug(f"Auto-fixed stream {stream.id} recording path: {old_path} -> {correct_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error fixing stream {stream.id} recording path: {e}")
            return False
    
    async def auto_cleanup_orphaned_recordings(self) -> Dict[str, Any]:
        """Automatically clean up orphaned database recording entries"""
        results = {
            "checked": 0,
            "cleaned": 0,
            "errors": 0
        }
        
        try:
            # Calculate cutoff time
            cutoff_time = datetime.utcnow() - timedelta(hours=self.orphaned_max_hours)
            
            with SessionLocal() as db:
                # Find recordings that are still "recording" but started too long ago
                orphaned_recordings = db.query(Recording).filter(
                    Recording.status == "recording",
                    Recording.start_time < cutoff_time
                ).all()
                
                for recording in orphaned_recordings:
                    results["checked"] += 1
                    
                    try:
                        # Mark as completed with current time
                        recording.status = "completed"
                        recording.end_time = datetime.utcnow()
                        if recording.start_time:
                            duration = recording.end_time - recording.start_time
                            recording.duration = duration.total_seconds()
                        
                        results["cleaned"] += 1
                        
                        logger.debug(f"Auto-cleaned orphaned recording {recording.id}")
                        
                    except Exception as e:
                        logger.debug(f"Error cleaning recording {recording.id}: {e}")
                        results["errors"] += 1
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Error in auto_cleanup_orphaned_recordings: {e}", exc_info=True)
            results["errors"] += 1
        
        if results["cleaned"] > 0:
            logger.info(f"Auto-cleaned {results['cleaned']} orphaned recording entries")
        
        return results
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get current service status"""
        return {
            "is_running": self.is_running,
            "check_interval_minutes": self.check_interval_minutes,
            "orphaned_max_hours": self.orphaned_max_hours,
            "background_task_running": self.background_task is not None and not self.background_task.done()
        }


# Global service instance
recording_auto_fix_service = RecordingAutoFixService()
