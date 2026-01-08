"""
RecordingWebSocketService - Real-time WebSocket communications

Extracted from recording_service.py ULTRA-BOSS (1084 lines)
Handles all WebSocket communications for recording status updates and real-time notifications.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("streamvault")


class RecordingWebSocketService:
    """Handles WebSocket communications for recording events"""

    def __init__(self, websocket_manager=None):
        self.websocket_manager = websocket_manager

    async def send_active_recordings_update(self, active_recordings: Dict[int, Dict[str, Any]]) -> None:
        """Send active recordings update via WebSocket"""
        if not self.websocket_manager:
            logger.debug("WebSocket manager not available, skipping active recordings update")
            return

        try:
            # Convert active recordings to WebSocket format
            websocket_data = []
            for recording_id, recording_data in active_recordings.items():
                websocket_data.append({
                    'id': recording_id,
                    'streamer_id': recording_data.get('streamer_id'),
                    'stream_id': recording_data.get('stream_id'),
                    'file_path': recording_data.get('file_path'),
                    'status': recording_data.get('status', 'recording'),
                    'started_at': recording_data.get('started_at'),
                    'progress': recording_data.get('progress', 0.0)
                })

            message = {
                "type": "active_recordings_update",
                "data": websocket_data
            }

            await self.websocket_manager.send_notification(message)
            logger.debug(f"Sent active recordings update: {len(websocket_data)} recordings")

        except Exception as e:
            logger.error(f"Failed to send active recordings WebSocket update: {e}")

    async def send_recording_status_update(
        self,
        recording_id: int,
        status: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send recording status update via WebSocket"""
        if not self.websocket_manager:
            logger.debug("WebSocket manager not available, skipping recording status update")
            return

        try:
            message = {
                "type": "recording_status_update",
                "data": {
                    "recording_id": recording_id,
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(additional_data or {})
                }
            }

            await self.websocket_manager.send_notification(message)
            logger.debug(f"Sent recording status update: {recording_id} -> {status}")

        except Exception as e:
            logger.error(f"Failed to send recording status WebSocket update: {e}")

    async def send_recording_job_update(
        self,
        recording_id: int,
        job_type: str,
        status: str,
        progress: float = 0.0,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send recording job status update via WebSocket"""
        if not self.websocket_manager:
            logger.debug("WebSocket manager not available, skipping recording job update")
            return

        try:
            message = {
                "type": "recording_job_update",
                "data": {
                    "recording_id": recording_id,
                    "job_type": job_type,
                    "status": status,
                    "progress": progress,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(additional_data or {})
                }
            }

            await self.websocket_manager.send_notification(message)
            logger.debug(f"Sent recording job update: {recording_id} {job_type} -> {status} ({progress:.1f}%)")

        except Exception as e:
            logger.error(f"Failed to send recording job WebSocket update: {e}")

    async def send_background_task_update(
        self,
        task_id: str,
        task_type: str,
        status: str,
        progress: float = 0.0,
        recording_id: Optional[int] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send background task update via WebSocket"""
        if not self.websocket_manager:
            logger.debug("WebSocket manager not available, skipping background task update")
            return

        try:
            message = {
                "type": "background_task_update",
                "data": {
                    "task_id": task_id,
                    "task_type": task_type,
                    "status": status,
                    "progress": progress,
                    "recording_id": recording_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(additional_data or {})
                }
            }

            await self.websocket_manager.send_notification(message)
            logger.debug(f"Sent background task update: {task_id} {task_type} -> {status} ({progress:.1f}%)")

        except Exception as e:
            logger.error(f"Failed to send background task WebSocket update: {e}")

    async def send_recording_error(
        self,
        recording_id: int,
        error_message: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send recording error notification via WebSocket"""
        if not self.websocket_manager:
            logger.debug("WebSocket manager not available, skipping recording error notification")
            return

        try:
            message = {
                "type": "recording_error",
                "data": {
                    "recording_id": recording_id,
                    "error_message": error_message,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(additional_data or {})
                }
            }

            await self.websocket_manager.send_notification(message)
            logger.debug(f"Sent recording error notification: {recording_id}")

        except Exception as e:
            logger.error(f"Failed to send recording error WebSocket notification: {e}")

    async def send_recording_completed(
        self,
        recording_id: int,
        file_path: str,
        duration_seconds: Optional[int] = None,
        file_size: Optional[int] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send recording completed notification via WebSocket"""
        if not self.websocket_manager:
            logger.debug("WebSocket manager not available, skipping recording completed notification")
            return

        try:
            message = {
                "type": "recording_completed",
                "data": {
                    "recording_id": recording_id,
                    "file_path": file_path,
                    "duration_seconds": duration_seconds,
                    "file_size": file_size,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(additional_data or {})
                }
            }

            await self.websocket_manager.send_notification(message)
            logger.debug(f"Sent recording completed notification: {recording_id}")

        except Exception as e:
            logger.error(f"Failed to send recording completed WebSocket notification: {e}")

    async def send_recording_started(
        self,
        recording_id: int,
        streamer_id: int,
        stream_id: int,
        file_path: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send recording started notification via WebSocket"""
        if not self.websocket_manager:
            logger.debug("WebSocket manager not available, skipping recording started notification")
            return

        try:
            message = {
                "type": "recording_started",
                "data": {
                    "recording_id": recording_id,
                    "streamer_id": streamer_id,
                    "stream_id": stream_id,
                    "file_path": file_path,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(additional_data or {})
                }
            }

            await self.websocket_manager.send_notification(message)
            logger.debug(f"Sent recording started notification: {recording_id}")

        except Exception as e:
            logger.error(f"Failed to send recording started WebSocket notification: {e}")

    async def send_system_notification(
        self,
        notification_type: str,
        message: str,
        level: str = "info",
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send system notification via WebSocket"""
        if not self.websocket_manager:
            logger.debug("WebSocket manager not available, skipping system notification")
            return

        try:
            notification = {
                "type": "system_notification",
                "data": {
                    "notification_type": notification_type,
                    "message": message,
                    "level": level,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(additional_data or {})
                }
            }

            await self.websocket_manager.send_notification(notification)
            logger.debug(f"Sent system notification: {notification_type} - {message}")

        except Exception as e:
            logger.error(f"Failed to send system WebSocket notification: {e}")

    async def send_recording_progress_update(
        self,
        recording_id: int,
        progress: float,
        stage: str = "recording",
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send recording progress update via WebSocket"""
        if not self.websocket_manager:
            return

        try:
            message = {
                "type": "recording_progress",
                "data": {
                    "recording_id": recording_id,
                    "progress": progress,
                    "stage": stage,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(additional_data or {})
                }
            }

            await self.websocket_manager.send_notification(message)

        except Exception as e:
            logger.error(f"Failed to send recording progress WebSocket update: {e}")

    async def send_bulk_status_update(self, updates: List[Dict[str, Any]]) -> None:
        """Send multiple status updates in a single WebSocket message"""
        if not self.websocket_manager or not updates:
            return

        try:
            message = {
                "type": "bulk_recording_update",
                "data": {
                    "updates": updates,
                    "timestamp": datetime.utcnow().isoformat(),
                    "count": len(updates)
                }
            }

            await self.websocket_manager.send_notification(message)
            logger.debug(f"Sent bulk status update: {len(updates)} updates")

        except Exception as e:
            logger.error(f"Failed to send bulk WebSocket update: {e}")

    def is_websocket_available(self) -> bool:
        """Check if WebSocket manager is available"""
        return self.websocket_manager is not None

    def set_websocket_manager(self, websocket_manager) -> None:
        """Set or update the WebSocket manager"""
        self.websocket_manager = websocket_manager
        logger.debug("WebSocket manager updated")
