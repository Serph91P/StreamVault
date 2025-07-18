"""
Simple in-memory cache for frequently accessed data
"""
import time
from typing import Any, Optional, Dict
from threading import Lock

class SimpleCache:
    """Thread-safe in-memory cache with TTL support"""
    
    def __init__(self):
        self._cache: Dict[str, tuple] = {}  # key -> (value, expire_time)
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired"""
        with self._lock:
            if key in self._cache:
                value, expire_time = self._cache[key]
                if time.time() < expire_time:
                    return value
                else:
                    # Remove expired entry
                    del self._cache[key]
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set cached value with TTL (time to live) in seconds"""
        with self._lock:
            expire_time = time.time() + ttl
            self._cache[key] = (value, expire_time)
    
    def delete(self, key: str) -> None:
        """Delete cached value"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cached values"""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed entries"""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, expire_time) in self._cache.items()
                if current_time >= expire_time
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            return len(expired_keys)

# Global cache instance
app_cache = SimpleCache()
