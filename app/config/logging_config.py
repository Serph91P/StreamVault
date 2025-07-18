import logging
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
    """Setup logging with structured file outputs"""
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
    
    # File handler for persistent logs in the app directory
    file_handler = logging.FileHandler(app_logs_dir / 'streamvault.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Initialize the structured logging service
    try:
        from app.services.system.logging_service import logging_service
        logger.info("Structured logging service initialized")
        
        # Schedule periodic cleanup of old logs
        import asyncio
        import threading
        
        def start_cleanup_scheduler():
            """Start the log cleanup scheduler in a separate thread"""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def cleanup_scheduler():
                """Schedule periodic log cleanup"""
                while True:
                    await asyncio.sleep(24 * 3600)  # Run every 24 hours
                    try:
                        logging_service.cleanup_old_logs()
                    except Exception as e:
                        logger.error(f"Error during scheduled log cleanup: {e}")
            
            cleanup_task = loop.create_task(cleanup_scheduler())
        
        # Start the cleanup scheduler in a daemon thread
        cleanup_thread = threading.Thread(target=start_cleanup_scheduler, daemon=True)
        cleanup_thread.start()
        
    except Exception as e:
        logger.warning(f"Could not initialize structured logging service: {e}")

    return logger
