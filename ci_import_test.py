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

# Suppress SQLAlchemy warnings and errors
logging.getLogger('sqlalchemy').setLevel(logging.CRITICAL)

# Set a dummy database URL for testing
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TESTING"] = "true"
os.environ["SQLALCHEMY_SILENCE_UBER_WARNING"] = "1"  # Silence SQLAlchemy warnings

# Add the current directory to the path
sys.path.insert(0, '.')

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

# Mock SQLAlchemy operations
with mock.patch('sqlalchemy.orm.Query.first', return_value=None), \
     mock.patch('sqlalchemy.orm.Query.scalar', return_value=None), \
     mock.patch('sqlalchemy.engine.Engine.connect'):

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
