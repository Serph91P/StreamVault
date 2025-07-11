from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.routing import APIRoute
from starlette.routing import WebSocketRoute
from app.routes import streamers, auth
from app.routes import settings as settings_router
from app.routes import twitch_auth
from app.routes import recording as recording_router
from app.routes import logging as logging_router
from app.routes import videos
import logging
import hmac
import hashlib
import json
import asyncio
import os
from pathlib import Path

from contextlib import asynccontextmanager

from app.events.handler_registry import EventHandlerRegistry
from app.config.logging_config import setup_logging
from app.database import engine
import app.models as models
from app.dependencies import websocket_manager, get_event_registry, get_auth_service
from app.middleware.error_handler import error_handler
from app.middleware.logging import logging_middleware
from app.config.settings import settings
from app.middleware.auth import AuthMiddleware
from app.routes import categories
from app.utils.security_enhanced import safe_file_access, safe_error_message

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application initialization...")
      # Run database migrations using the improved migration system
    try:
        # Check if migrations were already run by entrypoint.sh in development
        if os.getenv("ENVIRONMENT") == "development":
            logger.info("🔄 Development mode: Migrations handled by entrypoint.sh")
        else:
            logger.info("🚀 Production mode: Running database migrations...")
            
            # Use the improved MigrationService with safe migrations
            from app.services.migration_service import MigrationService
            
            # Run safe migrations first
            migration_success = MigrationService.run_safe_migrations()
            
            if migration_success:
                logger.info("✅ All database migrations completed successfully")
            else:
                logger.warning("⚠️ Some migrations failed, trying legacy system...")
                
                # Fallback to legacy system if needed (only in production)
                try:
                    from app.migrations_init import run_migrations
                    run_migrations()
                    logger.info("✅ Legacy migrations completed")
                except Exception as fallback_error:
                    logger.error(f"❌ Legacy migration system also failed: {fallback_error}")
                    logger.warning("⚠️ Application starting without full migrations - some features may not work")
            
    except Exception as e:
        logger.error(f"❌ Migration system failed: {e}")
        logger.warning("⚠️ Application starting without migrations - some features may not work")
    
    event_registry = await get_event_registry()
    
    # Start log cleanup service
    try:
        from app.services.logging_service import LoggingService
        logging_service = LoggingService()
        # Run cleanup once on startup and schedule daily cleanups
        asyncio.create_task(asyncio.to_thread(logging_service.cleanup_old_logs))
        asyncio.create_task(logging_service._schedule_cleanup(interval_hours=24))
        logger.info("Scheduled log cleanup service started (will run daily)")
    except Exception as e:
        logger.error(f"Failed to start log cleanup service: {e}")
    
    # Start the recordings cleanup service
    try:
        from app.services.cleanup_service import CleanupService
        
        async def scheduled_recording_cleanup():
            while True:
                try:
                    await CleanupService.run_scheduled_cleanup()
                except Exception as e:
                    logger.error(f"Error in scheduled recording cleanup: {e}", exc_info=True)
                
                # Run every 12 hours
                await asyncio.sleep(12 * 3600)
                
        # Run the cleanup task - first cleanup and then schedule regular cleanups
        logger.info("Starting scheduled recording cleanup service")
        asyncio.create_task(scheduled_recording_cleanup())
    except Exception as e:
        logger.error(f"Failed to start recording cleanup service: {e}")
    
    # Initialize EventSub subscriptions
    await event_registry.initialize_eventsub()
    logger.info("Application startup complete")
    
    yield
    
    # Cleanup with logging
    logger.info("Starting application shutdown...")
    event_registry = await get_event_registry()
    if event_registry.eventsub:
        await event_registry.eventsub.stop()
        logger.info("EventSub stopped")
    logger.info("Application shutdown complete")

# Initialize application components
logger = setup_logging()
models.Base.metadata.create_all(bind=engine)
app = FastAPI(lifespan=lifespan)
app.middleware("http")(logging_middleware)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info(f"New WebSocket connection from {websocket.client}")
    await websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {websocket.client}")
        await websocket_manager.disconnect(websocket)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "StreamVault"}

# EventSub Routes
@app.get("/eventsub")
@app.head("/eventsub")
async def eventsub_root():
    return Response(content="Twitch EventSub Endpoint", media_type="text/plain")

@app.post("/eventsub")
async def eventsub_callback(request: Request):
    try:
        # Read headers and body
        headers = request.headers
        body = await request.body()

        # Extract required headers
        message_id = headers.get("Twitch-Eventsub-Message-Id", "")
        timestamp = headers.get("Twitch-Eventsub-Message-Timestamp", "")
        received_signature = headers.get("Twitch-Eventsub-Message-Signature", "")
        message_type = headers.get("Twitch-Eventsub-Message-Type", "")

        # Debug logging
        logger.debug(f"Message ID: {message_id}")
        logger.debug(f"Timestamp: {timestamp}")
        logger.debug(f"Received signature: {received_signature}")
        logger.debug(f"Raw body: {body.decode()}")

        # Validate required headers
        if not all([message_id, timestamp, received_signature, message_type]):
            logger.error("Missing required headers for signature verification.")
            return Response(status_code=403)

        # Create message exactly as Twitch does
        hmac_message = message_id.encode() + timestamp.encode() + body        # Calculate HMAC using raw bytes
        calculated_signature = "sha256=" + hmac.new(
            settings.EVENTSUB_SECRET.encode(),
            hmac_message,
            hashlib.sha256
        ).hexdigest()

        # Debug HMAC calculation (without exposing sensitive data)
        logger.debug(f"HMAC message length: {len(hmac_message)}")
        logger.debug(f"Calculated signature: {calculated_signature}")
        logger.debug(f"Secret length: {len(settings.EVENTSUB_SECRET)}")

        if not hmac.compare_digest(received_signature, calculated_signature):
            logger.error(f"Signature mismatch. Got: {received_signature[:16]}..., Expected: {calculated_signature[:16]}...")
            return Response(status_code=403)

        # Process webhook message based on message_type
        if message_type == "webhook_callback_verification":
            try:
                body_json = json.loads(body)
                challenge = body_json.get("challenge")
                if challenge:
                    logger.info("Challenge request received and processed successfully.")
                    return Response(content=challenge, media_type=None, headers={"Content-Type": "text/plain"})
                else:
                    logger.error("Challenge request missing 'challenge' field.")
                    return Response(status_code=400)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON body: {e}")
                return Response(status_code=400)

        elif message_type == "notification":
            # Handle event notifications
            try:
                body_json = json.loads(body)
                event_registry = await get_event_registry()
                event_type = body_json.get("subscription", {}).get("type")
                event_data = body_json.get("event")

                logger.debug(f"Processing EventSub notification: {event_type}")
                logger.debug(f"Event data: {event_data}")

                handler = event_registry.handlers.get(event_type)
                if handler:
                    try:
                        await asyncio.wait_for(handler(event_data), timeout=5.0)
                        logger.info(f"Event {event_type} handled successfully.")
                        return Response(status_code=204)
                    except asyncio.TimeoutError:
                        logger.error(f"Handler for {event_type} timed out.")
                        return Response(status_code=500)
                    except Exception as e:
                        logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)
                        return Response(status_code=500)
                else:
                    logger.warning(f"No handler found for event type: {event_type}.")
                    return Response(status_code=400)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON body: {e}")
                return Response(status_code=400)

        elif message_type == "revocation":
            # Handle subscription revocation
            body_json = json.loads(body)
            subscription_id = body_json.get("subscription", {}).get("id", "unknown")
            reason = body_json.get("subscription", {}).get("status", "unknown reason")
            logger.warning(f"Subscription {subscription_id} revoked by Twitch. Reason: {reason}")
            return Response(status_code=204)

        else:
            logger.warning(f"Unsupported message type: {message_type}")
            return Response(status_code=400)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return Response(status_code=500)

# API routes first
app.include_router(streamers.router)
app.include_router(auth.router, prefix="/auth")
app.include_router(settings_router.router)
app.include_router(twitch_auth.router)
app.include_router(recording_router.router)
app.include_router(logging_router.router)
app.include_router(categories.router)
app.include_router(videos.router)  # Router already has /api prefix

# Push notification routes
from app.routes import push as push_router
app.include_router(push_router.router)

# Admin routes
from app.routes import admin as admin_router
app.include_router(admin_router.router)

# Explicit SPA routes - these must come after API routes but before static files
@app.get("/streamers")
@app.get("/videos") 
@app.get("/subscriptions")
@app.get("/add-streamer")
@app.get("/settings")
@app.get("/welcome")
@app.get("/admin")
@app.get("/auth/setup")
@app.get("/auth/login")
@app.get("/streamer/{streamer_id}")
@app.get("/streamer/{streamer_id}/stream/{stream_id}/watch")
async def serve_spa_routes():
    """Serve SPA for known frontend routes"""
    for path in ["app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"]:
        try:
            import os
            if os.path.exists(path):
                return FileResponse(path, media_type="text/html")
        except Exception as e:
            continue
    
    return Response(content="SPA index.html not found", status_code=500)

# Static files for assets
try:
    # Try the standard production path
    app.mount("/assets", StaticFiles(directory="app/frontend/dist/assets"), name="assets")
except Exception as e:
    logger.warning(f"Could not mount static files from app/frontend/dist/assets: {e}")
    # Fallback to a secondary path for development
    try:
        app.mount("/assets", StaticFiles(directory="/app/app/frontend/dist/assets"), name="assets")
        logger.info("Successfully mounted static files from /app/app/frontend/dist/assets")
    except Exception as e:
        logger.error(f"Failed to mount static assets: {e}")

app.mount("/data", StaticFiles(directory="/app/data"), name="data")

# PWA Files serving - these must be at root level
@app.get("/manifest.json")
async def serve_manifest():
    for path in ["app/frontend/public/manifest.json", "/app/app/frontend/public/manifest.json"]:
        try:
            return FileResponse(
                path,
                media_type="application/manifest+json",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/manifest.webmanifest")
async def serve_manifest_webmanifest():
    for path in ["app/frontend/public/manifest.webmanifest", "/app/app/frontend/public/manifest.webmanifest"]:
        try:
            return FileResponse(
                path,
                media_type="application/manifest+json",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/sw.js")
async def service_worker():
    for path in ["app/frontend/public/sw.js", "/app/app/frontend/public/sw.js"]:
        try:
            return FileResponse(
                path,
                media_type="application/javascript",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Service-Worker-Allowed": "/",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/browserconfig.xml")
async def serve_browserconfig():
    for path in ["app/frontend/public/browserconfig.xml", "/app/app/frontend/public/browserconfig.xml"]:
        try:
            return FileResponse(
                path,
                media_type="application/xml",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/pwa-test.html")
async def serve_pwa_test():
    for path in ["app/frontend/public/pwa-test.html", "/app/app/frontend/public/pwa-test.html"]:
        try:
            return FileResponse(path, media_type="text/html")
        except:
            continue
    return Response(status_code=404)

@app.get("/pwa-helper.js")
async def serve_pwa_helper():
    for path in ["app/frontend/public/pwa-helper.js", "/app/app/frontend/public/pwa-helper.js"]:
        try:
            return FileResponse(path, media_type="application/javascript")
        except:
            continue
    return Response(status_code=404)

# PWA Icons - serve from public directory
@app.get("/{icon_file}")
async def serve_pwa_icons(icon_file: str):
    # SECURITY: Complete isolation of user input from file operations
    # Step 1: Strict allowlist validation - no user data flows to file operations
    pwa_files = {
        'android-icon-36x36.png', 'android-icon-48x48.png', 'android-icon-72x72.png',
        'android-icon-96x96.png', 'android-icon-144x144.png', 'android-icon-192x192.png',
        'apple-icon-57x57.png', 'apple-icon-60x60.png', 'apple-icon-72x72.png',
        'apple-icon-76x76.png', 'apple-icon-114x114.png', 'apple-icon-120x120.png',
        'apple-icon-144x144.png', 'apple-icon-152x152.png', 'apple-icon-180x180.png',
        'apple-icon-precomposed.png', 'apple-icon.png',
        'favicon-16x16.png', 'favicon-32x32.png', 'favicon-96x96.png', 'favicon.ico',
        'icon-512x512.png', 'maskable-icon-192x192.png', 'maskable-icon-512x512.png',
        'ms-icon-70x70.png', 'ms-icon-144x144.png', 'ms-icon-150x150.png', 'ms-icon-310x310.png'
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
                    break  # Found in this directory, no need to check others
        except Exception as e:
            logger.warning(f"Error scanning directory {base_dir}: {e}")
            continue
    
    # Step 5: Serve file using safe mapping (no user input in file operations)
    if icon_file in safe_file_mappings:
        safe_path = safe_file_mappings[icon_file]
        
        # Determine media type based on file extension
        media_type = "image/png"
        if icon_file.endswith('.ico'):
            media_type = "image/x-icon"
        elif icon_file.endswith('.svg'):
            media_type = "image/svg+xml"
        
        try:
            return FileResponse(
                str(safe_path),
                media_type=media_type,
                headers={"Cache-Control": "public, max-age=31536000"}  # 1 year
            )
        except Exception as e:
            logger.warning(f"Error serving icon file: {e}")
    
    return Response(status_code=404)

# Root route to serve index.html
@app.get("/")
async def serve_root():
    """Serve the main SPA index.html for the root route"""
    for path in ["app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"]:
        try:
            import os
            if os.path.exists(path):
                logger.info(f"Serving root index.html from: {path}")
                return FileResponse(path, media_type="text/html")
        except Exception as e:
            logger.warning(f"Could not serve root from {path}: {e}")
            continue
    
    logger.error("Could not find index.html for root route")
    return Response(content="Welcome to StreamVault - Frontend not available", status_code=500)

# Error handler
app.add_exception_handler(Exception, error_handler)

# Auth Middleware
app.add_middleware(AuthMiddleware)

# SPA catch-all route must be last - only serve for non-API paths
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Don't serve SPA for API paths, static files, or PWA files
    if (full_path.startswith("api/") or 
        full_path.startswith("assets/") or 
        full_path.startswith("data/") or
        full_path.startswith("video/") or
        full_path.startswith("ws") or  # WebSocket
        full_path.startswith("eventsub") or  # EventSub
        full_path.startswith("health") or  # Health check
        full_path.startswith("debug/") or  # Debug endpoints
        full_path in {"manifest.json", "manifest.webmanifest", "sw.js", "browserconfig.xml", "pwa-test.html", "pwa-helper.js"} or
        full_path.endswith((".png", ".ico", ".svg", ".jpg", ".jpeg", ".gif", ".webp", ".js", ".css", ".map", ".xml"))):
        raise HTTPException(status_code=404)
    
    # For SPA routes like /streamers, /subscriptions, etc., serve index.html
    logger.info(f"SPA Fallback: Serving index.html for route '{full_path}'")
    
    # Try production path first, then fallback
    for path in ["app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"]:
        try:
            import os
            if os.path.exists(path):
                logger.debug(f"Successfully serving index.html from: {path}")
                return FileResponse(path, media_type="text/html")
        except Exception as e:
            logger.warning(f"Could not serve from {path}: {e}")
            continue
    
    logger.error(f"Could not find index.html for SPA route '{full_path}' in any expected location")
    return Response(content=f"SPA index.html not found for route: {full_path}", status_code=500)
