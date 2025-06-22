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

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application initialization...")
    
    # Run database migrations
    from app.migrations_init import run_migrations
    run_migrations()
    
    # Auto-run push subscription table creation if needed
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        
        # Check if push_subscriptions table exists
        if 'push_subscriptions' not in inspector.get_table_names():
            logger.info("🔄 Creating push_subscriptions table...")
            import subprocess
            import os
            
            migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "20250620_add_push_subscriptions.py")
            result = subprocess.run(["python", migration_path], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ Push subscription table created successfully")
            else:
                logger.warning(f"⚠️ Push subscription migration failed: {result.stderr}")
        else:
            logger.debug("✅ Push subscription table already exists")
        
        # Check if system_config table exists
        if 'system_config' not in inspector.get_table_names():
            logger.info("🔄 Creating system_config table...")
            
            migration_path = os.path.join(os.path.dirname(__file__), "..", "migrations", "20250620_add_system_config.py")
            result = subprocess.run(["python", migration_path], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ System config table created successfully")
            else:
                logger.warning(f"⚠️ System config migration failed: {result.stderr}")
        else:
            logger.debug("✅ System config table already exists")
            
    except Exception as e:
        logger.warning(f"⚠️ Push subscription table check failed: {e}")
        logger.info("💡 You can manually run: python migrations/20250620_add_push_subscriptions.py")
    
    event_registry = await get_event_registry()
    
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
        hmac_message = message_id.encode() + timestamp.encode() + body

        # Calculate HMAC using raw bytes
        calculated_signature = "sha256=" + hmac.new(
            settings.EVENTSUB_SECRET.encode(),
            hmac_message,
            hashlib.sha256
        ).hexdigest()

        # Debug HMAC calculation
        logger.debug(f"HMAC message: {hmac_message}")
        logger.debug(f"Calculated signature: {calculated_signature}")
        logger.debug(f"Secret used: {settings.EVENTSUB_SECRET}")

        if not hmac.compare_digest(received_signature, calculated_signature):
            logger.error(f"Signature mismatch. Got: {received_signature}, Expected: {calculated_signature}")
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
app.include_router(videos.router)

# Push notification routes
from app.routes import push as push_router
app.include_router(push_router.router)

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
    # Only serve known PWA icon files
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
    
    if icon_file in pwa_files:
        # Determine media type based on file extension
        media_type = "image/png"
        if icon_file.endswith('.ico'):
            media_type = "image/x-icon"
        elif icon_file.endswith('.svg'):
            media_type = "image/svg+xml"
            
        for base_path in ["app/frontend/public", "/app/app/frontend/public"]:
            try:
                return FileResponse(
                    f"{base_path}/{icon_file}",
                    media_type=media_type,
                    headers={"Cache-Control": "public, max-age=31536000"}  # 1 year
                )
            except:
                continue
    return Response(status_code=404)

# Custom video serving route to handle URL encoding issues
@app.get("/video/{file_path:path}")
async def serve_video(file_path: str):
    """Serve video files with proper URL decoding"""
    import urllib.parse
    from pathlib import Path
    
    try:
        # URL decode the file path
        decoded_path = urllib.parse.unquote(file_path)
        
        # Construct full path
        full_path = Path("/app/data") / decoded_path
        
        # Security check - ensure path is within /app/data
        if not str(full_path.resolve()).startswith("/app/data"):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Check if file exists
        if not full_path.exists():
            logger.error(f"Video file not found: {full_path}")
            # Try to find the file with different extensions
            possible_files = []
            parent_dir = full_path.parent
            base_name = full_path.stem
            
            if parent_dir.exists():
                for ext in ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.ts']:
                    candidate = parent_dir / f"{base_name}{ext}"
                    if candidate.exists():
                        possible_files.append(candidate)
            
            if possible_files:
                full_path = possible_files[0]
                logger.info(f"Found alternative video file: {full_path}")
            else:
                raise HTTPException(status_code=404, detail="Video file not found")
        
        # Serve the file
        return FileResponse(
            full_path,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except Exception as e:
        logger.error(f"Error serving video {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error serving video file")

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
        full_path in {"manifest.json", "manifest.webmanifest", "sw.js", "browserconfig.xml", "pwa-test.html", "pwa-helper.js"} or
        full_path.endswith((".png", ".ico", ".svg", ".jpg", ".jpeg", ".gif", ".webp", ".js", ".css", ".map"))):
        raise HTTPException(status_code=404)
    
    # Try production path first, then fallback
    for path in ["app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"]:
        try:
            return FileResponse(path, media_type="text/html")
        except:
            continue
    return Response(status_code=404)
