from fastapi import WebSocket
from typing import List, Dict, Any
from starlette.websockets import WebSocketState
import logging
import json
from datetime import datetime
import asyncio

logger = logging.getLogger('streamvault')

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # Use dict instead of list
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        # Use a more reliable client identifier that includes user agent
        client_info = f"{websocket.client.host}:{websocket.client.port}"
        connection_id = id(websocket)  # Use object ID as unique identifier
        
        async with self._lock:
            # Clean up any stale connections first
            await self._cleanup_stale_connections()
            
            self.active_connections[connection_id] = websocket
            
        connection_count = len(self.active_connections)
        logger.info(f"🔌 WebSocket connected: {client_info} (ID: {connection_id}) - Total connections: {connection_count}")
        
        await self.send_notification_to_socket(websocket, {
            "type": "connection.status",
            "data": {
                "status": "connected",
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"StreamVault WebSocket connected - {connection_count} total connections",
                "connection_id": connection_id
            }
        })

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            connection_id = id(websocket)
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
                connection_count = len(self.active_connections)
                logger.info(f"🔌 WebSocket disconnected: {websocket.client} (ID: {connection_id}) - Remaining connections: {connection_count}")
    
    async def _cleanup_stale_connections(self):
        """Remove stale/closed WebSocket connections"""
        stale_connections = []
        for connection_id, ws in self.active_connections.items():
            if ws.application_state != WebSocketState.CONNECTED:
                stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            del self.active_connections[connection_id]
            logger.debug(f"🧹 Cleaned up stale connection: {connection_id}")
        
        if stale_connections:
            logger.info(f"🧹 Cleaned up {len(stale_connections)} stale connections")

    async def send_notification_to_socket(self, websocket: WebSocket, message: Dict[str, Any]):
        try:
            if websocket.application_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
                return True
        except Exception as e:
            logger.error(f"Failed to send message to {websocket.client}: {e}")
            await self.disconnect(websocket)
            return False

    async def send_notification(self, message: dict):
        # Only log for non-routine broadcasts or when there's actual data
        should_log = (message.get("type") != "active_recordings_update" or 
                     bool(message.get("data")) or 
                     len(self.active_connections) <= 2)
        
        if should_log:
            logger.debug(f"WebSocketManager: Attempting to send notification: {message}")
            
        async with self._lock:
            active_sockets = list(self.active_connections.values())
    
        if not active_sockets:
            if should_log:
                logger.warning("WebSocketManager: No active WebSocket connections")
            return

        for ws in active_sockets:
            try:
                await ws.send_json(message)
                if should_log:
                    logger.debug(f"WebSocketManager: Notification sent to {ws.client}")
            except Exception as e:
                logger.error(f"WebSocketManager: Failed to send to {ws.client}: {e}")
                # Remove failed connection
                await self.disconnect(ws)

    async def send_active_recordings_update(self, active_recordings: List[Dict[str, Any]]):
        """Send active recordings update to all connected clients"""
        message = {
            "type": "active_recordings_update",
            "data": active_recordings,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_notification(message)
        # Only log when there are active recordings or few clients
        if active_recordings or len(self.active_connections) <= 2:
            logger.debug(f"WebSocketManager: Sent active recordings update to {len(self.active_connections)} clients")

    async def send_recording_started(self, recording_info: Dict[str, Any]):
        """Send recording started notification"""
        message = {
            "type": "recording_started",
            "data": recording_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_notification(message)
        logger.info(f"WebSocketManager: Sent recording started notification for {recording_info.get('streamer_name', 'unknown')}")

    async def send_recording_stopped(self, recording_info: Dict[str, Any]):
        """Send recording stopped notification"""
        message = {
            "type": "recording_stopped",
            "data": recording_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_notification(message)
        logger.info(f"WebSocketManager: Sent recording stopped notification for {recording_info.get('streamer_name', 'unknown')}")

    async def send_queue_stats_update(self, stats: Dict[str, Any]):
        """Send background queue stats update"""
        message = {
            "type": "queue_stats_update",
            "data": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_notification(message)
        logger.debug(f"WebSocketManager: Sent queue stats update: {stats}")

    async def send_task_status_update(self, task_info: Dict[str, Any]):
        """Send task status update"""
        message = {
            "type": "task_status_update",
            "data": task_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_notification(message)
        logger.debug(f"WebSocketManager: Sent task status update for task {task_info.get('id')}")

    async def send_task_progress_update(self, task_id: str, progress: float, message_text: str = None):
        """Send task progress update"""
        message = {
            "type": "task_progress_update",
            "data": {
                "task_id": task_id,
                "progress": progress,
                "message": message_text
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_notification(message)
        logger.debug(f"WebSocketManager: Sent progress update for task {task_id}: {progress}%")

    async def send_recording_job_update(self, recording_info: Dict[str, Any]):
        """Send recording job update (streamlink/ffmpeg status)"""
        message = {
            "type": "recording_job_update",
            "data": recording_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_notification(message)
        logger.debug(f"WebSocketManager: Sent recording job update for {recording_info.get('streamer_name')}")
