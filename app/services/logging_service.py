import os
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

logger = logging.getLogger("streamvault")


class LoggingService:
    """Enhanced logging service for StreamVault with separate logging for FFmpeg and Streamlink"""
    
    def __init__(self, logs_base_dir: str = "/app/logs"):
        self.logs_base_dir = Path(logs_base_dir)
        self.streamlink_logs_dir = self.logs_base_dir / "streamlink"
        self.ffmpeg_logs_dir = self.logs_base_dir / "ffmpeg"
        self.app_logs_dir = self.logs_base_dir / "app"
        
        # Create directories
        self._ensure_log_directories()
        
        # Initialize loggers
        self._setup_loggers()
    
    def _ensure_log_directories(self):
        """Create log directories if they don't exist"""
        for log_dir in [self.streamlink_logs_dir, self.ffmpeg_logs_dir, self.app_logs_dir]:
            log_dir.mkdir(parents=True, exist_ok=True)
            # Ensure proper permissions
            os.chmod(log_dir, 0o755)
    
    def _setup_loggers(self):
        """Setup separate loggers for different components"""
        # Streamlink logger
        self.streamlink_logger = logging.getLogger("streamvault.streamlink")
        streamlink_handler = TimedRotatingFileHandler(
            self.streamlink_logs_dir / "streamlink.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        streamlink_handler.setFormatter(
            logging.Formatter("[{asctime}][{name}][{levelname}] {message}", style="{")
        )
        self.streamlink_logger.addHandler(streamlink_handler)
        self.streamlink_logger.setLevel(logging.DEBUG)
        
        # FFmpeg logger
        self.ffmpeg_logger = logging.getLogger("streamvault.ffmpeg")
        ffmpeg_handler = TimedRotatingFileHandler(
            self.ffmpeg_logs_dir / "ffmpeg.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        ffmpeg_handler.setFormatter(
            logging.Formatter("[{asctime}][{name}][{levelname}] {message}", style="{")
        )
        self.ffmpeg_logger.addHandler(ffmpeg_handler)
        self.ffmpeg_logger.setLevel(logging.DEBUG)
        
        # Recording activity logger
        self.recording_logger = logging.getLogger("streamvault.recording")
        recording_handler = TimedRotatingFileHandler(
            self.app_logs_dir / "recording_activity.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        recording_handler.setFormatter(
            logging.Formatter("[{asctime}][{levelname}] {message}", style="{")
        )
        self.recording_logger.addHandler(recording_handler)
        self.recording_logger.setLevel(logging.DEBUG)
    
    def get_streamlink_log_path(self, streamer_name: str) -> str:
        """Get log file path for a specific streamer's streamlink session"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.streamlink_logs_dir / f"{streamer_name}_{today}.log"
        return str(log_file)
    
    def get_ffmpeg_log_path(self, operation: str, identifier: Optional[str] = None) -> str:
        """Get log file path for FFmpeg operations"""
        today = datetime.now().strftime("%Y-%m-%d")
        if identifier:
            log_file = self.ffmpeg_logs_dir / f"{operation}_{identifier}_{today}.log"
        else:
            log_file = self.ffmpeg_logs_dir / f"{operation}_{today}.log"
        return str(log_file)
    
    def log_streamlink_start(self, streamer_name: str, quality: str, output_path: str, cmd: List[str]):
        """Log streamlink command start"""
        self.streamlink_logger.info(f"Starting recording for {streamer_name}")
        self.streamlink_logger.info(f"Quality: {quality}")
        self.streamlink_logger.info(f"Output: {output_path}")
        self.streamlink_logger.info(f"Command: {' '.join(cmd)}")
    
    def log_streamlink_output(self, streamer_name: str, stdout: bytes, stderr: bytes, exit_code: int):
        """Log streamlink process output"""
        if stdout:
            stdout_text = stdout.decode("utf-8", errors="ignore")
            self.streamlink_logger.info(f"[{streamer_name}] STDOUT:\n{stdout_text}")
        
        if stderr:
            stderr_text = stderr.decode("utf-8", errors="ignore")
            if exit_code == 0:
                self.streamlink_logger.info(f"[{streamer_name}] STDERR:\n{stderr_text}")
            else:
                self.streamlink_logger.error(f"[{streamer_name}] STDERR (exit {exit_code}):\n{stderr_text}")
    
    def log_ffmpeg_start(self, operation: str, cmd: List[str], identifier: Optional[str] = None):
        """Log FFmpeg command start"""
        self.ffmpeg_logger.info(f"Starting {operation} operation" + (f" for {identifier}" if identifier else ""))
        self.ffmpeg_logger.info(f"Command: {' '.join(cmd)}")
    
    def log_ffmpeg_output(self, operation: str, stdout: bytes, stderr: bytes, exit_code: int, identifier: Optional[str] = None):
        """Log FFmpeg process output"""
        prefix = f"[{operation}" + (f"_{identifier}" if identifier else "") + "]"
        
        if stdout:
            stdout_text = stdout.decode("utf-8", errors="ignore")
            self.ffmpeg_logger.info(f"{prefix} STDOUT:\n{stdout_text}")
        
        if stderr:
            stderr_text = stderr.decode("utf-8", errors="ignore")
            if exit_code == 0:
                self.ffmpeg_logger.info(f"{prefix} STDERR:\n{stderr_text}")
            else:
                self.ffmpeg_logger.error(f"{prefix} STDERR (exit {exit_code}):\n{stderr_text}")
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up log files older than specified days"""
        try:
            import time
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            
            for log_dir in [self.streamlink_logs_dir, self.ffmpeg_logs_dir, self.app_logs_dir]:
                for log_file in log_dir.glob("*.log*"):
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        logger.info(f"Cleaned up old log file: {log_file}")
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}", exc_info=True)
    
    # === Recording Activity Logging Methods ===
    
    def log_recording_activity(self, activity_type: str, streamer_name: str, details: str = "", level: str = "info"):
        """Log recording activities with detailed context"""
        message = f"[{activity_type}] {streamer_name}"
        if details:
            message += f" - {details}"
        
        if level == "debug":
            self.recording_logger.debug(message)
        elif level == "warning":
            self.recording_logger.warning(message)
        elif level == "error":
            self.recording_logger.error(message)
        else:
            self.recording_logger.info(message)
    
    def log_recording_start(self, streamer_id: int, streamer_name: str, quality: str, output_path: str):
        """Log recording start with all relevant details"""
        self.recording_logger.info(f"[RECORDING_START] {streamer_name} (ID: {streamer_id})")
        self.recording_logger.info(f"[RECORDING_START] Quality: {quality}")
        self.recording_logger.info(f"[RECORDING_START] Output: {output_path}")
    
    def log_recording_stop(self, streamer_id: int, streamer_name: str, duration: float, output_path: str, reason: str = "manual"):
        """Log recording stop with duration and details"""
        self.recording_logger.info(f"[RECORDING_STOP] {streamer_name} (ID: {streamer_id})")
        self.recording_logger.info(f"[RECORDING_STOP] Duration: {duration:.2f} seconds")
        self.recording_logger.info(f"[RECORDING_STOP] Output: {output_path}")
        self.recording_logger.info(f"[RECORDING_STOP] Reason: {reason}")
    
    def log_recording_error(self, streamer_id: int, streamer_name: str, error_type: str, error_message: str):
        """Log recording errors with context"""
        self.recording_logger.error(f"[RECORDING_ERROR] {streamer_name} (ID: {streamer_id}) - {error_type}: {error_message}")
    
    def log_stream_detection(self, streamer_name: str, is_live: bool, stream_info: Optional[Dict[str, Any]] = None):
        """Log stream detection results"""
        status = "LIVE" if is_live else "OFFLINE"
        self.recording_logger.info(f"[STREAM_DETECTION] {streamer_name}: {status}")
        if stream_info and is_live:
            title = stream_info.get('title', 'Unknown')
            category = stream_info.get('category_name', 'Unknown')
            self.recording_logger.info(f"[STREAM_DETECTION] {streamer_name} - Title: {title}, Category: {category}")
    
    def log_file_operation(self, operation: str, file_path: str, success: bool, details: str = "", size_mb: Optional[float] = None):
        """Log file operations (remux, conversion, cleanup, etc.)"""
        status = "SUCCESS" if success else "FAILED"
        message = f"[FILE_OPERATION] {operation}: {file_path} - {status}"
        if size_mb:
            message += f" (Size: {size_mb:.2f} MB)"
        if details:
            message += f" - {details}"
        
        if success:
            self.recording_logger.info(message)
        else:
            self.recording_logger.error(message)
    
    def log_configuration_change(self, setting: str, old_value: str, new_value: str, streamer_id: Optional[int] = None):
        """Log configuration changes"""
        target = "Global" if streamer_id is None else f"Streamer {streamer_id}"
        self.recording_logger.info(f"[CONFIG_CHANGE] {target}: {setting} changed from '{old_value}' to '{new_value}'")


# Global logging service instance
logging_service = LoggingService()
