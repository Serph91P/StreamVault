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

# Static files for root-level items
@app.get("/favicon.ico")
async def favicon():
    # Try production path first, then fallback
    for path in ["app/frontend/dist/favicon.ico", "/app/app/frontend/dist/favicon.ico"]:
        try:
            return FileResponse(path)
        except:
            continue
    return Response(status_code=404)

@app.get("/icons/{file_path:path}")
async def serve_icons(file_path: str):
    import os
    base_dir = "app/frontend/dist/icons"
    fallback_dir = "/app/app/frontend/dist/icons"
    
    # Normalize and validate the path
    for base_path in [base_dir, fallback_dir]:
        full_path = os.path.normpath(os.path.join(base_path, file_path))
        if not full_path.startswith(os.path.abspath(base_path)):
            continue  # Skip invalid paths
        try:
            return FileResponse(full_path)
        except:
            continue
    return Response(status_code=404)

# Error handler
app.add_exception_handler(Exception, error_handler)

# Auth Middleware
app.add_middleware(AuthMiddleware)

# SPA catch-all route must be last
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return FileResponse("app/frontend/dist/index.html")

@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        "app/frontend/dist/sw.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache",
            "Service-Worker-Allowed": "/"
        }
    )
