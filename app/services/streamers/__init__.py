"""
Streamer Services Package

Split from the original streamer_service.py God Class (347 lines):
- StreamerRepository: Database operations for streamers, streams, settings
- TwitchIntegrationService: Twitch API calls and EventSub management
- StreamerImageService: Profile image downloading and caching
"""

__all__ = ["StreamerRepository", "TwitchIntegrationService", "StreamerImageService"]


def __getattr__(name):
    """Lazy import of streamer services to avoid side effects at import time"""
    if name == "StreamerRepository":
        from .streamer_repository import StreamerRepository

        return StreamerRepository
    elif name == "TwitchIntegrationService":
        from .twitch_integration_service import TwitchIntegrationService

        return TwitchIntegrationService
    elif name == "StreamerImageService":
        from .streamer_image_service import StreamerImageService

        return StreamerImageService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
