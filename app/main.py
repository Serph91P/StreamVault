from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from starlette.websockets import WebSocketState
import logging
import os
from datetime import datetime

# Local imports
from app.config.settings import settings
from app.config.logging_config import setup_logging
from app.middleware.auth import AuthMiddleware
from app.middleware.error_handler import error_handler
from app.database import SessionLocal, engine
from app.services.streamer_service import StreamerService
from app.services.websocket_manager import ConnectionManager
from app.events.handler_registry import EventHandlerRegistry
import app.models as models
from app.routes import streamers

# Initialize application components
logger = setup_logging()
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

# Initialize core services
connection_manager = ConnectionManager()
twitch = None
event_sub = None
event_registry = EventHandlerRegistry(connection_manager, twitch)

# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_streamer_service(db: Session = Depends(get_db)) -> StreamerService:
    return StreamerService(db, twitch)

# Twitch API initialization
async def initialize_twitch():
    global twitch
    try:
        twitch = Twitch(settings.TWITCH_APP_ID, settings.TWITCH_APP_SECRET)
        await twitch.authenticate_app([])
        logger.info("Twitch API initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twitch API: {e}")
        raise

async def initialize_eventsub():
    global event_sub, twitch
    try:
        event_sub = EventSubWebhook(
            settings.WEBHOOK_URL,
            8080,
            twitch
        )
        await event_sub.unsubscribe_all()
        event_sub.start()
        logger.info("EventSub initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize EventSub: {e}")
        raise

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await connection_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)

# Application Lifecycle Events
@app.on_event("startup")
async def startup_event():
    await initialize_twitch()
    await event_registry.initialize_eventsub()
    event_registry.register_handlers()
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    await event_registry.shutdown()
    logger.info("Application shutdown complete")
# EventSub Callback Routes
@app.get("/eventsub/callback")
async def eventsub_verify():
    return Response(content="pyTwitchAPI eventsub", media_type="text/plain")

@app.post("/eventsub/callback")
async def eventsub_callback(request: Request, db: Session = Depends(get_db)):
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
app.include_router(streamers.router)

# Static files
app.mount("/static", StaticFiles(directory="app/frontend/dist"), name="static")
app.mount("/", StaticFiles(directory="app/frontend/dist", html=True), name="frontend")

# Error handler
app.add_exception_handler(Exception, error_handler)
