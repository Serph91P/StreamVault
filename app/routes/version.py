"""
Version API endpoints for checking StreamVault version and updates.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import httpx
import logging
from datetime import datetime, timedelta

from app.database import get_db
from app.version import get_version_info, VERSION, BRANCH

router = APIRouter(prefix="/version", tags=["version"])
logger = logging.getLogger("streamvault")

# Cache for GitHub API responses (avoid rate limiting)
_update_check_cache = {"data": None, "expires_at": None}


@router.get("")
async def get_version(db: Session = Depends(get_db)):
    """
    Get current StreamVault version information.

    Returns:
        - version: Current version (e.g., "v1.2.3" or "dev")
        - branch: Git branch (main/develop)
        - build_date: ISO timestamp when image was built
        - commit_sha: Git commit SHA (first 7 chars)
        - is_production: True if running main branch
        - update_available: True if newer version exists on GitHub
        - latest_version: Latest version from GitHub (if available)
    """
    version_info = get_version_info()

    # Check for updates (with caching)
    update_info = await _check_for_updates()

    return {**version_info, **update_info}


async def _check_for_updates() -> dict:
    """
    Check GitHub for newer version.
    Uses caching to avoid rate limiting (cache: 5 minutes).
    """
    now = datetime.utcnow()

    # Return cached data if still valid
    if _update_check_cache["expires_at"] and now < _update_check_cache["expires_at"]:
        return _update_check_cache["data"]

    result = {"update_available": False, "latest_version": None, "latest_version_url": None, "update_check_error": None}

    try:
        # Only check for updates on main/develop branches
        if BRANCH not in ["main", "develop"]:
            result["update_check_error"] = "Not checking updates for feature branches"
            return result

        # Determine which releases to check
        if BRANCH == "main":
            # Main branch: Check latest stable release
            api_url = "https://api.github.com/repos/Serph91P/StreamVault/releases/latest"
        else:
            # Develop branch: Check all releases for latest develop tag
            api_url = "https://api.github.com/repos/Serph91P/StreamVault/releases"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                api_url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "StreamVault-UpdateChecker"}
            )

            if response.status_code != 200:
                result["update_check_error"] = f"GitHub API returned {response.status_code}"
                return result

            data = response.json()

            if BRANCH == "main":
                # Main: Direct latest release
                latest_version = data.get("tag_name", "").replace("v", "")
                latest_url = data.get("html_url")
            else:
                # Develop: Find latest develop-tagged release
                if not isinstance(data, list):
                    result["update_check_error"] = "Unexpected GitHub API response"
                    return result

                develop_releases = [r for r in data if "develop" in r.get("tag_name", "").lower()]
                if not develop_releases:
                    result["update_check_error"] = "No develop releases found"
                    return result

                latest_release = develop_releases[0]
                latest_version = latest_release.get("tag_name", "").replace("v", "")
                latest_url = latest_release.get("html_url")

            result["latest_version"] = latest_version
            result["latest_version_url"] = latest_url

            # Compare versions (simple string comparison for semantic versioning)
            current_version = VERSION.replace("v", "")

            # Skip comparison if running dev build
            if current_version == "dev":
                result["update_available"] = False
            else:
                # Parse versions (e.g., "1.2.3" -> [1, 2, 3])
                try:
                    current_parts = [int(x) for x in current_version.split(".")]
                    latest_parts = [int(x) for x in latest_version.split(".")]

                    # Compare major.minor.patch
                    result["update_available"] = latest_parts > current_parts
                except (ValueError, AttributeError):
                    # Fallback to string comparison
                    result["update_available"] = latest_version > current_version

    except httpx.TimeoutException:
        result["update_check_error"] = "GitHub API timeout"
        logger.warning("GitHub update check timed out")
    except Exception as e:
        result["update_check_error"] = str(e)
        logger.error(f"Failed to check for updates: {e}")

    # Cache result for 5 minutes
    _update_check_cache["data"] = result
    _update_check_cache["expires_at"] = now + timedelta(minutes=5)

    return result
