import logging
import logging.handlers
import sys
import json
import re
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

request_context: ContextVar[str | None] = ContextVar("request_id", default=None)


def _redact(message: str) -> str:
    """Remove credential-like URL, query, and header values from log output."""
    message = re.sub(r"(://[^:/\s]+:)[^@\s]+(@)", r"\1***\2", message)
    message = re.sub(r"(?i)(authorization)\s*:\s*bearer\s+[^\s;]+", r"\1: ***", message)
    message = re.sub(
        r"(?i)(cookie|set-cookie|x-api-key)\s*:\s*[^\s;]+", r"\1: ***", message
    )
    message = re.sub(
        r"(?i)(token|secret|password|authorization|api[_-]?key)=([^&\s]+)",
        r"\1=***",
        message,
    )
    return message


class RedactingFormatter(logging.Formatter):
    """Apply the same redaction policy to the standard text log format."""

    def format(self, record):
        return _redact(super().format(record))


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        request_id = getattr(record, "request_id", None) or request_context.get()
        if request_id:
            log_entry["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = _redact(self.formatException(record.exc_info))

        # Add extra fields if present
        if hasattr(record, "streamer_name"):
            log_entry["streamer_name"] = record.streamer_name
        if hasattr(record, "stream_id"):
            log_entry["stream_id"] = record.stream_id
        if hasattr(record, "operation"):
            log_entry["operation"] = record.operation
        if hasattr(record, "recording_id"):
            log_entry["recording_id"] = record.recording_id
        if hasattr(record, "task_id"):
            log_entry["task_id"] = record.task_id

        return json.dumps(log_entry)


def setup_logging(app_settings=None):
    """Setup logging with daily rotating files"""
    if app_settings is None:
        from app.config.settings import get_settings

        app_settings = get_settings()

    logger = logging.getLogger("streamvault")
    logger.setLevel(app_settings.LOG_LEVEL)
    logger.propagate = False

    # Choose formatter based on environment
    use_json = app_settings.LOG_FORMAT.lower() == "json"

    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = RedactingFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Console handler
    if not any(
        getattr(handler, "_streamvault_console", False) for handler in logger.handlers
    ):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler._streamvault_console = True
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Ensure log directories exist - use environment variable or fallback
    logs_base = app_settings.LOGS_BASE_DIR or app_settings.LOG_DIR or "/app/logs"
    logs_dir = Path(logs_base)
    app_logs_dir = logs_dir / "app"
    app_logs_dir.mkdir(parents=True, exist_ok=True)

    # Daily rotating file handler instead of simple file handler
    # CRITICAL: Convert Path to string - TimedRotatingFileHandler expects string!
    log_file_path = str(app_logs_dir / "streamvault.log")

    try:
        rotating_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_file_path,
            when="midnight",
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding="utf-8",
            utc=True,
        )
        rotating_handler.setFormatter(formatter)

        # Set the suffix for rotated files (will be streamvault.log.2025-09-17)
        rotating_handler.suffix = "%Y-%m-%d"

        if not any(
            getattr(handler, "baseFilename", None) == log_file_path
            for handler in logger.handlers
        ):
            logger.addHandler(rotating_handler)

        # Verify handler was added successfully
        logger.info(f"📝 TimedRotatingFileHandler configured for: {log_file_path}")

    except Exception as e:
        # If handler creation fails, log to console only
        logger.error(
            f"❌ Failed to create TimedRotatingFileHandler for {log_file_path}: {e}"
        )
        logger.error("Logs will only be written to Docker stdout, not to file!")

    return logger
