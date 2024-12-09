import os
import asyncio
import logging
from app.config.logging_config import setup_logging
from app.middleware.auth import AuthMiddleware
from app.middleware.error_handler import error_handler
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.webhook import EventSubWebhook as EventSub
from twitchAPI.object.eventsub import ChannelFollowEvent
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
import threading
import app.models as models
from app.database import SessionLocal, engine
from starlette.websockets import WebSocketState

# Initialize logging
logger = setup_logging()

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Add error handling middleware
app.add_exception_handler(Exception, error_handler)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

# Initialize the manager
manager = ConnectionManager()

# Twitch API credentials
APP_ID = os.getenv('TWITCH_APP_ID')
APP_SECRET = os.getenv('TWITCH_APP_SECRET')
BASE_URL = os.getenv('BASE_URL')
WEBHOOK_URL = f"{BASE_URL}/eventsub"

if not all([APP_ID, APP_SECRET, BASE_URL]):
    raise ValueError("Missing required environment variables")

# Initialize Twitch API
twitch = None

async def initialize_twitch():
    global twitch
    try:
        twitch = Twitch(APP_ID, APP_SECRET)
        await twitch.authenticate_app([])
        logger.info("Twitch API initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Twitch API: {e}")
        raise

# Initialize EventSub
event_sub = None

async def initialize_eventsub():
    global event_sub
    try:
        event_sub = EventSub(WEBHOOK_URL, APP_SECRET, twitch)
        await event_sub.start()
        logger.info("EventSub initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize EventSub: {e}")
        raise

@app.on_event("startup")
async def startup_event():
    try:
        await initialize_twitch()
        await initialize_eventsub()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

# Pydantic models with updated config
class StreamerBase(BaseModel):
    username: str

class StreamerCreate(StreamerBase):
    pass

class Streamer(StreamerBase):
    id: int

    class Config:
        from_attributes = True

# Routes remain the same as in your original main.py, but with added logging
@app.get("/", response_class=HTMLResponse)
async def read_root():
    logger.info("Serving homepage")
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Twitch Streamer Monitor</title>
    </head>
    <body>
        <h1>Twitch Streamer Monitor</h1>
        <form action="/add_streamer" method="post">
            <input type="text" name="username" placeholder="Streamer Username" required>
            <button type="submit">Add Streamer</button>
        </form>
        <ul id="notifications"></ul>
        <script>
            var ws = new WebSocket("ws://" + location.host + "/ws");
            ws.onmessage = function(event) {
                var notifications = document.getElementById('notifications');
                var newItem = document.createElement('li');
                newItem.textContent = event.data;
                notifications.appendChild(newItem);
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/add_streamer")
async def add_streamer(username: str = Form(...), background_tasks: BackgroundTasks = BackgroundTasks(), db: Session = Depends(get_db)):
    try:
        existing_streamer = db.query(models.Streamer).filter(models.Streamer.username == username).first()
        if existing_streamer:
            logger.warning(f"Attempted to add existing streamer: {username}")
            return JSONResponse(status_code=400, content={"message": f"Streamer {username} is already subscribed."})

        background_tasks.add_task(subscribe_to_streamer, username, db)
        logger.info(f"Added subscription task for streamer: {username}")
        return HTMLResponse(content=f"Subscription to {username} is being processed.")
    except Exception as e:
        logger.error(f"Error adding streamer {username}: {e}")
        raise

async def subscribe_to_streamer(username: str, db: Session):
    try:
        user_info = await twitch.get_users(logins=[username])
        if not user_info['data']:
            await manager.send_notification(f"Streamer {username} does not exist.")
            return

        user_data = user_info['data'][0]
        user_id = user_data['id']
        display_name = user_data['display_name']

        # Add streamer to database
        new_streamer = models.Streamer(id=user_id, username=display_name)
        db.add(new_streamer)
        db.commit()

        # Updated subscription calls with correct parameters
        await event_sub.listen_stream_online(user_id)
        await event_sub.listen_stream_offline(user_id)

        await manager.send_notification(f"Successfully subscribed to {display_name}.")

    except Exception as e:
        await manager.send_notification(f"Failed to subscribe to {username}: {str(e)}")

@app.post("/eventsub")
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
                return JSONResponse(status_code=404, content={"message": "Streamer not found in the database."})

            event_type = body['subscription']['type']
            message = ""
            if event_type == 'stream.online':
                message = f"{streamer.username} is now **online**."
            elif event_type == 'stream.offline':
                message = f"{streamer.username} is now **offline**."

            # Save event to the database
            new_stream = models.Stream(streamer_id=streamer_id, event_type=event_type)
            db.add(new_stream)
            db.commit()

            # Send notification via WebSocket
            await manager.send_notification(message)

        return JSONResponse(status_code=200, content={"message": "Event processed successfully."})
    except Exception as e:
        logger.error(f"Error processing EventSub callback: {e}")
        raise

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.on_event("shutdown")
async def shutdown_event():
    try:
        if event_sub:
            await event_sub.stop()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
