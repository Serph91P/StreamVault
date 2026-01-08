"""
Media Services Package

Contains media processing and metadata services.
"""

# Lazy imports to avoid directory creation at import time
# These are imported when the package is first accessed

__all__ = ["artwork_service", "thumbnail_service", "metadata_service"]


def __getattr__(name):
    """Lazy import of services to avoid side effects at import time"""
    if name == "artwork_service":
        from .artwork_service import artwork_service

        return artwork_service
    elif name == "thumbnail_service":
        from .thumbnail_service import thumbnail_service

        return thumbnail_service
    elif name == "metadata_service":
        from .metadata_service import metadata_service

        return metadata_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
