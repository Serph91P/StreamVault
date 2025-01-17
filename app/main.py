from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from app.routes import streamers, auth
import logging
import hmac
import hashlib

from app.config.logging_config import setup_logging
from app.database import engine
import app.models as models
from app.dependencies import websocket_manager, get_event_registry, get_twitch, get_auth_service
from app.middleware.error_handler import error_handler
from app.middleware.logging import logging_middleware
from app.config.settings import settings
from app.middleware.auth import AuthMiddleware
from app.test_eventsub import router as test_router

# Initialize application components
logger = setup_logging()
models.Base.metadata.create_all(bind=engine)
app = FastAPI()
app.include_router(test_router)
app.middleware("http")(logging_middleware)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

# Application Lifecycle Events
@app.on_event("startup")
async def startup_event():
    await get_twitch()
    await get_event_registry()
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    event_registry = await get_event_registry()
    logger.info("Application shutdown complete")

# EventSub Routes
@app.get("/eventsub/callback")
@app.head("/eventsub/callback")
async def eventsub_root():
    return Response(content="Twitch EventSub Endpoint", media_type="text/plain")

@app.post("/eventsub/callback")
async def eventsub_callback(request: Request):
    try:
        # Read the headers and body
        headers = request.headers
        body = await request.body()

        # Extract the Twitch Message Type
        message_type = headers.get("Twitch-Eventsub-Message-Type")
        logger.debug(f"Received EventSub request: type={message_type}, headers={headers}, body={body}")

        # Handle challenge requests
        if message_type == "webhook_callback_verification":
            challenge_data = await request.json()
            challenge = challenge_data.get("challenge")
            if challenge:
                logger.info("Challenge request received and processed successfully.")
                return Response(content=challenge, media_type="text/plain", status_code=200)
            else:
                logger.error("Challenge request missing 'challenge' field.")
                return JSONResponse(status_code=400, content={"error": "Missing challenge field"})

        # Validate signature for notifications
        message_id = headers.get("Twitch-Eventsub-Message-Id", "")
        timestamp = headers.get("Twitch-Eventsub-Message-Timestamp", "")
        signature = headers.get("Twitch-Eventsub-Message-Signature", "")

        if not all([message_id, timestamp, signature]):
            logger.error("Missing required headers for signature verification")
            return JSONResponse(status_code=403, content={"error": "Missing required headers"})

        # Compute and verify the HMAC signature
        hmac_message = message_id + timestamp + body.decode()
        expected_signature = "sha256=" + hmac.new(
            settings.WEBHOOK_SECRET.encode("utf-8"),
            hmac_message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if signature != expected_signature:
            logger.error("Invalid webhook signature")
            return JSONResponse(status_code=403, content={"error": "Invalid signature"})

        # Process the notification
        body_json = await request.json()
        logger.info(f"Notification received: {body_json}")

        # Initialize the event registry
        event_registry = await get_event_registry()

        if message_type == "notification":
            event_type = body_json.get("subscription", {}).get("type")
            event_data = body_json.get("event")

            if not event_type or not event_data:
                logger.error("Missing event type or data in notification")
                return JSONResponse(status_code=400, content={"error": "Missing event type or data"})

            handler = event_registry.handlers.get(event_type)
            if handler:
                logger.info(f"Handling event type: {event_type}")
                try:
                    await handler(event_data)
                    return JSONResponse(content={"message": "Event processed successfully"}, status_code=200)
                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)
                    return JSONResponse(status_code=500, content={"error": f"Error processing event: {str(e)}"})
            else:
                logger.warning(f"No handler found for event type: {event_type}")
                return JSONResponse(status_code=400, content={"error": f"No handler for event type: {event_type}"})

        # Unsupported message type
        logger.warning(f"Unsupported message type: {message_type}")
        return JSONResponse(status_code=400, content={"error": f"Unsupported message type: {message_type}"})

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Internal server error: {str(e)}"})
    
# API routes first
app.include_router(streamers.router)
app.include_router(auth.router, prefix="/auth")

# Static files for assets
app.mount("/assets", StaticFiles(directory="app/frontend/dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return FileResponse("app/frontend/dist/index.html")

# Error handler
app.add_exception_handler(Exception, error_handler)

# Auth Middleware
app.add_middleware(AuthMiddleware)
