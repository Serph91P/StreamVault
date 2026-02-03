"""
Version information for StreamVault.
This file is auto-populated during Docker build with build args.
"""

import os
from datetime import datetime, UTC

# Build-time information (injected by Docker build)
VERSION = os.getenv("STREAMVAULT_VERSION", "dev")
BRANCH = os.getenv("STREAMVAULT_BRANCH", "unknown")
BUILD_DATE = os.getenv("STREAMVAULT_BUILD_DATE", datetime.now(UTC).isoformat())
COMMIT_SHA = os.getenv("STREAMVAULT_COMMIT_SHA", "unknown")

# Application metadata
APP_NAME = "StreamVault"
DESCRIPTION = "Automated Twitch stream recording and management system"
REPOSITORY = "https://github.com/Serph91P/StreamVault"


def get_version_info() -> dict:
    """Get complete version information."""
    return {
        "app_name": APP_NAME,
        "version": VERSION,
        "branch": BRANCH,
        "build_date": BUILD_DATE,
        "commit_sha": COMMIT_SHA,
        "description": DESCRIPTION,
        "repository": REPOSITORY,
        "is_production": BRANCH == "main",
        "is_development": BRANCH == "develop",
    }
