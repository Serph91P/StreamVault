import logging
import sys
import json
from datetime import datetime
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
            
        return json.dumps(log_entry)

def setup_logging():
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

    # File handler for persistent logs
    file_handler = logging.FileHandler('streamvault.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger