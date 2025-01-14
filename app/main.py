from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from app.routes import streamers, auth
import logging
import hmac
import hashlib

from app.config.logging_config import setup_logging
from app.database import engine
import app.models as models
from app.dependencies import websocket_manager, get_event_registry, get_twitch
from app.middleware.error_handler import error_handler
from app.config.settings import settings

# Initialize application components
logger = setup_logging()
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

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
        # Verify the webhook signature
        body = await request.body()
        headers = request.headers
        
        message_id = headers.get('Twitch-Eventsub-Message-Id')
        timestamp = headers.get('Twitch-Eventsub-Message-Timestamp')
        signature = headers.get('Twitch-Eventsub-Message-Signature')
        
        # Verify webhook signature
        hmac_message = message_id + timestamp + body.decode()
        expected_signature = 'sha256=' + hmac.new(
            settings.WEBHOOK_SECRET.encode('utf-8'),
            hmac_message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected_signature:
            logger.error("Invalid webhook signature")
            return JSONResponse(status_code=403, content={"error": "Invalid signature"})

        # Process the webhook payload
        body_json = await request.json()
        logger.debug(f"Received EventSub request: headers={headers}, body={body_json}")

        # Initialize event registry
        event_registry = await get_event_registry()

        # Handle webhook verification
        message_type = headers.get("Twitch-Eventsub-Message-Type")
        if message_type == "webhook_callback_verification":
            logger.info("Handling EventSub verification")
            challenge = body_json.get("challenge")
            if not challenge:
                logger.error("Missing challenge in webhook verification")
                return JSONResponse(
                    status_code=400, 
                    content={"error": "Missing challenge in webhook verification"}
                )
            logger.info(f"Webhook verified with challenge: {challenge}")
            return Response(content=challenge, media_type="text/plain")

        # Handle notifications
        if message_type == "notification":
            event_type = body_json.get("subscription", {}).get("type")
            event_data = body_json.get("event")

            if not event_type or not event_data:
                logger.error("Missing event type or data in notification")
                return JSONResponse(
                    status_code=400, 
                    content={"error": "Missing event type or data"}
                )

            handler = event_registry.handlers.get(event_type)
            if handler:
                logger.info(f"Handling event type: {event_type}")
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)
                    return JSONResponse(
                        status_code=500, 
                        content={"error": f"Error processing event: {str(e)}"}
                    )
            else:
                logger.warning(f"No handler found for event type: {event_type}")
                return JSONResponse(
                    status_code=400, 
                    content={"error": f"No handler for event type: {event_type}"}
                )

            return JSONResponse(content={"message": "Event processed successfully"})

        return JSONResponse(
            status_code=400, 
            content={"error": f"Unsupported message type: {message_type}"}
        )
    
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, 
            content={"error": f"Internal server error: {str(e)}"}
        )
    
# Include routers
from app.routes import streamers, auth
app.include_router(streamers.router)
app.include_router(auth.router)

# Add this after including the router
for route in app.routes:
    if hasattr(route, "methods"):
        print(f"Registered HTTP route: {route.path} [{route.methods}]")
    else:
        print(f"Registered WebSocket route: {route.path}")

# Static files
app.mount("/static", StaticFiles(directory="app/frontend/dist"), name="static")
app.mount("/", StaticFiles(directory="app/frontend/dist", html=True), name="frontend")

# Error handler
app.add_exception_handler(Exception, error_handler)
