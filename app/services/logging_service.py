import os
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
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
    
    def get_streamlink_log_path(self, streamer_name: str) -> str:
        """Get log file path for a specific streamer's streamlink session"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.streamlink_logs_dir / f"{streamer_name}_{today}.log"
        return str(log_file)
    
    def get_ffmpeg_log_path(self, operation: str, identifier: str = None) -> str:
        """Get log file path for FFmpeg operations"""
        today = datetime.now().strftime("%Y-%m-%d")
        if identifier:
            log_file = self.ffmpeg_logs_dir / f"{operation}_{identifier}_{today}.log"
        else:
            log_file = self.ffmpeg_logs_dir / f"{operation}_{today}.log"
        return str(log_file)
    
    def log_streamlink_start(self, streamer_name: str, quality: str, output_path: str, cmd: list):
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
    
    def log_ffmpeg_start(self, operation: str, cmd: list, identifier: str = None):
        """Log FFmpeg command start"""
        self.ffmpeg_logger.info(f"Starting {operation} operation" + (f" for {identifier}" if identifier else ""))
        self.ffmpeg_logger.info(f"Command: {' '.join(cmd)}")
    
    def log_ffmpeg_output(self, operation: str, stdout: bytes, stderr: bytes, exit_code: int, identifier: str = None):
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


# Global logging service instance
logging_service = LoggingService()
