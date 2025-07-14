"""
Active Recordings Broadcaster Service

This service periodically sends active recordings updates via WebSocket
to replace the frontend polling mechanism.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.dependencies import websocket_manager
from app.services.recording.recording_service import RecordingService

logger = logging.getLogger("streamvault")

class ActiveRecordingsBroadcaster:
    def __init__(self, recording_service: RecordingService):
        self.recording_service = recording_service
        self.is_running = False
        self.broadcast_task: Optional[asyncio.Task] = None
        self.broadcast_interval = 10  # seconds (instead of 5 second polling)
        
    async def start(self):
        """Start the periodic broadcast task"""
        if self.is_running:
            logger.warning("ActiveRecordingsBroadcaster is already running")
            return
            
        self.is_running = True
        self.broadcast_task = asyncio.create_task(self._broadcast_loop())
        logger.info("ActiveRecordingsBroadcaster started")
        
    async def stop(self):
        """Stop the periodic broadcast task"""
        if not self.is_running:
            return
            
        self.is_running = False
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass
            self.broadcast_task = None
            
        logger.info("ActiveRecordingsBroadcaster stopped")
        
    async def _broadcast_loop(self):
        """Main broadcast loop that sends active recordings updates"""
        logger.info(f"Starting active recordings broadcast loop (interval: {self.broadcast_interval}s)")
        
        try:
            while self.is_running:
                try:
                    # Send active recordings update via WebSocket
                    await self.recording_service.send_active_recordings_websocket_update()
                    
                    # Wait for the next broadcast interval
                    await asyncio.sleep(self.broadcast_interval)
                    
                except Exception as e:
                    logger.error(f"Error in active recordings broadcast loop: {e}", exc_info=True)
                    # Wait a bit before retrying
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            logger.info("Active recordings broadcast loop cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in active recordings broadcast loop: {e}", exc_info=True)
        finally:
            logger.info("Active recordings broadcast loop ended")
            
    async def send_immediate_update(self):
        """Send an immediate update without waiting for the next interval"""
        try:
            await self.recording_service.send_active_recordings_websocket_update()
        except Exception as e:
            logger.error(f"Error sending immediate active recordings update: {e}", exc_info=True)

# Global instance
active_recordings_broadcaster: Optional[ActiveRecordingsBroadcaster] = None

async def start_active_recordings_broadcaster(recording_service: RecordingService):
    """Start the active recordings broadcaster"""
    global active_recordings_broadcaster
    
    if active_recordings_broadcaster is not None:
        logger.warning("ActiveRecordingsBroadcaster already exists")
        return
        
    active_recordings_broadcaster = ActiveRecordingsBroadcaster(recording_service)
    await active_recordings_broadcaster.start()
    
async def stop_active_recordings_broadcaster():
    """Stop the active recordings broadcaster"""
    global active_recordings_broadcaster
    
    if active_recordings_broadcaster is not None:
        await active_recordings_broadcaster.stop()
        active_recordings_broadcaster = None

async def send_immediate_active_recordings_update():
    """Send an immediate active recordings update"""
    global active_recordings_broadcaster
    
    if active_recordings_broadcaster is not None:
        await active_recordings_broadcaster.send_immediate_update()
