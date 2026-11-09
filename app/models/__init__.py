"""Stable model imports over feature-local SQLAlchemy mappings.

All features share the historical Base registry. Existing imports and table
identities are preserved; defining models does not open resources.
"""

from app.models.categories import Category, FavoriteCategory
from app.models.identity import ApiKey, RefreshToken, Session, User
from app.models.notifications import (
    NotificationSettings,
    NotificationState,
    PushSubscription,
)
from app.models.proxies import ProxySettings
from app.models.recordings import (
    ActiveRecordingState,
    Recording,
    RecordingProcessingState,
    RecordingSettings,
    StreamerRecordingSettings,
)
from app.models.streams import Stream, StreamEvent, StreamMetadata, Streamer
from app.models.system import GlobalSettings, SystemConfig, SystemState
from app.models.upstream import TwitchUpstreamCoordinationState, TwitchUpstreamLease
from app.models.video_catalog import VideoCatalogEntry
from app.models.background_task import BackgroundTask, BackgroundTaskDependency

__all__ = [
    "ActiveRecordingState",
    "ApiKey",
    "BackgroundTask",
    "BackgroundTaskDependency",
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
    "VideoCatalogEntry",
]
