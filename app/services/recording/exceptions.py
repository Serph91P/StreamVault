"""
Custom exception classes for the recording service.
"""

# Base exception for recording-related errors
class RecordingError(Exception):
    """Base exception for recording-related errors"""
    pass


class StreamerNotFoundError(RecordingError):
    """Raised when a streamer is not found"""
    pass


class StreamNotFoundError(RecordingError):
    """Raised when a stream is not found"""
    pass


class RecordingAlreadyActiveError(RecordingError):
    """Raised when attempting to start a recording that's already active"""
    pass


class StreamlinkError(RecordingError):
    """Raised when streamlink process fails"""
    pass


class FFmpegError(RecordingError):
    """Raised when FFmpeg process fails"""
    pass
