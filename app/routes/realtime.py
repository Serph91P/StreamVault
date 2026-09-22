from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
import logging

from app.dependencies import websocket_manager, get_current_user

logger = logging.getLogger("streamvault")

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from app.utils.client_ip import get_real_client_ip

    real_ip = get_real_client_ip(websocket)
    logger.info(f"📞 New WebSocket connection attempt from {real_ip}")

    if not await websocket_manager.connect(websocket):
        return
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"📞 WebSocket disconnected: {real_ip}")
        await websocket_manager.disconnect(websocket)


@router.get("/api/realtime/events")
async def replay_realtime_events(
    since: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=500),
    current_user=Depends(get_current_user),
):
    """Return recent authenticated realtime events after a client cursor.

    Retention is bounded in memory by the WebSocket manager. Clients should
    pass the highest event_id they have already processed as since to avoid
    duplicate replay of live events received before reconnect.
    """
    replay_window = await websocket_manager.get_replay_window(since=since, limit=limit)

    return {
        "since": since,
        **replay_window,
    }
