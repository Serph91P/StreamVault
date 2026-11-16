"""Compatibility aliases for callers of the former monolithic model module.

Definitions live in feature modules and share the existing Base registry.
"""

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

__all__ = [
    "ActiveRecordingState",
    "ApiKey",
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
