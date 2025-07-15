"""
State Persistence Service for Active Recordings

This service manages the persistent state of active recordings,
enabling recovery after application restarts.
"""
import os
import logging

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import SessionLocal
from app.models import ActiveRecordingState, Stream, Recording
from app.utils.structured_logging import log_with_context

logger = logging.getLogger("streamvault")

class StatePersistenceService:
    """Service for managing persistent state of active recordings"""
    
    def __init__(self):
        self.heartbeat_interval = 60  # seconds
        self.stale_timeout = 300  # 5 minutes
        self.is_running = False
        self.heartbeat_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the state persistence service"""
        if self.is_running:
            logger.warning("StatePersistenceService already running")
            return
            
        self.is_running = True
        
        # Clean up stale entries on startup
        await self.cleanup_stale_entries()
        
        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("StatePersistenceService started")
        
    async def stop(self):
        """Stop the state persistence service"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
                
        logger.info("StatePersistenceService stopped")
        
    async def save_active_recording(
        self,
        stream_id: int,
        recording_id: int,
        process_id: int,
        process_identifier: str,
        streamer_name: str,
        started_at: datetime,
        ts_output_path: str,
        force_mode: bool = False,
        quality: str = 'best',
        config: Optional[Dict[str, Any]] = None
    ) -> ActiveRecordingState:
        """Save an active recording to persistent storage"""
        
        try:
            with SessionLocal() as db:
                # Check if entry already exists
                existing = db.query(ActiveRecordingState).filter(
                    ActiveRecordingState.stream_id == stream_id
                ).first()
                
                if existing:
                    # Update existing entry
                    existing.recording_id = recording_id
                    existing.process_id = process_id
                    existing.process_identifier = process_identifier
                    existing.streamer_name = streamer_name
                    existing.started_at = started_at
                    existing.ts_output_path = ts_output_path
                    existing.force_mode = force_mode
                    existing.quality = quality
                    existing.status = 'active'
                    existing.last_heartbeat = datetime.now(timezone.utc)
                    existing.set_config(config)
                    
                    state = existing
                else:
                    # Create new entry
                    state = ActiveRecordingState(
                        stream_id=stream_id,
                        recording_id=recording_id,
                        process_id=process_id,
                        process_identifier=process_identifier,
                        streamer_name=streamer_name,
                        started_at=started_at,
                        ts_output_path=ts_output_path,
                        force_mode=force_mode,
                        quality=quality,
                        status='active',
                        last_heartbeat=datetime.now(timezone.utc)
                    )
                    state.set_config(config)
                    db.add(state)
                
                db.commit()
                
                log_with_context(
                    logger, 'info',
                    f"Saved active recording state for {streamer_name}",
                    stream_id=stream_id,
                    process_id=process_id,
                    operation='state_persistence'
                )
                
                return state
                
        except Exception as e:
            logger.error(f"Error saving active recording state: {e}", exc_info=True)
            raise
            
    async def remove_active_recording(self, stream_id: int) -> bool:
        """Remove an active recording from persistent storage"""
        
        try:
            with SessionLocal() as db:
                result = db.query(ActiveRecordingState).filter(
                    ActiveRecordingState.stream_id == stream_id
                ).delete()
                
                db.commit()
                
                if result > 0:
                    log_with_context(
                        logger, 'info',
                        f"Removed active recording state for stream {stream_id}",
                        stream_id=stream_id,
                        operation='state_persistence'
                    )
                    return True
                else:
                    logger.warning(f"No active recording state found for stream {stream_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error removing active recording state: {e}", exc_info=True)
            return False
            
    async def update_heartbeat(self, stream_id: int) -> bool:
        """Update heartbeat for an active recording"""
        
        try:
            with SessionLocal() as db:
                state = db.query(ActiveRecordingState).filter(
                    ActiveRecordingState.stream_id == stream_id
                ).first()
                
                if state:
                    state.last_heartbeat = datetime.now(timezone.utc)
                    db.commit()
                    return True
                else:
                    logger.warning(f"No active recording state found for heartbeat update: {stream_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error updating heartbeat: {e}", exc_info=True)
            return False
            
    async def get_all_active_recordings(self) -> List[ActiveRecordingState]:
        """Get all active recordings from persistent storage"""
        
        try:
            with SessionLocal() as db:
                states = db.query(ActiveRecordingState).filter(
                    ActiveRecordingState.status == 'active'
                ).all()
                
                return states
                
        except Exception as e:
            logger.error(f"Error getting active recordings: {e}", exc_info=True)
            return []
            
    async def cleanup_stale_entries(self) -> int:
        """Clean up stale entries where processes no longer exist"""
        
        try:
            with SessionLocal() as db:
                states = db.query(ActiveRecordingState).filter(
                    ActiveRecordingState.status == 'active'
                ).all()
                
                removed_count = 0
                
                for state in states:
                    # Check if process still exists
                    if not self._process_exists(state.process_id):
                        logger.warning(f"Process {state.process_id} no longer exists, removing state for {state.streamer_name}")
                        db.delete(state)
                        removed_count += 1
                    # Check if entry is stale
                    elif state.is_stale(self.stale_timeout):
                        logger.warning(f"Stale entry detected for {state.streamer_name}, removing")
                        db.delete(state)
                        removed_count += 1
                
                db.commit()
                
                if removed_count > 0:
                    logger.info(f"Cleaned up {removed_count} stale recording state entries")
                    
                return removed_count
                
        except Exception as e:
            logger.error(f"Error cleaning up stale entries: {e}", exc_info=True)
            return 0
            
    async def recover_active_recordings(self) -> List[Dict[str, Any]]:
        """Recover active recordings from persistent storage
        
        Returns:
            List of recording info dicts that can be used to restore memory state
        """
        
        try:
            states = await self.get_all_active_recordings()
            recoverable_recordings = []
            
            for state in states:
                # Verify process still exists
                if not self._process_exists(state.process_id):
                    logger.warning(f"Process {state.process_id} no longer exists, cannot recover {state.streamer_name}")
                    await self.remove_active_recording(state.stream_id)
                    continue
                    
                # Verify output file exists
                if not os.path.exists(state.ts_output_path):
                    logger.warning(f"Output file {state.ts_output_path} not found, cannot recover {state.streamer_name}")
                    await self.remove_active_recording(state.stream_id)
                    continue
                    
                # Build recovery info
                recovery_info = {
                    'stream_id': state.stream_id,
                    'recording_id': state.recording_id,
                    'process_id': state.process_id,
                    'process_identifier': state.process_identifier,
                    'streamer_name': state.streamer_name,
                    'start_time': state.started_at,
                    'ts_output_path': state.ts_output_path,
                    'force_mode': state.force_mode,
                    'config': state.get_config()
                }
                
                recoverable_recordings.append(recovery_info)
                
            if recoverable_recordings:
                logger.info(f"Found {len(recoverable_recordings)} recoverable recordings")
            else:
                logger.info("No recoverable recordings found")
                
            return recoverable_recordings
            
        except Exception as e:
            logger.error(f"Error recovering active recordings: {e}", exc_info=True)
            return []
            
    def _process_exists(self, pid: int) -> bool:
        """Check if a process exists"""
        try:
            if HAS_PSUTIL:
                return psutil.pid_exists(pid)
            else:
                # Fallback method when psutil is not available
                logger.warning("psutil not available, cannot check process existence")
                return False
        except Exception:
            return False
            
    async def _heartbeat_loop(self):
        """Background task to maintain heartbeats and cleanup stale entries"""
        
        logger.info(f"Starting state persistence heartbeat loop (interval: {self.heartbeat_interval}s)")
        
        try:
            while self.is_running:
                try:
                    # Cleanup stale entries periodically
                    await self.cleanup_stale_entries()
                    
                    # Sleep until next heartbeat
                    await asyncio.sleep(self.heartbeat_interval)
                    
                except Exception as e:
                    logger.error(f"Error in state persistence heartbeat loop: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Wait before retrying
                    
        except asyncio.CancelledError:
            logger.info("State persistence heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in state persistence heartbeat loop: {e}", exc_info=True)
        finally:
            logger.info("State persistence heartbeat loop ended")

# Global instance
state_persistence_service = StatePersistenceService()
