from fastapi import WebSocket
from typing import List, Dict, Any
from starlette.websockets import WebSocketState
import logging
import json

logger = logging.getLogger('streamvault')

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected: {websocket.client}")
        
        # Send initial status message
        await websocket.send_json({
            "type": "connection.status",
            "data": {
                "status": "connected",
                "message": "WebSocket connection established"
            }
        })

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected: {websocket.client}")

    async def send_notification(self, message: str | Dict[str, Any]):
        disconnected = []

        if isinstance(message, dict):
            message = json.dumps(message)

        for connection in self.active_connections:
            logger.debug(f"Sending message to connection: {connection}")
            if connection.application_state == WebSocketState.CONNECTED:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to send message to {connection.client}: {e}")
                    disconnected.append(connection)
            else:
                disconnected.append(connection)

        for conn in disconnected:
            logger.warning(f"Cleaning up disconnected connection: {conn}")
            self.disconnect(conn)

    async def broadcast(self, message: str):
        await self.send_notification(message)
