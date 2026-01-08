from fastapi import WebSocket
from starlette.websockets import WebSocketState
from typing import List, Dict, Any
import logging
from datetime import datetime
import asyncio
from app.utils.client_ip import get_client_info

logger = logging.getLogger("streamvault")


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # Use dict instead of list
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()

        # Get real client information including IP behind reverse proxy
        client_info_data = get_client_info(websocket)
        real_ip = client_info_data["real_ip"]
        proxy_ip = client_info_data["proxy_ip"]
        user_agent = (
            client_info_data["user_agent"][:50] + "..."
            if len(client_info_data["user_agent"]) > 50
            else client_info_data["user_agent"]
        )
        is_proxied = client_info_data["is_reverse_proxied"]

        # Create a unique identifier based on real IP and browser info
        client_identifier = f"{real_ip}_{hash(user_agent) % 10000}"
        connection_id = id(websocket)  # Use object ID as unique identifier

        async with self._lock:
            # Clean up any stale connections first
            await self._cleanup_stale_connections()

            # Check for existing connections from same client
            existing_from_client = sum(
                1
                for ws_id, ws in self.active_connections.items()
                if hasattr(ws, "_client_identifier") and ws._client_identifier == client_identifier
            )

            # Store client identifier in websocket for tracking
            websocket._client_identifier = client_identifier
            websocket._real_ip = real_ip

            self.active_connections[connection_id] = websocket

        connection_count = len(self.active_connections)
        proxy_info = f" (via proxy {proxy_ip})" if is_proxied else ""

        logger.info(
            f"🔌 WebSocket connected: {real_ip}{proxy_info} - Agent: {user_agent} (ID: {connection_id}) - Total: {connection_count} connections"
        )

        if existing_from_client > 0:
            logger.warning(
                f"⚠️ Client {real_ip} now has {existing_from_client + 1} connections (possible multiple tabs/windows)"
            )

        await self.send_notification_to_socket(
            websocket,
            {
                "type": "connection.status",
                "data": {
                    "status": "connected",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": f"StreamVault WebSocket connected - {connection_count} total connections",
                    "connection_id": connection_id,
                    "real_ip": real_ip,
                    "is_reverse_proxied": is_proxied,
                },
            },
        )

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            connection_id = id(websocket)
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
                connection_count = len(self.active_connections)

                # Get client info for better logging
                real_ip = getattr(websocket, "_real_ip", "unknown")
                client_identifier = getattr(websocket, "_client_identifier", "unknown")

                # Count remaining connections from same client
                remaining_from_client = sum(
                    1
                    for ws_id, ws in self.active_connections.items()
                    if hasattr(ws, "_client_identifier") and ws._client_identifier == client_identifier
                )

                logger.info(
                    f"🔌 WebSocket disconnected: {real_ip} (ID: {connection_id}) - Remaining: {connection_count} total, {remaining_from_client} from this client"
                )

    async def _cleanup_stale_connections(self):
        """Remove stale/closed WebSocket connections"""
        stale_connections = []
        for connection_id, ws in self.active_connections.items():
            # Check if the connection is still active
            try:
                # Use the proper enum value instead of string comparison
                if not hasattr(ws, "client_state") or ws.client_state != WebSocketState.CONNECTED:
                    stale_connections.append(connection_id)
            except AttributeError:
                # Connection is likely closed due to missing client_state
                stale_connections.append(connection_id)

        for connection_id in stale_connections:
            del self.active_connections[connection_id]
            logger.debug(f"🧹 Cleaned up stale connection: {connection_id}")

        if stale_connections:
            logger.info(f"🧹 Cleaned up {len(stale_connections)} stale connections")

    async def send_notification_to_socket(self, websocket: WebSocket, message: Dict[str, Any]):
        try:
            # Check if the connection is still active using proper enum comparison
            if hasattr(websocket, "client_state") and websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
                return True
        except Exception as e:
            logger.error(f"Failed to send message to {websocket.client}: {e}")
            await self.disconnect(websocket)
            return False

    async def send_notification(self, message: dict):
        # Only log for non-routine broadcasts or when there's actual data
        should_log = (
            message.get("type") != "active_recordings_update"
            or bool(message.get("data"))
            or len(self.active_connections) <= 2
        )

        if should_log:
            logger.debug(f"WebSocketManager: Attempting to send notification: {message}")

        async with self._lock:
            active_sockets = list(self.active_connections.values())

        if not active_sockets:
            if should_log:
                logger.warning("WebSocketManager: No active WebSocket connections")
            return

        for ws in active_sockets:
            try:
                await ws.send_json(message)
                if should_log:
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
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.send_notification(message)
        # Only log when there are active recordings or few clients
        if active_recordings or len(self.active_connections) <= 2:
            logger.debug(f"WebSocketManager: Sent active recordings update to {len(self.active_connections)} clients")

    async def send_recording_started(self, recording_info: Dict[str, Any]):
        """Send recording started notification"""
        message = {"type": "recording_started", "data": recording_info, "timestamp": datetime.utcnow().isoformat()}
        await self.send_notification(message)
        logger.info(
            f"WebSocketManager: Sent recording started notification for {recording_info.get('streamer_name', 'unknown')}"
        )

    async def send_recording_stopped(self, recording_info: Dict[str, Any]):
        """Send recording stopped notification"""
        message = {"type": "recording_stopped", "data": recording_info, "timestamp": datetime.utcnow().isoformat()}
        await self.send_notification(message)
        logger.info(
            f"WebSocketManager: Sent recording stopped notification for {recording_info.get('streamer_name', 'unknown')}"
        )

    async def send_queue_stats_update(self, stats: Dict[str, Any]):
        """Send background queue stats update"""
        message = {"type": "queue_stats_update", "data": stats, "timestamp": datetime.utcnow().isoformat()}
        await self.send_notification(message)
        logger.debug(f"WebSocketManager: Sent queue stats update: {stats}")

    async def send_task_status_update(self, task_info: Dict[str, Any]):
        """Send task status update"""
        message = {"type": "task_status_update", "data": task_info, "timestamp": datetime.utcnow().isoformat()}
        await self.send_notification(message)
        logger.debug(f"WebSocketManager: Sent task status update for task {task_info.get('id')}")

    async def send_task_progress_update(self, task_id: str, progress: float, message_text: str = None):
        """Send task progress update"""
        message = {
            "type": "task_progress_update",
            "data": {"task_id": task_id, "progress": progress, "message": message_text},
            "timestamp": datetime.utcnow().isoformat(),
        }
        await self.send_notification(message)
        logger.debug(f"WebSocketManager: Sent progress update for task {task_id}: {progress}%")

    async def send_recording_job_update(self, recording_info: Dict[str, Any]):
        """Send recording job update (streamlink/ffmpeg status)"""
        message = {"type": "recording_job_update", "data": recording_info, "timestamp": datetime.utcnow().isoformat()}
        await self.send_notification(message)
        logger.debug(f"WebSocketManager: Sent recording job update for {recording_info.get('streamer_name')}")

    async def send_toast_notification(
        self, toast_type: str, title: str, message: str, duration: int = 5000, extra_data: Dict[str, Any] = None
    ):
        """Send toast notification to all connected clients"""
        notification = {
            "type": "toast_notification",
            "data": {
                "toast_type": toast_type,  # 'success', 'error', 'warning', 'info'
                "title": title,
                "message": message,
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat(),
                **(extra_data or {}),
            },
        }
        await self.send_notification(notification)
        logger.info(f"WebSocketManager: Sent {toast_type} toast: {title} - {message}")

    async def send_force_recording_feedback(
        self, success: bool, streamer_name: str, message: str, extra_data: Dict[str, Any] = None
    ):
        """Send force recording feedback as toast notification"""
        toast_type = "success" if success else "error"
        title = f"Force Recording - {streamer_name}"

        await self.send_toast_notification(
            toast_type=toast_type,
            title=title,
            message=message,
            duration=6000,  # Longer duration for recording feedback
            extra_data={
                "action": "force_recording",
                "streamer_name": streamer_name,
                "success": success,
                **(extra_data or {}),
            },
        )

    async def send_live_status_feedback(self, streamer_name: str, is_live: bool, extra_data: Dict[str, Any] = None):
        """Send live status check feedback as toast notification"""
        title = f"Live Status - {streamer_name}"
        if is_live:
            message = "Streamer is currently live on Twitch"
            toast_type = "success"
        else:
            message = "Streamer is not currently live on Twitch"
            toast_type = "warning"

        await self.send_toast_notification(
            toast_type=toast_type,
            title=title,
            message=message,
            duration=4000,
            extra_data={
                "action": "live_status_check",
                "streamer_name": streamer_name,
                "is_live": is_live,
                **(extra_data or {}),
            },
        )


# Global instance for backward compatibility
websocket_manager = ConnectionManager()
