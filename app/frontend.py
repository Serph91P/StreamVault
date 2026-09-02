import os
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings

logger = logging.getLogger("streamvault")


def _index_html_path():
    for p in ("app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"):
        try:
            if os.path.exists(p):
                return p
        except OSError:
            continue
    return None


# ---------------------------------------------------------------------------
# Explicit SPA routes
# ---------------------------------------------------------------------------

spa_router = APIRouter()


@spa_router.get("/streamers")
@spa_router.get("/videos")
@spa_router.get("/subscriptions")
@spa_router.get("/add-streamer")
@spa_router.get("/settings")
@spa_router.get("/welcome")
@spa_router.get("/admin")
@spa_router.get("/streamer/{streamer_id}")
@spa_router.get("/streamer/{streamer_id}/stream/{stream_id}/watch")
async def serve_spa_routes():
    """Serve SPA for known frontend routes"""
    path = _index_html_path()
    if path:
        return FileResponse(path, media_type="text/html")
    return Response(content="SPA index.html not found", status_code=500)


# ---------------------------------------------------------------------------
# PWA file-serving routes (order must match legacy main module exactly)
# ---------------------------------------------------------------------------

pwa_router = APIRouter()


@pwa_router.get("/manifest.json")
async def serve_manifest():
    for path in [
        "app/frontend/public/manifest.json",
        "/app/app/frontend/public/manifest.json",
    ]:
        try:
            return FileResponse(
                path,
                media_type="application/manifest+json",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except (FileNotFoundError, PermissionError):
            continue
    return Response(status_code=404)


@pwa_router.get("/manifest.webmanifest")
async def serve_manifest_webmanifest():
    for path in [
        "app/frontend/public/manifest.webmanifest",
        "/app/app/frontend/public/manifest.webmanifest",
    ]:
        try:
            return FileResponse(
                path,
                media_type="application/manifest+json",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except (FileNotFoundError, PermissionError):
            continue
    return Response(status_code=404)


@pwa_router.get("/pwa/push-sw.js")
async def serve_push_sw_helper():
    """Serve the custom push handler for the service worker from the public dir"""
    for path in [
        "app/frontend/public/push-sw.js",
        "/app/app/frontend/public/push-sw.js",
    ]:
        try:
            return FileResponse(
                path,
                media_type="application/javascript",
                headers={"Cache-Control": "public, max-age=3600"},
            )
        except (FileNotFoundError, PermissionError):
            continue
    return Response(status_code=404)


@pwa_router.get("/registerSW.js")
async def register_service_worker():
    """Serve a compatibility no-op for stale cached pages.

    Runtime service worker registration is owned by VitePWA in frontend main.ts.
    Keeping this endpoint as a no-op avoids duplicate /sw.js registration paths.
    """
    return Response(
        content="// VitePWA owns service worker registration.\n",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@pwa_router.get("/sw.js")
async def service_worker():
    for path in ["app/frontend/dist/sw.js", "/app/app/frontend/dist/sw.js"]:
        try:
            # Read and append import for custom push handlers if not present
            try:
                with open(path, "r", encoding="utf-8") as f:
                    sw_code = f.read()
                # Only inject once and only if our public file exists
                inject_marker = "// streamvault-push-import"
                push_import = "\n".join(
                    [
                        "",
                        inject_marker,
                        "try {",
                        "  importScripts('/pwa/push-sw.js');",
                        "} catch (e) { /* ignore */ }",
                        inject_marker,
                        "",
                    ]
                )
                if inject_marker not in sw_code:
                    sw_code = sw_code + push_import
                return Response(
                    content=sw_code,
                    media_type="application/javascript",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Service-Worker-Allowed": "/",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    },
                )
            except (OSError, UnicodeDecodeError) as e:
                # Fallback to raw file serving if reading fails
                logger.debug(f"Could not read/modify service worker, serving raw: {e}")
                return FileResponse(
                    path,
                    media_type="application/javascript",
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Service-Worker-Allowed": "/",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    },
                )
        except (FileNotFoundError, PermissionError):
            continue
    return Response(status_code=404)


@pwa_router.get("/browserconfig.xml")
async def serve_browserconfig():
    for path in [
        "app/frontend/public/browserconfig.xml",
        "/app/app/frontend/public/browserconfig.xml",
    ]:
        try:
            return FileResponse(
                path,
                media_type="application/xml",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except (FileNotFoundError, PermissionError):
            continue
    return Response(status_code=404)


# /registerSW.js compatibility endpoint is defined above as a no-op.


@pwa_router.get("/workbox-{filename:path}")
async def serve_workbox_files(filename: str):
    """Serve Workbox-related files from the dist directory"""
    # SECURITY: Complete isolation - user input never reaches file operations
    # Step 1: Create whitelist of allowed workbox files (hardcoded, no user input)
    ALLOWED_WORKBOX_FILES = {
        # Common workbox filenames - add more as needed
        "66610c77.js": "workbox-66610c77.js",
        "74f2ef77.js": "workbox-74f2ef77.js",
        "core.js": "workbox-core.js",
        "sw.js": "workbox-sw.js",
        "runtime.js": "workbox-runtime.js",
        "strategies.js": "workbox-strategies.js",
        "precaching.js": "workbox-precaching.js",
        "routing.js": "workbox-routing.js",
        "window.js": "workbox-window.js",
    }

    # Step 2: Validate user input against whitelist only
    if not isinstance(filename, str) or len(filename) > 50:
        logger.warning(f"Invalid workbox filename format: {filename}")
        return Response(status_code=404)

    # Step 3: Check if requested file is in whitelist
    if filename not in ALLOWED_WORKBOX_FILES:
        logger.warning(f"Workbox file not in whitelist: {filename}")
        return Response(status_code=404)

    # Step 4: Get hardcoded filename from whitelist (no user input involved)
    safe_filename = ALLOWED_WORKBOX_FILES[filename]

    # Step 5: Define hardcoded safe paths (completely isolated from user input)
    SAFE_FILE_PATHS = [
        f"app/frontend/dist/{safe_filename}",
        f"/app/app/frontend/dist/{safe_filename}",
    ]

    # Step 6: Try each hardcoded path (user input never touches file operations)
    for hardcoded_path in SAFE_FILE_PATHS:
        try:
            # All file operations use hardcoded paths only
            real_path = os.path.realpath(hardcoded_path)

            # Verify path is within expected directories
            expected_dirs = [
                os.path.realpath("app/frontend/dist"),
                os.path.realpath("/app/app/frontend/dist"),
            ]

            path_is_safe = False
            for expected_dir in expected_dirs:
                try:
                    if os.path.commonpath([real_path, expected_dir]) == expected_dir:
                        path_is_safe = True
                        break
                except (ValueError, OSError):
                    continue

            # File operations on hardcoded paths only
            if path_is_safe and os.path.exists(real_path) and os.path.isfile(real_path):
                return FileResponse(
                    real_path,  # This comes from hardcoded paths, not user input
                    media_type="application/javascript",
                    headers={
                        "Cache-Control": "public, max-age=31536000",
                        "Access-Control-Allow-Origin": "*",
                    },
                )
        except Exception as e:
            logger.warning(
                f"Error checking hardcoded workbox path {hardcoded_path}: {e}"
            )
            continue

    # No valid hardcoded path found
    logger.warning(f"Workbox file not found in any safe location: {filename}")
    return Response(status_code=404)


@pwa_router.get("/favicon.ico")
async def serve_favicon():
    from app.utils.file_paths import get_file_paths

    for path in get_file_paths("favicon.ico"):
        try:
            return FileResponse(
                path,
                media_type="image/x-icon",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        except (FileNotFoundError, PermissionError):
            continue
    return Response(status_code=404)


@pwa_router.get("/favicon.png")
async def serve_favicon_png():
    from app.utils.file_paths import get_file_paths

    # Try specific favicon.png files, then fall back to ico
    for filename in ["favicon.png", "favicon-32x32.png", "favicon.ico"]:
        for path in get_file_paths(filename):
            try:
                media_type = (
                    "image/png" if filename.endswith(".png") else "image/x-icon"
                )
                return FileResponse(
                    path,
                    media_type=media_type,
                    headers={"Cache-Control": "public, max-age=86400"},
                )
            except (FileNotFoundError, PermissionError):
                continue
    return Response(status_code=404)


# PWA Icons - serve from public directory


@pwa_router.get("/{icon_file}")
async def serve_pwa_icons(icon_file: str):
    # SECURITY: Complete isolation of user input from file operations
    # Step 1: Strict allowlist validation - no user data flows to file operations
    pwa_files = {
        "android-icon-36x36.png",
        "android-icon-48x48.png",
        "android-icon-72x72.png",
        "android-icon-96x96.png",
        "android-icon-144x144.png",
        "android-icon-192x192.png",
        "apple-icon-57x57.png",
        "apple-icon-60x60.png",
        "apple-icon-72x72.png",
        "apple-icon-76x76.png",
        "apple-icon-114x114.png",
        "apple-icon-120x120.png",
        "apple-icon-144x144.png",
        "apple-icon-152x152.png",
        "apple-icon-180x180.png",
        "apple-icon-precomposed.png",
        "apple-icon.png",
        "favicon-16x16.png",
        "favicon-32x32.png",
        "favicon-96x96.png",
        "favicon.ico",
        "icon-512x512.png",
        "maskable-icon-192x192.png",
        "maskable-icon-512x512.png",
        "ms-icon-70x70.png",
        "ms-icon-144x144.png",
        "ms-icon-150x150.png",
        "ms-icon-310x310.png",
    }

    # Step 2: Early validation - reject if not in allowlist
    if icon_file not in pwa_files:
        return Response(status_code=404)

    # Step 3: Additional security checks
    if ".." in icon_file or "/" in icon_file or "\\" in icon_file:
        return Response(status_code=404)

    # Step 4: Create safe file mapping - completely disconnect user input from file paths
    # This mapping ensures no user data ever flows to file operations
    safe_file_mappings = {}
    base_directories = ["app/frontend/public", "/app/app/frontend/public"]

    for base_dir in base_directories:
        try:
            base_path = Path(base_dir)
            if not base_path.exists():
                continue

            # Pre-validate each allowed file independently
            for allowed_file in pwa_files:
                safe_path = base_path / allowed_file
                if safe_path.exists() and safe_path.is_file():
                    safe_file_mappings[allowed_file] = safe_path
        except Exception as e:
            logger.warning(f"Error scanning directory {base_dir}: {e}")
            continue

    # Step 5: Serve file using safe mapping (no user input in file operations)
    if icon_file in safe_file_mappings:
        safe_path = safe_file_mappings[icon_file]

        # Determine media type based on file extension
        media_type = "image/png"
        if icon_file.endswith(".ico"):
            media_type = "image/x-icon"
        elif icon_file.endswith(".svg"):
            media_type = "image/svg+xml"

        try:
            return FileResponse(
                str(safe_path),
                media_type=media_type,
                headers={"Cache-Control": "public, max-age=31536000"},  # 1 year
            )
        except Exception as e:
            logger.warning(f"Error serving icon file: {e}")

    return Response(status_code=404)


# Root route to serve index.html


@pwa_router.get("/")
async def serve_root():
    """Serve the main SPA index.html for the root route"""
    for path in ["app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"]:
        try:
            if os.path.exists(path):
                logger.info(f"Serving root index.html from: {path}")
                return FileResponse(path, media_type="text/html")
        except Exception as e:
            logger.warning(f"Could not serve root from {path}: {e}")
            continue

    logger.error("Could not find index.html for root route")
    return Response(
        content="Welcome to StreamVault - Frontend not available", status_code=500
    )


# ---------------------------------------------------------------------------
# SPA catch-all (must be the last route registered)
# ---------------------------------------------------------------------------

catchall_router = APIRouter()


@catchall_router.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Don't serve SPA for API paths, static files, or PWA files
    if (
        full_path.startswith("api/")
        or full_path.startswith("assets/")
        or full_path.startswith("data/")
        or full_path.startswith("video/")
        or full_path.startswith("ws")  # WebSocket
        or full_path.startswith("eventsub")  # EventSub
        or full_path.startswith("health")  # Health check
        or full_path.startswith("debug/")  # Debug endpoints
        or full_path
        in {
            "manifest.json",
            "manifest.webmanifest",
            "sw.js",
            "browserconfig.xml",
        }
        or full_path.endswith(
            (
                ".png",
                ".ico",
                ".svg",
                ".jpg",
                ".jpeg",
                ".gif",
                ".webp",
                ".js",
                ".css",
                ".map",
                ".xml",
            )
        )
    ):
        raise HTTPException(status_code=404)

    # For SPA routes like /streamers, /subscriptions, etc., serve index.html
    logger.info(f"SPA Fallback: Serving index.html for route '{full_path}'")

    # Try production path first, then fallback
    for path in ["app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"]:
        try:
            if os.path.exists(path):
                logger.debug(f"Successfully serving index.html from: {path}")
                return FileResponse(path, media_type="text/html")
        except Exception as e:
            logger.warning(f"Could not serve from {path}: {e}")
            continue

    logger.error(
        f"Could not find index.html for SPA route '{full_path}' in any expected location"
    )
    return Response(
        content=f"SPA index.html not found for route: {full_path}", status_code=500
    )


# ---------------------------------------------------------------------------
# Static file mounts (called from create_app – preserves original mount order)
# ---------------------------------------------------------------------------


def register_static_mounts(app) -> None:
    """Mount static directories in the exact legacy order."""
    # Static files for assets
    try:
        # Try the standard production path
        app.mount(
            "/assets", StaticFiles(directory="app/frontend/dist/assets"), name="assets"
        )
    except Exception as e:
        logger.warning(
            f"Could not mount static files from app/frontend/dist/assets: {e}"
        )
        # Fallback to a secondary path for development
        try:
            app.mount(
                "/assets",
                StaticFiles(directory="/app/app/frontend/dist/assets"),
                name="assets",
            )
            logger.info(
                "Successfully mounted static files from /app/app/frontend/dist/assets"
            )
        except Exception as e:
            logger.error(f"Failed to mount static assets: {e}")

    # Static files for PWA assets (icons, registerSW.js, etc.)
    try:
        # Try the standard production path for PWA files
        app.mount(
            "/pwa", StaticFiles(directory="app/frontend/dist"), name="pwa-primary"
        )
    except Exception as e:
        logger.warning(f"Could not mount PWA files from app/frontend/dist: {e}")
        # Fallback to a secondary path for development
        try:
            app.mount(
                "/pwa",
                StaticFiles(directory="/app/app/frontend/dist"),
                name="pwa-fallback",
            )
            logger.info("Successfully mounted PWA files from /app/app/frontend/dist")
        except Exception as e:
            logger.error(f"Failed to mount PWA assets: {e}")

    # Mount data directory - use local path if Docker path doesn't exist
    data_dir = "/app/data" if os.path.exists("/app/data") else "app/data"
    try:
        os.makedirs(data_dir, exist_ok=True)
        app.mount("/data", StaticFiles(directory=data_dir), name="data")
    except Exception as e:
        logger.warning(f"Could not mount /data directory: {e}")

    # Mount images directory for unified image service
    # Use settings for recordings directory (supports both Docker and local dev)
    recordings_dir = settings.RECORDING_DIRECTORY
    images_dir = Path(recordings_dir) / ".media"
    # Create the directory if it doesn't exist
    images_dir.mkdir(parents=True, exist_ok=True)
    # Create subdirectories
    (images_dir / "profiles").mkdir(parents=True, exist_ok=True)
    (images_dir / "categories").mkdir(parents=True, exist_ok=True)
    (images_dir / "artwork").mkdir(parents=True, exist_ok=True)
    # Mount the images directory under both /data/images and /api/media for compatibility
    app.mount("/data/images", StaticFiles(directory=str(images_dir)), name="images")
    app.mount("/api/media", StaticFiles(directory=str(images_dir)), name="media")
    # Backward-compatibility mount: many services store absolute-like paths starting with
    # "/recordings/.media/..." in the database. Expose the same path prefix from the API
    app.mount(
        "/recordings/.media",
        StaticFiles(directory=str(images_dir)),
        name="images-compat",
    )
