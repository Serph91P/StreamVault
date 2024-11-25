from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.services.websocket import manager
from app.models import Streamer
from app.auth import current_user

router = APIRouter()

@router.websocket("/ws/{streamer_username}")
async def websocket_endpoint(websocket: WebSocket, streamer_username: str):
    streamer = Streamer.query.filter_by(username=streamer_username).first()
    if not streamer:
        await websocket.close(code=4004)
        return
        
    await manager.connect(websocket, streamer_username)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle any incoming messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket, streamer_username)
