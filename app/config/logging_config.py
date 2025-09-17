import logging
import logging.handlers
import sys
import json
from datetime import datetime
from pathlib import Path
from app.config.settings import settings

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'streamer_name'):
            log_entry['streamer_name'] = record.streamer_name
        if hasattr(record, 'stream_id'):
            log_entry['stream_id'] = record.stream_id
        if hasattr(record, 'operation'):
            log_entry['operation'] = record.operation
        if hasattr(record, 'recording_id'):
            log_entry['recording_id'] = record.recording_id
        if hasattr(record, 'task_id'):
            log_entry['task_id'] = record.task_id
            
        return json.dumps(log_entry)

def setup_logging():
    """Setup logging with daily rotating files"""
    logger = logging.getLogger('streamvault')
    logger.setLevel(settings.LOG_LEVEL)

    # Choose formatter based on environment
    use_json = getattr(settings, 'LOG_FORMAT', 'text').lower() == 'json'
    
    if use_json:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Ensure log directories exist
    logs_dir = Path("/app/logs")
    app_logs_dir = logs_dir / "app"
    app_logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Daily rotating file handler instead of simple file handler
    rotating_handler = logging.handlers.TimedRotatingFileHandler(
        filename=app_logs_dir / 'streamvault.log',
        when='midnight',
        interval=1,
        backupCount=30,  # Keep 30 days of logs
        encoding='utf-8',
        utc=True
    )
    rotating_handler.setFormatter(formatter)
    
    # Set the suffix for rotated files (will be streamvault.log.2025-09-17)
    rotating_handler.suffix = '%Y-%m-%d'
    
    logger.addHandler(rotating_handler)

    # Initialize the structured logging service
    try:
        from app.services.system.logging_service import logging_service
        logger.info("Structured logging service initialized")
        
        # Schedule periodic cleanup of old logs
        import asyncio
        import threading
        
        def start_cleanup_scheduler():
            """Start the log cleanup scheduler in a separate thread"""
            import time
            
            def cleanup_scheduler():
                """Schedule periodic log cleanup"""
                while True:
                    time.sleep(24 * 3600)  # Run every 24 hours
                    try:
                        logging_service.cleanup_old_logs()
                    except Exception as e:
                        logger.error(f"Error during scheduled log cleanup: {e}")
            
            try:
                cleanup_scheduler()
            except KeyboardInterrupt:
                logger.info("Log cleanup scheduler stopped")
            except Exception as e:
                logger.error(f"Log cleanup scheduler error: {e}")
        
        # Start the cleanup scheduler in a daemon thread
        cleanup_thread = threading.Thread(target=start_cleanup_scheduler, daemon=True)
        cleanup_thread.start()
        
    except Exception as e:
        logger.warning(f"Could not initialize structured logging service: {e}")

    return logger
