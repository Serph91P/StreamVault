from fastapi import WebSocket
from typing import List
from starlette.websockets import WebSocketState

# WebSocket manager for real-time notifications
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"WebSocket disconnected: {websocket.client}")

    async def send_notification(self, message: str):
        for connection in self.active_connections:
            if connection.application_state == WebSocketState.CONNECTED:
                await connection.send_text(message)
            else:
                self.disconnect(connection)

manager = ConnectionManager()
