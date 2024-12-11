from fastapi import WebSocket
from typing import List
from starlette.websockets import WebSocketState
import logging

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

    async def send_notification(self, message: str):
        for connection in self.active_connections:
            if connection.client_state != WebSocketState.DISCONNECTED:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    self.disconnect(connection)
                    logger.error(f"Failed to send message to {connection.client}: {e}")
