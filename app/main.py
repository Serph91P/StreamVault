import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub import EventSub
from twitchAPI.types import AuthScope
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
import threading
import app.models as models
from app.database import SessionLocal, engine
from starlette.websockets import WebSocketState

# Create the database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Mount static files (if any)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Twitch API credentials from environment variables
APP_ID = os.getenv('TWITCH_APP_ID')
APP_SECRET = os.getenv('TWITCH_APP_SECRET')
BASE_URL = os.getenv('BASE_URL')  # Use BASE_URL for webhook URL
WEBHOOK_URL = f"{BASE_URL}/eventsub"

if not APP_ID or not APP_SECRET or not WEBHOOK_URL:
    raise Exception("Environment variables TWITCH_APP_ID, TWITCH_APP_SECRET, and WEBHOOK_URL must be set")

# Initialize Twitch API
twitch = Twitch(APP_ID, APP_SECRET)
twitch.authenticate_app([])

# Initialize EventSub
event_sub = EventSub(WEBHOOK_URL, 7000, twitch)

# Start EventSub listener in a separate thread
def start_eventsub():
    event_sub.listen()

thread = threading.Thread(target=start_eventsub, daemon=True)
thread.start()

# Pydantic models
class StreamerBase(BaseModel):
    username: str

class StreamerCreate(StreamerBase):
    pass

class Streamer(StreamerBase):
    id: int

    class Config:
        orm_mode = True

# Route to serve the homepage
@app.get("/", response_class=HTMLResponse)
async def read_root():
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

# Endpoint to add a streamer
@app.post("/add_streamer")
async def add_streamer(username: str = Form(...), background_tasks: BackgroundTasks = BackgroundTasks(), db: Session = Depends(get_db)):
    # Check if streamer is already in the database
    existing_streamer = db.query(models.Streamer).filter(models.Streamer.username == username).first()
    if existing_streamer:
        return JSONResponse(status_code=400, content={"message": f"Streamer {username} is already subscribed."})

    # Add the subscription task to background tasks
    background_tasks.add_task(subscribe_to_streamer, username, db)
    return HTMLResponse(content=f"Subscription to {username} is being processed. You will receive a notification shortly.")

# Function to subscribe to a streamer asynchronously
async def subscribe_to_streamer(username: str, db: Session):
    try:
        # Get user information from Twitch API
        user_info = await twitch.get_users(logins=[username])
        if not user_info['data']:
            await manager.send_notification(f"Streamer {username} does not exist.")
            return

        user_data = user_info['data'][0]
        user_id = user_data['id']
        display_name = user_data['display_name']

        # Add streamer to the database
        new_streamer = models.Streamer(id=user_id, username=display_name)
        db.add(new_streamer)
        db.commit()

        # Subscribe to stream.online and stream.offline events
        await event_sub.subscribe_channel_stream_online(broadcaster_user_id=user_id, callback_url=f"{WEBHOOK_URL}/eventsub")
        await event_sub.subscribe_channel_stream_offline(broadcaster_user_id=user_id, callback_url=f"{WEBHOOK_URL}/eventsub")

        await manager.send_notification(f"Successfully subscribed to {display_name}.")

    except Exception as e:
        await manager.send_notification(f"Failed to subscribe to {username}: {str(e)}")

# EventSub notification handler
@app.post("/eventsub")
async def eventsub_callback(request: Request, db: Session = Depends(get_db)):
    headers = request.headers
    body = await request.json()

    # Handle EventSub verification
    if headers.get('Twitch-Eventsub-Message-Type') == 'webhook_callback_verification':
        return Response(content=body['challenge'], media_type='text/plain')

    # Handle incoming notifications
    if headers.get('Twitch-Eventsub-Message-Type') == 'notification':
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

    return JSONResponse(status_code=200, content={"message": "Event received successfully."})

# WebSocket endpoint for real-time notifications
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Shutdown EventSub when the app stops
@app.on_event("shutdown")
async def shutdown_event():
    await event_sub.stop()

