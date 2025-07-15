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
        client_id = f"{websocket.client.host}:{websocket.client.port}"
        async with self._lock:
            # Remove any existing connection for this client
            if client_id in self.active_connections:
                old_ws = self.active_connections[client_id]
                await self.disconnect(old_ws)
            self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {websocket.client}")
        
        await self.send_notification_to_socket(websocket, {
            "type": "connection.status",
            "data": {
                "status": "connected",
                "timestamp": datetime.utcnow().isoformat(),
                "message": "StreamVault WebSocket connected"
            }
        })

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            client_id = f"{websocket.client.host}:{websocket.client.port}"
            if client_id in self.active_connections:
                del self.active_connections[client_id]
                logger.info(f"WebSocket disconnected: {websocket.client}")

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
        logger.debug(f"WebSocketManager: Attempting to send notification: {message}")
        async with self._lock:
            active_sockets = list(self.active_connections.values())
    
        if not active_sockets:
            logger.warning("WebSocketManager: No active WebSocket connections")
            return

        for ws in active_sockets:
            try:
                await ws.send_json(message)
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
