from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState
import logging

# Local imports
from app.config.settings import settings
from app.config.logging_config import setup_logging
from app.middleware.auth import AuthMiddleware
from app.middleware.error_handler import error_handler
from app.database import engine
import app.models as models
from app.services.websocket_manager import ConnectionManager

# Initialize application components
logger = setup_logging()
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

# Initialize WebSocket manager
manager = ConnectionManager()

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
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown complete")

# EventSub Callback Routes
@app.get("/eventsub/callback")
async def eventsub_verify():
    return Response(content="pyTwitchAPI eventsub", media_type="text/plain")

@app.post("/eventsub/callback")
async def eventsub_callback(request: Request):
    try:
        headers = request.headers
        body = await request.json()
        
        if headers.get('Twitch-Eventsub-Message-Type') == 'webhook_callback_verification':
            logger.info("Handling EventSub verification")
            return Response(content=body['challenge'], media_type='text/plain')

        if headers.get('Twitch-Eventsub-Message-Type') == 'notification':
            event_type = body['subscription']['type']
            handler = event_registry.handlers.get(event_type)
            if handler:
                await handler(body)
            
        return JSONResponse(status_code=200, content={"message": "Event processed successfully."})
    except Exception as e:
        logger.error(f"Error processing EventSub callback: {e}")
        raise

# Include routers
from app.routes import streamers
app.include_router(streamers.router)

# Static files
app.mount("/static", StaticFiles(directory="app/frontend/dist"), name="static")
app.mount("/", StaticFiles(directory="app/frontend/dist", html=True), name="frontend")

# Error handler
app.add_exception_handler(Exception, error_handler)