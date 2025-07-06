import os
import logging
import asyncio
import time
import re
from datetime import datetime, timezone, timedelta
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
        
        # Log retention settings
        self.streamer_log_retention_days = 14  # Keep streamer-specific logs for 14 days
        self.system_log_retention_days = 30    # Keep system logs for 30 days
        
        # Create directories
        self._ensure_log_directories()
        
        # Initialize loggers
        self._setup_loggers()
        
        # Clean up old logs on initialization
        self.cleanup_old_logs()
    
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
        
        # FFmpeg logger (now streamer-specific, so this is for general/fallback messages only)
        self.ffmpeg_logger = logging.getLogger("streamvault.ffmpeg")
        ffmpeg_handler = TimedRotatingFileHandler(
            self.ffmpeg_logs_dir / "ffmpeg_system.log",  # Changed from generic ffmpeg.log
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
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Format consistently with FFmpeg logs: streamer_streamlink_timestamp_date.log
        streamer_name = streamer_name.replace(" ", "_")  # Remove spaces from streamer name
        log_file = self.streamlink_logs_dir / f"{streamer_name}_streamlink_{timestamp_str}_{today}.log"
        return str(log_file)
    
    def get_ffmpeg_log_path(self, operation: str, streamer_name: str) -> str:
        """Get log file path for FFmpeg operations with mandatory streamer name"""
        today = datetime.now().strftime("%Y-%m-%d")
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Place streamer name first for better organization and visual scanning
        # Format: streamer_operation_timestamp_date.log
        # This makes it easier to find logs for a specific streamer
        streamer_name = streamer_name.replace(" ", "_")  # Remove spaces from streamer name
        log_file = self.ffmpeg_logs_dir / f"{streamer_name}_{operation}_{timestamp_str}_{today}.log"
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
    
    def log_ffmpeg_start(self, operation: str, cmd: List[str], streamer_name: str):
        """Log FFmpeg command start with mandatory streamer name"""
        self.ffmpeg_logger.info(f"Starting {operation} operation for streamer: {streamer_name}")
        self.ffmpeg_logger.info(f"Command: {' '.join(cmd)}")
        
        # Generate a streamer-specific log filename for this operation
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = self.get_ffmpeg_log_path(f"{operation}_{timestamp_str}", streamer_name)
        return log_path
    
    def log_ffmpeg_output(self, operation: str, stdout: bytes, stderr: bytes, exit_code: int, streamer_name: str):
        """Log FFmpeg process output with mandatory streamer name"""
        prefix = f"[{operation}_{streamer_name}]"
        
        if stdout:
            stdout_text = stdout.decode("utf-8", errors="ignore") if isinstance(stdout, bytes) else stdout
            self.ffmpeg_logger.info(f"{prefix} STDOUT:\n{stdout_text}")
        
        if stderr:
            stderr_text = stderr.decode("utf-8", errors="ignore") if isinstance(stderr, bytes) else stderr
            if exit_code == 0:
                self.ffmpeg_logger.info(f"{prefix} STDERR:\n{stderr_text}")
            else:
                self.ffmpeg_logger.error(f"{prefix} STDERR (exit {exit_code}):\n{stderr_text}")
    
    def cleanup_old_logs(self):
        """Clean up old log files based on retention settings.
        
        This removes:
        - Old streamer-specific FFmpeg log files older than streamer_log_retention_days
        - Old streamer-specific Streamlink log files older than streamer_log_retention_days
        - Keeps main system logs according to system_log_retention_days
        """
        try:
            logger.info(f"Starting log cleanup. Retention: streamer logs={self.streamer_log_retention_days} days, system logs={self.system_log_retention_days} days")
            
            # Clean FFmpeg logs
            self._cleanup_directory(
                self.ffmpeg_logs_dir, 
                self.streamer_log_retention_days,
                self.system_log_retention_days
            )
            
            # Clean Streamlink logs
            self._cleanup_directory(
                self.streamlink_logs_dir, 
                self.streamer_log_retention_days,
                self.system_log_retention_days
            )
            
            # Clean App logs (all considered system logs)
            self._cleanup_directory(
                self.app_logs_dir, 
                self.system_log_retention_days,
                self.system_log_retention_days
            )
            
            logger.info("Log cleanup completed")
        except Exception as e:
            logger.error(f"Error during log cleanup: {e}", exc_info=True)
    
    def _is_system_log(self, filename: str) -> bool:
        """Determine if a file is a system log or a streamer-specific log.
        
        Args:
            filename: The filename to check
            
        Returns:
            bool: True if it's a system log, False if it's a streamer-specific log
        """
        system_log_patterns = [
            r"ffmpeg_system",
            r"streamlink\.log",
            r"recording_activity",
        ]
        
        for pattern in system_log_patterns:
            if re.search(pattern, filename):
                return True
                
        return False

    def _cleanup_directory(self, directory: Path, streamer_retention_days: int, system_retention_days: int):
        """Clean up log files in a directory based on retention days.
        
        Args:
            directory: Directory to clean up
            streamer_retention_days: Days to retain streamer-specific logs
            system_retention_days: Days to retain system logs
        """
        if not directory.exists():
            return
            
        now = datetime.now()
        streamer_cutoff = now - timedelta(days=streamer_retention_days)
        system_cutoff = now - timedelta(days=system_retention_days)
        
        deleted_count = 0
        skipped_count = 0
        
        for log_file in directory.glob("*.log*"):
            try:
                # Check file modification time
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                
                # Determine if this is a system log or a streamer log
                is_system = self._is_system_log(log_file.name)
                
                # Check against the appropriate cutoff date
                cutoff = system_cutoff if is_system else streamer_cutoff
                
                if mtime < cutoff:
                    # Log file is older than the cutoff, delete it
                    os.remove(log_file)
                    deleted_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing log file {log_file}: {e}", exc_info=True)
        
        logger.info(f"Cleaned {directory}: deleted {deleted_count} log files, kept {skipped_count}")
    
    async def _schedule_cleanup(self, interval_hours: int = 24):
        """Schedule periodic log cleanup.
        
        Args:
            interval_hours: How often to run cleanup (in hours)
        """
        while True:
            # Sleep for the specified interval
            await asyncio.sleep(interval_hours * 3600)
            
            # Run cleanup
            self.cleanup_old_logs()
    
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
