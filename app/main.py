from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import logging

from app.config.logging_config import setup_logging
from app.database import engine
import app.models as models
from app.dependencies import manager, get_event_registry, get_twitch
from app.middleware.error_handler import error_handler

# Initialize application components
logger = setup_logging()
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Application Lifecycle Events
@app.on_event("startup")
async def startup_event():
    twitch_client = await get_twitch()
    event_registry = await get_event_registry()
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    event_registry = await get_event_registry()
    await event_registry.shutdown()
    logger.info("Application shutdown complete")

# EventSub Callback Routes
# EventSub Verification Endpoint
@app.get("/eventsub/callback")
async def eventsub_verify():
    return Response(content="pyTwitchAPI eventsub", media_type="text/plain")

# EventSub Callback Handler
@app.post("/eventsub/callback")
async def eventsub_callback(request: Request):
    try:
        # Log all incoming requests for debugging
        headers = request.headers
        body = await request.json()
        logger.debug(f"Received EventSub request: headers={headers}, body={body}")

        # Initialize event registry
        event_registry = await get_event_registry()

        # Handle webhook verification
        message_type = headers.get("Twitch-Eventsub-Message-Type")
        if message_type == "webhook_callback_verification":
            logger.info("Handling EventSub verification")
            challenge = body.get("challenge")
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
            event_type = body.get("subscription", {}).get("type")
            event_data = body.get("event")

            if not event_type:
                logger.error("Missing event type in notification")
                return JSONResponse(
                    status_code=400, 
                    content={"error": "Missing event type in notification"}
                )

            if not event_data:
                logger.error("Missing event data in notification")
                return JSONResponse(
                    status_code=400, 
                    content={"error": "Missing event data in notification"}
                )

            # Look for a handler for the event type
            handler = event_registry.handlers.get(event_type)
            if handler:
                logger.info(f"Handling event type: {event_type} with data: {event_data}")
                try:
                    await handler(event_data)
                except Exception as e:
                    logger.error(f"Error processing event type {event_type}: {e}", exc_info=True)
                    return JSONResponse(
                        status_code=500, 
                        content={"error": f"Error processing event type {event_type}: {e}"}
                    )
            else:
                logger.warning(f"No handler found for event type: {event_type}")
                return JSONResponse(
                    status_code=400, 
                    content={"error": f"No handler found for event type: {event_type}"}
                )

            return JSONResponse(
                status_code=200, 
                content={"message": "Event processed successfully."}
            )

        # Log and respond to unsupported message types
        logger.warning(f"Unsupported message type: {message_type}")
        return JSONResponse(
            status_code=400, 
            content={"error": f"Unsupported message type: {message_type}"}
        )
    
    except Exception as e:
        logger.error(f"Error processing EventSub callback: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, 
            content={"error": f"Internal server error: {e}"}
        )

# Include routers
from app.routes import streamers
app.include_router(streamers.router)

# Static files
app.mount("/static", StaticFiles(directory="app/frontend/dist"), name="static")
app.mount("/", StaticFiles(directory="app/frontend/dist", html=True), name="frontend")

# Error handler
app.add_exception_handler(Exception, error_handler)
