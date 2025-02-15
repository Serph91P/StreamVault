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
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
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
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
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

    async def send_notification(self, message: Dict[str, Any]):
        logger.debug(f"WebSocket notification: {message}")
        async with self._lock:
            active_sockets = self.active_connections.copy()
    
        logger.debug(f"Active WebSocket connections: {len(active_sockets)}")
    
        for ws in active_sockets:
            try:
                success = await self.send_notification_to_socket(ws, message)
                logger.debug(f"Notification sent to {ws.client}: {success}")
            except Exception as e:
                logger.error(f"Failed to send to {ws.client}: {e}")
