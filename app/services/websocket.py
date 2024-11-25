from typing import Dict, List
from fastapi import WebSocket
from app.models import Streamer, TwitchEvent
from datetime import datetime

class StreamerConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, streamer_username: str):
        await websocket.accept()
        if streamer_username not in self.active_connections:
            self.active_connections[streamer_username] = []
        self.active_connections[streamer_username].append(websocket)

    def disconnect(self, websocket: WebSocket, streamer_username: str):
        if streamer_username in self.active_connections:
            self.active_connections[streamer_username].remove(websocket)
            if not self.active_connections[streamer_username]:
                del self.active_connections[streamer_username]

    async def broadcast_streamer_update(self, streamer: Streamer):
        if streamer.username in self.active_connections:
            message = {
                "type": "streamer_update",
                "data": {
                    "username": streamer.username,
                    "is_live": streamer.is_live,
                    "stream_title": streamer.stream_title,
                    "game_name": streamer.game_name,
                    "last_updated": streamer.last_updated.isoformat()
                }
            }
            await self.broadcast_to_streamer(streamer.username, message)

    async def broadcast_to_streamer(self, streamer_username: str, message: dict):
        if streamer_username in self.active_connections:
            for connection in self.active_connections[streamer_username]:
                try:
                    await connection.send_json(message)
                except:
                    await self.disconnect(connection, streamer_username)

manager = StreamerConnectionManager()
