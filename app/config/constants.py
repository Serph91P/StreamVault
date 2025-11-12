"""
Centralized Configuration Constants

This module contains all magic numbers, timeouts, thresholds, and other
hardcoded values that were previously scattered throughout the codebase.

Benefits:
- Single source of truth for configuration values
- Easy to tune performance without hunting through code
- Clear documentation of what each value controls
- Type safety and IDE autocomplete support
"""

from dataclasses import dataclass


# ============================================================================
# ASYNC OPERATION DELAYS (in seconds)
# ============================================================================

@dataclass(frozen=True)
class AsyncDelays:
    """Delays for asynchronous operations"""
    
    # Generic operation delays
    BRIEF_PAUSE: float = 1.0           # Brief pause between operations
    SHORT_RETRY_DELAY: float = 2.0     # Short wait before retrying
    NORMAL_RETRY_DELAY: float = 5.0    # Normal wait before retrying
    LONG_RETRY_DELAY: float = 10.0     # Long wait before retrying
    ERROR_RECOVERY_DELAY: float = 5.0  # Wait time after error before recovery
    
    # Specific operation delays
    QUEUE_WORKER_START_DELAY: float = 5.0        # Wait for queue workers to start
    RECORDING_MONITOR_INTERVAL: float = 10.0     # Recording status check interval
    QUEUE_TASK_POLL_INTERVAL: float = 1.0        # Task queue polling interval
    QUEUE_EMPTY_WAIT: float = 10.0               # Wait when queue is empty
    QUEUE_ERROR_WAIT: float = 5.0                # Wait after queue error
    IMAGE_SYNC_INTERVAL: float = 30.0            # Image sync check interval
    SESSION_CLEANUP_ERROR_WAIT: float = 300.0    # Wait on session cleanup error (5 min)
    WEBSOCKET_BROADCAST_ERROR_SHORT: float = 5.0 # Short wait on WS error
    WEBSOCKET_BROADCAST_ERROR_LONG: float = 10.0 # Long wait on WS error
    HANDLER_REGISTRY_RETRY: float = 1.0          # Handler registry retry delay
    WORKER_SHUTDOWN_PAUSE: float = 1.0           # Pause during worker shutdown
    IMAGE_SYNC_RETRY: float = 1.0                # Image sync retry delay
    AUTO_RECOVERY_ERROR_WAIT: float = 10.0       # Auto recovery error wait


# ============================================================================
# RETRY CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class RetryConfig:
    """Retry attempts and strategies"""
    
    # Default retry counts
    DEFAULT_MAX_RETRIES: int = 3          # Default retry attempts
    REDUCED_RETRIES: int = 1              # Reduced retries for repair operations
    LOW_RETRIES: int = 2                  # Low retry count for quick operations
    
    # Specific operation retry counts
    MIGRATION_MAX_RETRIES: int = 5        # Database migration retries
    API_CALL_MAX_RETRIES: int = 3         # API call retries
    HANDLER_VERIFICATION_ATTEMPTS: int = 10  # Event handler verification attempts
    
    # Retry delays
    MIGRATION_RETRY_DELAY: float = 2.0    # Delay between migration retries
    API_RETRY_DELAY: float = 0.1          # Delay between API retries


# ============================================================================
# TIMEOUT CONFIGURATION (in seconds)
# ============================================================================

@dataclass(frozen=True)
class Timeouts:
    """Timeout values for various operations"""
    
    # Process timeouts
    GRACEFUL_SHUTDOWN: int = 30           # Graceful shutdown timeout
    SEGMENT_CONCAT_START: int = 30        # Segment concatenation start timeout
    SEGMENT_CONCAT_COMPLETE: int = 600    # Segment concatenation complete timeout (10 min)
    RECORDING_REMUX_SMALL: int = 300      # Small file remux timeout (5 min)
    RECORDING_REMUX_LARGE: int = 600      # Large file remux timeout (10 min)
    RECOVERY_OPERATION: int = 3600        # Recovery operation timeout (1 hour)
    
    # Queue timeouts
    QUEUE_GET_TIMEOUT: float = 1.0        # Queue get operation timeout
    
    # API/Network timeouts
    EVENT_HANDLER_TIMEOUT: float = 5.0    # Event handler execution timeout
    IMAGE_SYNC_QUEUE_TIMEOUT: float = 5.0 # Image sync queue timeout
    
    # Subprocess timeouts
    FFMPEG_VERSION_CHECK: int = 5         # FFmpeg version check timeout
    STREAMLINK_VERSION_CHECK: int = 5     # Streamlink version check timeout
    QUICK_SUBPROCESS: int = 10            # Quick subprocess operations
    NORMAL_SUBPROCESS: int = 15           # Normal subprocess operations
    SLOW_SUBPROCESS: int = 20             # Slow subprocess operations
    VERY_SLOW_SUBPROCESS: int = 30        # Very slow subprocess operations


# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class CacheConfig:
    """Cache sizes and TTL values"""
    
    # Cache sizes
    DEFAULT_CACHE_SIZE: int = 1000        # Default cache max size
    SMALL_CACHE_SIZE: int = 500           # Small cache max size
    
    # TTL values (in seconds)
    EVENT_DEDUPLICATION_TTL: int = 60     # Event deduplication TTL (1 minute)
    NOTIFICATION_DEBOUNCE_TTL: int = 300  # Notification debounce TTL (5 minutes)
    BROADCAST_DEBOUNCE_TTL: int = 60      # WebSocket broadcast debounce TTL (1 minute)
    IMAGE_CACHE_TTL: int = 3600           # Image cache TTL (1 hour)
    CONFIG_CACHE_TTL: int = 300           # Configuration cache TTL (5 minutes)
    SHORT_CACHE_TTL: int = 2              # Short-lived cache TTL
    FALLBACK_CACHE_TTL: int = 300         # Fallback cache TTL (5 minutes)


# ============================================================================
# FILE SIZE THRESHOLDS
# ============================================================================

@dataclass(frozen=True)
class FileSizeThresholds:
    """File size thresholds in bytes"""
    
    # Byte conversion constants
    KB: int = 1024
    MB: int = 1024 * 1024
    GB: int = 1024 * 1024 * 1024
    
    # Size thresholds
    TEST_FILE_SIZE: int = 2 * MB          # Test file size (2 MB)


# ============================================================================
# METADATA CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class MetadataConfig:
    """Metadata extraction and parsing configuration"""
    
    ATOM_NESTING_DEPTH_LIMIT: int = 6    # Maximum atom nesting depth for metadata
    EXTENDED_ATOM_DEPTH_LIMIT: int = 8   # Extended atom nesting depth


# ============================================================================
# CODEC CONFIGURATION (Streamlink 8.0.0+)
# ============================================================================

@dataclass(frozen=True)
class CodecConfig:
    """Video codec preferences for H.265/AV1 support
    
    Requires Streamlink 8.0.0+ with --twitch-supported-codecs support.
    Higher quality streams (1440p60) require modern codecs (h265/av1).
    """
    
    # Default codec preference (RECOMMENDED: best quality/compatibility balance)
    DEFAULT_CODECS: str = "h264,h265"
    
    # Available codec options with descriptions
    CODEC_OPTIONS: dict = {
        "h264": {
            "label": "H.264 Only",
            "description": "Maximum 1080p60, highest compatibility",
            "max_resolution": "1080p60",
            "compatibility": "high",
            "requires_modern_hardware": False
        },
        "h265": {
            "label": "H.265/HEVC Only", 
            "description": "Up to 1440p60, modern hardware required",
            "max_resolution": "1440p60",
            "compatibility": "medium",
            "requires_modern_hardware": True
        },
        "av1": {
            "label": "AV1 Only",
            "description": "Experimental, newest hardware required, very rare",
            "max_resolution": "1440p60",
            "compatibility": "low",
            "requires_modern_hardware": True
        },
        "h264,h265": {
            "label": "H.264 + H.265 (RECOMMENDED)",
            "description": "Best quality/compatibility balance, auto-fallback",
            "max_resolution": "1440p60",
            "compatibility": "high",
            "requires_modern_hardware": False  # H.264 fallback for older hardware
        },
        "h264,h265,av1": {
            "label": "All Codecs (Future-proof)",
            "description": "Maximum quality, requires AV1 decode support",
            "max_resolution": "1440p60",
            "compatibility": "medium",
            "requires_modern_hardware": True
        }
    }


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

# Create singleton instances for easy import
ASYNC_DELAYS = AsyncDelays()
RETRY_CONFIG = RetryConfig()
TIMEOUTS = Timeouts()
CACHE_CONFIG = CacheConfig()
FILE_SIZE_THRESHOLDS = FileSizeThresholds()
METADATA_CONFIG = MetadataConfig()
CODEC_CONFIG = CodecConfig()
