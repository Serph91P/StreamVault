import subprocess
from app.celery import celery 
from app.services.websocket import manager
from app.models import Streamer, TwitchEvent
from app.celery import make_celery
from datetime import datetime
import asyncio
from app import db

@celery.task
def start_recording_task(streamer_id):
    stream_url = f'https://twitch.tv/{streamer_id}'
    output_file = f'/recordings/{streamer_id}.mp4'
    
    # Update streamer status
    streamer = Streamer.query.filter_by(twitch_id=streamer_id).first()
    if streamer:
        streamer.is_live = True
        streamer.last_updated = datetime.utcnow()
        db.session.commit()
        
        # Send WebSocket update
        celery.send_task('send_websocket_update', args=[streamer.id])

@celery.task
def send_websocket_update(streamer_id):
    streamer = Streamer.query.filter_by(id=streamer_id).first()
    if streamer:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(manager.broadcast_streamer_update(streamer))