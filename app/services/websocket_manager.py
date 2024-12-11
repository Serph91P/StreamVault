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

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected: {websocket.client}")

    async def send_notification(self, message: str | Dict[str, Any]):
        disconnected = []
        
        if isinstance(message, dict):
            message = json.dumps(message)

        for connection in self.active_connections:
            if connection.client_state != WebSocketState.DISCONNECTED:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to send message to {connection.client}: {e}")
                    disconnected.append(connection)
            else:
                disconnected.append(connection)

        # Clean up disconnected connections
        for conn in disconnected:
            if conn in self.active_connections:
                self.disconnect(conn)

    async def broadcast(self, message: str):
        await self.send_notification(message)
