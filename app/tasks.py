import subprocess
from app.celery import celery 
from app.services.websocket import manager
from app.models import Streamer, TwitchEvent
from app import db
from datetime import datetime
import asyncio
import os

@celery.task
def start_recording_task(streamer_id):
    stream_url = f'https://twitch.tv/{streamer_id}'
    output_file = os.path.join(os.getenv('RECORDINGS_DIR', '/recordings/'), f'{streamer_id}.mp4')
    
    streamer = Streamer.query.filter_by(twitch_id=streamer_id).first()
    if streamer:
        streamer.is_live = True
        streamer.last_updated = datetime.utcnow()
        db.session.commit()
        
        # Start recording process
        try:
            subprocess.Popen(['streamlink', stream_url, 'best', '-o', output_file])
        except Exception as e:
            print(f"Recording failed to start: {e}")
            
        celery.send_task('send_websocket_update', args=[streamer.id])

@celery.task
def send_websocket_update(streamer_id):
    streamer = Streamer.query.filter_by(id=streamer_id).first()
    if streamer:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.broadcast_streamer_update(streamer))
        loop.close()