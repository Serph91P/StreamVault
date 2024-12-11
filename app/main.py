# Standard library imports
import os
import asyncio
import logging
from datetime import datetime

# Third-party imports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, BackgroundTasks, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook
from twitchAPI.helper import first
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

# Local imports
from app.config.logging_config import setup_logging
from app.middleware.auth import AuthMiddleware
from app.middleware.error_handler import error_handler
import app.models as models
from app.database import SessionLocal, engine

# Event Handlers
async def on_stream_online(data):
    streamer_id = data.event.broadcaster_user_id
    with SessionLocal() as db:
        streamer = db.query(models.Streamer).filter(models.Streamer.id == streamer_id).first()
        if streamer:
            new_stream = models.Stream(streamer_id=streamer_id, event_type='stream.online')
            db.add(new_stream)
            db.commit()
            await manager.send_notification(f"{streamer.username} is now **online**!")

async def on_stream_offline(data):
    streamer_id = data.event.broadcaster_user_id
    with SessionLocal() as db:
        streamer = db.query(models.Streamer).filter(models.Streamer.id == streamer_id).first()
        if streamer:
            new_stream = models.Stream(streamer_id=streamer_id, event_type='stream.offline')
            db.add(new_stream)
            db.commit()
            await manager.send_notification(f"{streamer.username} is now **offline**!")

# Initialize application components
logger = setup_logging()
models.Base.metadata.create_all(bind=engine)
app = FastAPI()

# Database session dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected: {websocket.client}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected: {websocket.client}")

    async def send_notification(self, message: str):
        for connection in self.active_connections:
            if connection.client_state != WebSocketState.DISCONNECTED:
                try:
                    await connection.send_text(message)
                except WebSocketDisconnect:
                    self.disconnect(connection)
                    logger.error(f"Failed to send message to {connection.client}")

manager = ConnectionManager()

# Twitch API Configuration
APP_ID = os.getenv('TWITCH_APP_ID')
APP_SECRET = os.getenv('TWITCH_APP_SECRET')
BASE_URL = os.getenv('BASE_URL')
WEBHOOK_URL = f"{BASE_URL}/eventsub"

if not all([APP_ID, APP_SECRET, BASE_URL]):
    raise ValueError("Missing required environment variables")

# Twitch API and EventSub initialization
twitch = None
event_sub = None

async def initialize_twitch():
    global twitch
    try:
        twitch = Twitch(APP_ID, APP_SECRET)
        await twitch.authenticate_app([])
        logger.info("Twitch API initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twitch API: {e}")
        raise

async def initialize_eventsub():
    global event_sub, twitch
    try:
        event_sub = EventSubWebhook(
            WEBHOOK_URL,
            8080,
            twitch
        )
        await event_sub.unsubscribe_all()
        event_sub.start()
        logger.info("EventSub initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize EventSub: {e}")
        raise

# Pydantic Models
class StreamerBase(BaseModel):
    username: str

class StreamerCreate(StreamerBase):
    pass

class Streamer(StreamerBase):
    id: int
    class Config:
        from_attributes = True

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
    await initialize_twitch()
    await initialize_eventsub()
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    try:
        if event_sub:
            await event_sub.stop()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        raise

# API Routes
@app.get("/api/streamers")
async def get_streamers(db: Session = Depends(get_db)):
    streamers = db.query(models.Streamer).all()
    streamer_statuses = []
    
    for streamer in streamers:
        latest_event = db.query(models.Stream)\
            .filter(models.Stream.streamer_id == streamer.id)\
            .order_by(models.Stream.timestamp.desc())\
            .first()
            
        streamer_statuses.append({
            "id": streamer.id,
            "username": streamer.username,
            "is_live": latest_event.event_type == 'stream.online' if latest_event else False,
            "last_updated": latest_event.timestamp if latest_event else None
        })
    
    return streamer_statuses
async def add_streamer(username: str = Form(...), background_tasks: BackgroundTasks = BackgroundTasks(), db: Session = Depends(get_db)):
    try:
        existing_streamer = db.query(models.Streamer).filter(models.Streamer.username == username).first()
        if existing_streamer:
            logger.warning(f"Attempted to add existing streamer: {username}")
            return JSONResponse(status_code=400, content={"message": f"Streamer {username} is already subscribed."})

        background_tasks.add_task(subscribe_to_streamer, username, db)
        logger.info(f"Added subscription task for streamer: {username}")
        
        return JSONResponse(
            status_code=202, 
            content={
                "message": f"Processing subscription for {username}",
                "status": "processing"
            }
        )
    except Exception as e:
        logger.error(f"Error adding streamer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/streamers/{streamer_id}")
async def delete_streamer(streamer_id: int, db: Session = Depends(get_db)):
    try:
        # Unsubscribe from EventSub
        await event_sub.delete_all_subscriptions_of_type('stream.online', streamer_id)
        await event_sub.delete_all_subscriptions_of_type('stream.offline', streamer_id)
        await event_sub.delete_all_subscriptions_of_type('channel.update', streamer_id)
        await event_sub.delete_all_subscriptions_of_type('channel.update.v2', streamer_id)
        
        # Delete from database
        streamer = db.query(models.Streamer).filter(models.Streamer.id == streamer_id).first()
        if streamer:
            db.delete(streamer)
            db.commit()
            await manager.send_notification(f"Removed streamer {streamer.username}")
            return {"message": "Streamer deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting streamer {streamer_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete streamer")

@app.get("/eventsub/callback")
async def eventsub_verify():
    return Response(content="pyTwitchAPI eventsub", media_type="text/plain")

async def subscribe_to_streamer(username: str, db: Session):
        try:
            user_info = await twitch.get_users(logins=[username])
            if not user_info['data']:
                await manager.send_notification(f"Streamer {username} not found")
                return

            user_data = user_info['data'][0]
            user_id = user_data['id']
            display_name = user_data['display_name']
            logger.info(f"Found streamer {display_name} with ID {user_id}")

            # Subscribe to all events with individual error handling
            subscription_errors = []
            try:
                await event_sub.listen_stream_online(user_id)
            except Exception as e:
                subscription_errors.append(f"Stream online subscription failed: {str(e)}")
            
            try:
                await event_sub.listen_stream_offline(user_id)
            except Exception as e:
                subscription_errors.append(f"Stream offline subscription failed: {str(e)}")
            
            try:
                await event_sub.listen_channel_update(user_id)
            except Exception as e:
                subscription_errors.append(f"Channel update subscription failed: {str(e)}")
            
            try:
                await event_sub.listen_channel_update_v2(user_id)
            except Exception as e:
                subscription_errors.append(f"Channel update v2 subscription failed: {str(e)}")

            if subscription_errors:
                error_message = "\n".join(subscription_errors)
                logger.error(f"Subscription errors for {display_name}:\n{error_message}")
                await manager.send_notification(f"Failed to set up all subscriptions for {display_name}. Errors: {error_message}")
                return

            # Only add to database if all subscriptions succeed
            new_streamer = models.Streamer(id=user_id, username=display_name)
            db.add(new_streamer)
            db.commit()
            logger.info(f"Added streamer {display_name} to database")
        
            await manager.send_notification(f"Successfully subscribed to {display_name}")

        except Exception as e:
            logger.error(f"Failed to subscribe to {username}: {str(e)}")
            await manager.send_notification(f"Failed to add {username}")

@app.post("/eventsub/callback")
async def eventsub_callback(request: Request, db: Session = Depends(get_db)):
    try:
        headers = request.headers
        body = await request.json()
        
        if headers.get('Twitch-Eventsub-Message-Type') == 'webhook_callback_verification':
            logger.info("Handling EventSub verification")
            return Response(content=body['challenge'], media_type='text/plain')

        if headers.get('Twitch-Eventsub-Message-Type') == 'notification':
            logger.info("Processing EventSub notification")
            event = body['event']
            streamer_id = event['broadcaster_user_id']
            streamer = db.query(models.Streamer).filter(models.Streamer.id == streamer_id).first()
            
            if not streamer:
                return JSONResponse(
                    status_code=404, 
                    content={"message": "Streamer not found in the database."}
                )

            event_type = body['subscription']['type']
            message = f"{streamer.username} is now **{'online' if event_type == 'stream.online' else 'offline'}**."

            new_stream = models.Stream(streamer_id=streamer_id, event_type=event_type)
            db.add(new_stream)
            db.commit()

            await manager.send_notification(message)

        return JSONResponse(status_code=200, content={"message": "Event processed successfully."})
    except Exception as e:
        logger.error(f"Error processing EventSub callback: {e}")
        raise

@app.delete("/api/streamers/{streamer_id}")
async def delete_streamer(streamer_id: int, db: Session = Depends(get_db)):
    try:
        # Unsubscribe from EventSub
        await event_sub.delete_all_subscriptions_of_type('stream.online', streamer_id)
        await event_sub.delete_all_subscriptions_of_type('stream.offline', streamer_id)
        
        # Delete from database
        streamer = db.query(models.Streamer).filter(models.Streamer.id == streamer_id).first()
        if streamer:
            db.delete(streamer)
            db.commit()
            await manager.send_notification(f"Removed streamer {streamer.username}")
            return {"message": "Streamer deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting streamer {streamer_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete streamer")

# Static files
app.mount("/static", StaticFiles(directory="app/frontend/dist"), name="static")
app.mount("/", StaticFiles(directory="app/frontend/dist", html=True), name="frontend")

# Error handler
app.add_exception_handler(Exception, error_handler)




