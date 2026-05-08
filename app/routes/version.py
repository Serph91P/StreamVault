"""
Version API endpoints for checking StreamVault version and updates.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import httpx
import logging
import re
from datetime import datetime, timedelta

from app.database import get_db
from app.version import get_version_info, VERSION, BRANCH

router = APIRouter(prefix="/version", tags=["version"])
logger = logging.getLogger("streamvault")

# Cache for GitHub API responses (avoid rate limiting)
_update_check_cache = {"data": None, "expires_at": None}

GITHUB_REPO = "Serph91P/StreamVault"


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
        - release_channel: Which channel was checked ("stable" or "prerelease")
    """
    version_info = get_version_info()

    # Check for updates (with caching)
    update_info = await _check_for_updates()

    return {**version_info, **update_info}


def _is_prerelease_version(version: str) -> bool:
    """
    Determine if the running build is a prerelease/develop build.

    Heuristics (in order):
      1. Explicit BRANCH == "develop" wins.
      2. Version string contains "-dev" or starts with "dev." -> prerelease.
      3. Version string is the literal "dev" placeholder -> prerelease
         (local/unknown build, default to develop channel).
      4. Otherwise stable.
    """
    if BRANCH == "develop":
        return True
    if BRANCH == "main":
        return False
    v = (version or "").lower()
    if "-dev" in v or v.startswith("dev.") or v.startswith("dev-"):
        return True
    if v in ("dev", "unknown", ""):
        return True
    return False


_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _parse_version_tuple(version: str) -> tuple[int, int, int] | None:
    """Extract (major, minor, patch) from a version string. Returns None on failure."""
    if not version:
        return None
    m = _VERSION_RE.search(version)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


async def _check_for_updates() -> dict:
    """
    Check GitHub for newer version.
    Uses caching to avoid rate limiting (cache: 5 minutes).

    Channel selection is driven by the running version's suffix (not BRANCH),
    so unknown/local builds still get a sensible check:
      - Prerelease builds (-dev / develop) are compared against the highest
        prerelease on GitHub.
      - Stable builds are compared against /releases/latest.
    """
    now = datetime.utcnow()

    # Return cached data if still valid
    if _update_check_cache["expires_at"] and now < _update_check_cache["expires_at"]:
        return _update_check_cache["data"]

    is_prerelease = _is_prerelease_version(VERSION)
    channel = "prerelease" if is_prerelease else "stable"

    result = {
        "update_available": False,
        "latest_version": None,
        "latest_version_url": None,
        "update_check_error": None,
        "release_channel": channel,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "StreamVault-UpdateChecker",
            }

            if not is_prerelease:
                # Stable channel: latest non-prerelease release.
                response = await client.get(
                    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                    headers=headers,
                )
                if response.status_code != 200:
                    result["update_check_error"] = (
                        f"GitHub API returned {response.status_code}"
                    )
                    return _cache_and_return(result, now)

                data = response.json()
                latest_tag = data.get("tag_name", "")
                latest_url = data.get("html_url")
            else:
                # Prerelease channel: scan recent releases, take the highest
                # prerelease by semver (independent of GitHub's sort order).
                response = await client.get(
                    f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=30",
                    headers=headers,
                )
                if response.status_code != 200:
                    result["update_check_error"] = (
                        f"GitHub API returned {response.status_code}"
                    )
                    return _cache_and_return(result, now)

                data = response.json()
                if not isinstance(data, list):
                    result["update_check_error"] = "Unexpected GitHub API response"
                    return _cache_and_return(result, now)

                prereleases = [r for r in data if r.get("prerelease")]
                if not prereleases:
                    # No prereleases yet, treat as up-to-date.
                    result["latest_version"] = VERSION
                    return _cache_and_return(result, now)

                def _key(r):
                    parsed = _parse_version_tuple(r.get("tag_name", ""))
                    return parsed if parsed else (-1, -1, -1)

                latest_release = max(prereleases, key=_key)
                latest_tag = latest_release.get("tag_name", "")
                latest_url = latest_release.get("html_url")

            # Strip a leading "v" but keep the rest of the tag for display.
            latest_display = (
                latest_tag[1:] if latest_tag.startswith("v") else latest_tag
            )
            result["latest_version"] = latest_display
            result["latest_version_url"] = latest_url

            # Compare semver tuples. If parsing fails on either side we cannot
            # tell, so we fall back to "no update" rather than crying wolf.
            current_parts = _parse_version_tuple(VERSION)
            latest_parts = _parse_version_tuple(latest_tag)

            if current_parts and latest_parts:
                result["update_available"] = latest_parts > current_parts
            elif latest_parts and not current_parts:
                # Local build (VERSION == "dev" / "unknown") cannot be compared.
                # Surface the latest version but do not flag an update so we
                # don't nag developers running their own builds.
                result["update_available"] = False

    except httpx.TimeoutException:
        result["update_check_error"] = "GitHub API timeout"
        logger.warning("GitHub update check timed out")
    except Exception as e:
        result["update_check_error"] = "Failed to check for updates"
        logger.error(f"Failed to check for updates: {e}")

    return _cache_and_return(result, now)


def _cache_and_return(result: dict, now: datetime) -> dict:
    """Cache the result for 5 minutes and return it."""
    _update_check_cache["data"] = result
    _update_check_cache["expires_at"] = now + timedelta(minutes=5)
    return result
