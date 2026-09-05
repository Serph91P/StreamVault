from fastapi import APIRouter, Depends
import logging

from app.dependencies import websocket_manager, get_current_user

logger = logging.getLogger("streamvault")

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "StreamVault"}


@router.get("/admin/websocket-connections")
async def get_websocket_connections(current_user=Depends(get_current_user)):
    """Admin endpoint to monitor WebSocket connections"""
    connections = []
    async with websocket_manager._lock:
        for connection_id, ws in websocket_manager.active_connections.items():
            real_ip = getattr(ws, "_real_ip", "unknown")
            client_identifier = getattr(ws, "_client_identifier", "unknown")

            connections.append(
                {
                    "connection_id": connection_id,
                    "real_ip": real_ip,
                    "client_identifier": client_identifier,
                    "state": (
                        ws.application_state.value
                        if hasattr(ws.application_state, "value")
                        else str(ws.application_state)
                    ),
                }
            )

    # Group by real IP to show multiple connections per client
    clients = {}
    for conn in connections:
        ip = conn["real_ip"]
        if ip not in clients:
            clients[ip] = {"ip": ip, "connections": [], "count": 0}
        clients[ip]["connections"].append(conn)
        clients[ip]["count"] += 1

    return {
        "total_connections": len(connections),
        "unique_clients": len(clients),
        "clients": list(clients.values()),
        "connections": connections,
    }
