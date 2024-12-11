import logging
import sys
from app.config.settings import settings

def setup_logging():
    logger = logging.getLogger('streamvault')
    logger.setLevel(settings.LOG_LEVEL)

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