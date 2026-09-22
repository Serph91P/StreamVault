"""Stable model import surface.

Feature modules are introduced incrementally. Existing callers continue to use
``from app.models import ...`` while extracted models also gain a focused module
path. Importing this package registers the complete historical SQLAlchemy
metadata exactly once.
"""

from app.models._legacy import (
    ActiveRecordingState,
    ApiKey,
    GlobalSettings,
    NotificationSettings,
    NotificationState,
    ProxySettings,
    PushSubscription,
    Recording,
    RecordingProcessingState,
    RecordingSettings,
    RefreshToken,
    Session,
    Stream,
    StreamEvent,
    StreamMetadata,
    Streamer,
    StreamerRecordingSettings,
    SystemConfig,
    SystemState,
    TwitchUpstreamCoordinationState,
    TwitchUpstreamLease,
    User,
)
from app.models.categories import Category, FavoriteCategory

__all__ = [
    "ActiveRecordingState",
    "ApiKey",
    "Category",
    "FavoriteCategory",
    "GlobalSettings",
    "NotificationSettings",
    "NotificationState",
    "ProxySettings",
    "PushSubscription",
    "Recording",
    "RecordingProcessingState",
    "RecordingSettings",
    "RefreshToken",
    "Session",
    "Stream",
    "StreamEvent",
    "StreamMetadata",
    "Streamer",
    "StreamerRecordingSettings",
    "SystemConfig",
    "SystemState",
    "TwitchUpstreamCoordinationState",
    "TwitchUpstreamLease",
    "User",
]
