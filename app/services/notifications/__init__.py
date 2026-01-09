"""
Notification Services Package

Split from the original notification_service.py God Class:
- NotificationDispatcher: Main coordination service
- ExternalNotificationService: Apprise-based notifications
- PushNotificationService: Browser push notifications
- NotificationFormatter: Message formatting utilities
"""

from .notification_dispatcher import NotificationDispatcher
from .external_notification_service import ExternalNotificationService
from .push_notification_service import PushNotificationService
from .notification_formatter import NotificationFormatter

__all__ = ["NotificationDispatcher", "ExternalNotificationService", "PushNotificationService", "NotificationFormatter"]
