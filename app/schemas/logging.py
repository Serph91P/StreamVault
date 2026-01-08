from pydantic import BaseModel


class LoggingSettingsSchema(BaseModel):
    """Logging settings configuration"""

    # Streamlink logging
    streamlink_log_level: str = "debug"
    streamlink_log_format: str = "[{asctime}][{name}][{levelname}] {message}"
    streamlink_log_date_format: str = "%Y-%m-%d %H:%M:%S"

    # FFmpeg logging
    ffmpeg_log_level: str = "verbose"
    ffmpeg_enable_stats: bool = True
    ffmpeg_enable_report: bool = True

    # General settings
    enable_separate_logs: bool = True
    log_rotation_days: int = 30

    # Retry settings
    enable_auto_retry: bool = True
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 30

    class Config:
        json_encoders = {
            # Add any custom encoders if needed
        }


class LogFileSchema(BaseModel):
    """Schema for log file information"""
    filename: str
    size: int
    last_modified: str
    type: str  # 'streamlink', 'ffmpeg', 'app'


class LogsListSchema(BaseModel):
    """Schema for listing log files"""
    streamlink_logs: list[LogFileSchema]
    ffmpeg_logs: list[LogFileSchema]
    app_logs: list[LogFileSchema]
    total_size: int
