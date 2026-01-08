"""
Notification tracking API endpoints
Handles persistent notification read state and clearing
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

from app.database import get_db
from app.models import NotificationState

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationMarkReadRequest(BaseModel):
    """Request to mark notifications as read"""

    timestamp: Optional[str] = None  # ISO timestamp - all notifications before this are marked read


class NotificationClearRequest(BaseModel):
    """Request to clear all notifications"""


@router.post("/mark-read")
async def mark_notifications_read(request: NotificationMarkReadRequest, db: Session = Depends(get_db)):
    """
    Mark all notifications as read up to a specific timestamp.
    Stores the last read timestamp in the database.
    """
    try:
        # Get current user (from session - assuming authentication is set up)
        # For now, use a default user ID (1) since we don't have multi-user yet
        user_id = 1

        # Parse timestamp
        if request.timestamp:
            try:
                read_timestamp = datetime.fromisoformat(request.timestamp.replace("Z", "+00:00"))
            except ValueError:
                read_timestamp = datetime.now(timezone.utc)
        else:
            read_timestamp = datetime.now(timezone.utc)

        # Find or create notification state
        notification_state = db.query(NotificationState).filter(NotificationState.user_id == user_id).first()

        if not notification_state:
            notification_state = NotificationState(user_id=user_id, last_read_timestamp=read_timestamp)
            db.add(notification_state)
        else:
            notification_state.last_read_timestamp = read_timestamp

        db.commit()

        logger.info(f"Marked notifications as read for user {user_id} up to {read_timestamp}")

        return {"success": True, "last_read_timestamp": read_timestamp.isoformat()}

    except Exception as e:
        logger.error(f"Error marking notifications as read: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to mark notifications as read: {str(e)}")


@router.post("/clear")
async def clear_notifications(request: NotificationClearRequest, db: Session = Depends(get_db)):
    """
    Clear all notifications for the current user.
    Sets the last read timestamp to now and marks all as cleared.
    """
    try:
        user_id = 1  # Default user ID

        # Find or create notification state
        notification_state = db.query(NotificationState).filter(NotificationState.user_id == user_id).first()

        now = datetime.now(timezone.utc)

        if not notification_state:
            notification_state = NotificationState(user_id=user_id, last_read_timestamp=now, last_cleared_timestamp=now)
            db.add(notification_state)
        else:
            notification_state.last_read_timestamp = now
            notification_state.last_cleared_timestamp = now

        db.commit()

        logger.info(f"Cleared all notifications for user {user_id}")

        return {"success": True, "last_cleared_timestamp": now.isoformat()}

    except Exception as e:
        logger.error(f"Error clearing notifications: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear notifications: {str(e)}")


@router.get("/state")
async def get_notification_state(db: Session = Depends(get_db)):
    """
    Get the current notification state (last read/cleared timestamps).
    Used by frontend to filter out already-read notifications.
    """
    try:
        user_id = 1  # Default user ID

        notification_state = db.query(NotificationState).filter(NotificationState.user_id == user_id).first()

        if not notification_state:
            # No state yet - return default (never read/cleared)
            return {"last_read_timestamp": None, "last_cleared_timestamp": None, "unread_count": 0}

        return {
            "last_read_timestamp": (
                notification_state.last_read_timestamp.isoformat() if notification_state.last_read_timestamp else None
            ),
            "last_cleared_timestamp": (
                notification_state.last_cleared_timestamp.isoformat()
                if notification_state.last_cleared_timestamp
                else None
            ),
            "unread_count": 0,  # TODO: Calculate from stored notifications if we store them
        }

    except Exception as e:
        logger.error(f"Error getting notification state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get notification state: {str(e)}")
