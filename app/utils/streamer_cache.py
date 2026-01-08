"""
Cached streamer directory validation utility
"""

import time
import threading
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger("streamvault")

# Global cache for valid streamers
_streamer_cache: Dict[str, Any] = {"valid_streamers": [], "last_updated": 0.0, "cache_duration": 300}  # 5 minutes

# Thread lock for cache operations
_cache_lock = threading.Lock()


def get_valid_streamers(base_recordings_dir: Path, force_refresh: bool = False) -> List[str]:
    """
    Get valid streamer directories with caching to avoid filesystem scans on every request.

    Args:
        base_recordings_dir: Base directory containing streamer subdirectories
        force_refresh: Force cache refresh regardless of expiration

    Returns:
        List of valid streamer directory names
    """
    current_time = time.time()

    with _cache_lock:
        # Check if cache needs refresh
        cache_expired = (current_time - _streamer_cache["last_updated"]) > _streamer_cache["cache_duration"]

        if force_refresh or cache_expired or not _streamer_cache["valid_streamers"]:
            logger.debug(f"Refreshing streamer cache. Force: {force_refresh}, Expired: {cache_expired}")

            # Refresh cache by scanning filesystem
            valid_streamers = []
            if base_recordings_dir.exists():
                try:
                    for item in base_recordings_dir.iterdir():
                        if item.is_dir():
                            valid_streamers.append(item.name)

                    _streamer_cache["valid_streamers"] = valid_streamers
                    _streamer_cache["last_updated"] = current_time

                    logger.debug(f"Updated streamer cache with {len(valid_streamers)} streamers")

                except Exception as e:
                    logger.error(f"Error scanning streamer directories: {e}")
                    # Return cached data if available, otherwise empty list
                    return _streamer_cache["valid_streamers"]
            else:
                logger.warning(f"Base recordings directory does not exist: {base_recordings_dir}")
                _streamer_cache["valid_streamers"] = []
                _streamer_cache["last_updated"] = current_time

        return _streamer_cache["valid_streamers"].copy()


def invalidate_streamer_cache():
    """
    Invalidate the streamer cache, forcing a refresh on next access.
    Useful when streamer directories are added/removed.
    """
    with _cache_lock:
        _streamer_cache["last_updated"] = 0.0
        logger.debug("Streamer cache invalidated")


def get_cache_info() -> Dict[str, Any]:
    """
    Get current cache information for debugging.

    Returns:
        Dictionary with cache status information
    """
    with _cache_lock:
        current_time = time.time()
        age = current_time - _streamer_cache["last_updated"]

        return {
            "streamer_count": len(_streamer_cache["valid_streamers"]),
            "last_updated": _streamer_cache["last_updated"],
            "cache_age_seconds": age,
            "cache_duration": _streamer_cache["cache_duration"],
            "is_expired": age > _streamer_cache["cache_duration"],
            "streamers": _streamer_cache["valid_streamers"].copy(),
        }
