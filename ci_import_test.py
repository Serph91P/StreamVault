#!/usr/bin/env python
"""
CI import test script for GitHub Actions.

This is a simplified version that just imports key modules without trying
to initialize services or connect to databases. It's designed to catch
basic import and syntax errors.
"""

import os
import sys
import logging
from unittest import mock
from pathlib import Path

# Suppress SQLAlchemy warnings and errors
logging.getLogger('sqlalchemy').setLevel(logging.CRITICAL)

# Set a dummy database URL for testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TESTING"] = "true"
os.environ["SQLALCHEMY_SILENCE_UBER_WARNING"] = "1"  # Silence SQLAlchemy warnings
os.environ["LOGS_DIR"] = "/tmp/logs"  # Use /tmp for logs in CI environment

# Add the current directory to the path
sys.path.insert(0, '.')

# Create directories that might be accessed during import
for dir_path in ['/tmp/logs', '/tmp/logs/streamlink', '/tmp/logs/ffmpeg', '/tmp/logs/app', '/app']:
    Path(dir_path).mkdir(parents=True, exist_ok=True)
    try:
        # Make directories writable by all
        os.chmod(dir_path, 0o777)
    except:
        print(f"Warning: Could not chmod {dir_path}, but continuing anyway")

# Mock external dependencies
modules_to_mock = [
    'aiofiles', 'py_vapid', 'py_vapid.utils', 'fastapi_login',
    'apprise', 'pywebpush', 'fastapi_events', 'fastapi_events.middleware',
    'fastapi_events.handlers', 'pywebpush.webpush', 'py_vapid.utils.b64urlencode',
]
for module_name in modules_to_mock:
    sys.modules[module_name] = mock.MagicMock()

# Define custom mocks
class MockVapid:
    def __init__(self, private_key=None):
        pass
    
    def generate_keys(self):
        pass
        
    @staticmethod
    def from_string(private_key):
        return MockVapid()
        
    def private_key_bytes(self):
        return b'mock_private_key'
        
    def public_key_bytes(self):
        return b'mock_public_key'
        
    def sign(self, claims):
        return {"auth": "mock-auth-token"}

# Add specific mock implementations
if 'py_vapid' in sys.modules:
    sys.modules['py_vapid'].Vapid = MockVapid

# Patch the LoggingService class to avoid file system access issues
def patch_logging_service():
    from app.services.logging_service import LoggingService
    
    # Override the constructor to use /tmp
    original_init = LoggingService.__init__
    def safe_init(self, logs_base_dir=None):
        logs_base_dir = "/tmp/logs"
        original_init(self, logs_base_dir)
    LoggingService.__init__ = safe_init
    
    # Override filesystem operations that might cause issues
    LoggingService.get_streamlink_log_path = lambda self, streamer_name: f"/tmp/logs/streamlink/{streamer_name}.log"
    LoggingService.get_ffmpeg_log_path = lambda self, operation, identifier=None: f"/tmp/logs/ffmpeg/{operation}.log"

# Mock SQLAlchemy operations
with mock.patch('sqlalchemy.orm.Query.first', return_value=None), \
     mock.patch('sqlalchemy.orm.Query.scalar', return_value=None), \
     mock.patch('sqlalchemy.engine.Engine.connect'):

    # Patch the logging service before imports
    try:
        # Import the module first to patch it
        from app.services.logging_service import LoggingService, logging_service
        patch_logging_service()
        
        # Re-patch the global instance
        from app.services.logging_service import logging_service
        logging_service.logs_base_dir = Path("/tmp/logs")
        logging_service.streamlink_logs_dir = Path("/tmp/logs/streamlink")
        logging_service.ffmpeg_logs_dir = Path("/tmp/logs/ffmpeg")
        logging_service.app_logs_dir = Path("/tmp/logs/app")
        
        # Override instance methods
        logging_service.get_streamlink_log_path = lambda streamer_name: f"/tmp/logs/streamlink/{streamer_name}.log"
        logging_service.get_ffmpeg_log_path = lambda operation, identifier=None: f"/tmp/logs/ffmpeg/{operation}.log"
    except Exception as e:
        print(f"Warning: Could not patch logging service: {e}")

    # List of modules to test import
    modules_to_test = [
        'app.database',
        'app.models',
        'app.config.settings',
        'app.config.logging_config',
        'app.utils.path_utils',
        'app.utils.file_utils',
        'app.utils.ffmpeg_utils',
        'app.utils.streamlink_utils',
        'migrations.manage',
    ]
    
    # Try importing each module
    failed = False
    for module in modules_to_test:
        try:
            print(f"Testing import of {module}")
            __import__(module)
            print(f"✓ Successfully imported {module}")
        except Exception as e:
            print(f"✗ Failed to import {module}: {e}")
            failed = True
    
    # Exit with appropriate status code
    if failed:
        sys.exit(1)
    else:
        print("All critical imports successful!")
        sys.exit(0)
