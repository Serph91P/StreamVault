"""
Custom exception classes for the recording service.
"""

# Base exception for recording-related errors


class RecordingError(Exception):
    """Base exception for recording-related errors"""


class StreamerNotFoundError(RecordingError):
    """Raised when a streamer is not found"""


class StreamNotFoundError(RecordingError):
    """Raised when a stream is not found"""


class ProcessError(RecordingError):
    """Raised when there's an issue with a recording process"""


class ConfigurationError(RecordingError):
    """Raised when there's an issue with configuration"""


class StreamUnavailableError(RecordingError):
    """Raised when a stream is unavailable"""


class FileOperationError(RecordingError):
    """Raised when there's an issue with file operations"""


class RecordingAlreadyActiveError(RecordingError):
    """Raised when attempting to start a recording that's already active"""


class StreamlinkError(RecordingError):
    """Raised when streamlink process fails"""


class FFmpegError(RecordingError):
    """Raised when FFmpeg process fails"""
