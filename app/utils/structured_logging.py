"""
Structured logging utilities for StreamVault

Provides helper functions for creating structured log entries
with contextual information.
"""
import logging
from typing import Any, Optional


def get_structured_logger(name: str = "streamvault") -> logging.Logger:
    """Get a logger configured for structured logging"""
    return logging.getLogger(name)


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    **context: Any
) -> None:
    """Log a message with additional context fields

    Args:
        logger: Logger instance
        level: Log level (debug, info, warning, error)
        message: Log message
        **context: Additional context fields
    """
    # Create a new LogRecord with extra context
    record = logging.LogRecord(
        name=logger.name,
        level=getattr(logging, level.upper()),
        pathname="",
        lineno=0,
        msg=message,
        args=(),
        exc_info=None
    )

    # Add context fields to the record
    for key, value in context.items():
        setattr(record, key, value)

    # Log the record
    logger.handle(record)


def log_recording_event(
    logger: logging.Logger,
    event_type: str,
    streamer_name: str,
    stream_id: Optional[int] = None,
    **additional_context: Any
) -> None:
    """Log a recording-related event with structured context

    Args:
        logger: Logger instance
        event_type: Type of recording event (start, stop, error, etc.)
        streamer_name: Name of the streamer
        stream_id: Optional stream ID
        **additional_context: Additional context fields
    """
    context = {
        'event_type': event_type,
        'streamer_name': streamer_name,
        'operation': 'recording'
    }

    if stream_id is not None:
        context['stream_id'] = stream_id

    context.update(additional_context)

    log_with_context(
        logger,
        'info',
        f"Recording {event_type} for {streamer_name}",
        **context
    )


def log_ffmpeg_operation(
    logger: logging.Logger,
    operation: str,
    streamer_name: str,
    input_file: str,
    output_file: str,
    success: bool,
    **additional_context: Any
) -> None:
    """Log an FFmpeg operation with structured context

    Args:
        logger: Logger instance
        operation: FFmpeg operation type (remux, convert, etc.)
        streamer_name: Name of the streamer
        input_file: Input file path
        output_file: Output file path
        success: Whether operation was successful
        **additional_context: Additional context fields
    """
    context = {
        'operation': 'ffmpeg',
        'ffmpeg_operation': operation,
        'streamer_name': streamer_name,
        'input_file': input_file,
        'output_file': output_file,
        'success': success
    }

    context.update(additional_context)

    level = 'info' if success else 'error'
    status = 'completed' if success else 'failed'

    log_with_context(
        logger,
        level,
        f"FFmpeg {operation} {status} for {streamer_name}",
        **context
    )


def log_stream_detection(
    logger: logging.Logger,
    streamer_name: str,
    is_live: bool,
    title: Optional[str] = None,
    category: Optional[str] = None,
    **additional_context: Any
) -> None:
    """Log stream detection result with structured context

    Args:
        logger: Logger instance
        streamer_name: Name of the streamer
        is_live: Whether stream is live
        title: Stream title (if available)
        category: Stream category (if available)
        **additional_context: Additional context fields
    """
    context = {
        'operation': 'stream_detection',
        'streamer_name': streamer_name,
        'is_live': is_live,
        'status': 'LIVE' if is_live else 'OFFLINE'
    }

    if title:
        context['title'] = title
    if category:
        context['category'] = category

    context.update(additional_context)

    log_with_context(
        logger,
        'info',
        f"Stream detection: {streamer_name} is {'LIVE' if is_live else 'OFFLINE'}",
        **context
    )

# Convenience functions for common logging patterns


def log_info(message: str, **context):
    """Log info message with context"""
    logger = get_structured_logger()
    log_with_context(logger, 'info', message, **context)


def log_error(message: str, **context):
    """Log error message with context"""
    logger = get_structured_logger()
    log_with_context(logger, 'error', message, **context)


def log_warning(message: str, **context):
    """Log warning message with context"""
    logger = get_structured_logger()
    log_with_context(logger, 'warning', message, **context)


def log_debug(message: str, **context):
    """Log debug message with context"""
    logger = get_structured_logger()
    log_with_context(logger, 'debug', message, **context)
