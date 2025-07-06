#!/usr/bin/env python
"""
Import test script that sets up a mock environment for testing imports
without requiring an actual database connection.

This script mocks necessary modules and environment variables to allow
checking for import errors in CI environments without needing real
database connections or third-party services.
"""

import os
import sys
import secrets
from unittest import mock

# Set all required environment variables for testing
os.environ.update({
    "DATABASE_URL": "sqlite:///:memory:",
    "TWITCH_APP_ID": "test_client_id",
    "TWITCH_APP_SECRET": "test_client_secret",
    "BASE_URL": "http://localhost:8000",
    "POSTGRES_USER": "testuser",
    "POSTGRES_PASSWORD": "testpass",
    "POSTGRES_DB": "testdb",
    "EVENTSUB_SECRET": secrets.token_urlsafe(16),
    "TESTING": "true"
})

# Add the current directory to the path
sys.path.insert(0, '.')

# Define a list of modules to mock
MODULES_TO_MOCK = [
    'aiofiles',
    'py_vapid',
    'py_vapid.utils',
    'fastapi_login',
    'apprise',
    'pywebpush',
    'fastapi_events',
    'fastapi_events.middleware',
    'fastapi_events.handlers',
]

# Mock all modules
for module_name in MODULES_TO_MOCK:
    sys.modules[module_name] = mock.MagicMock()

# Now modify app.main to avoid service initialization
# This is a temporary patch just for testing imports
try:
    with open('app/main.py', 'r') as f:
        main_content = f.read()

    with open('app/main.py', 'r+') as f:
        if 'if os.getenv("TESTING") != "true":' not in main_content:
            # Add a conditional to prevent service initialization during testing
            new_content = main_content.replace(
                "# Initialize logging service",
                "# Skip initialization during testing\nif os.getenv(\"TESTING\") != \"true\":\n"
                "    # Initialize logging service"
            )
            f.seek(0)
            f.write(new_content)
            f.truncate()
except Exception as e:
    print(f"Warning: Could not modify app/main.py: {e}")

try:
    # Now attempt to import the main module
    with mock.patch('sqlalchemy.orm.Query.first', return_value=None):
        with mock.patch('sqlalchemy.orm.Query.scalar', return_value=None):
            with mock.patch('sqlalchemy.engine.Engine.connect'):
                import app.main
    print("Successfully imported all modules")
    
    # Restore the original main.py
    try:
        with open('app/main.py', 'w') as f:
            f.write(main_content)
    except Exception as e:
        print(f"Warning: Could not restore app/main.py: {e}")
        
    sys.exit(0)
except Exception as e:
    # Restore the original main.py even if there was an error
    try:
        with open('app/main.py', 'w') as f:
            f.write(main_content)
    except Exception as e2:
        print(f"Warning: Could not restore app/main.py: {e2}")
        
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
