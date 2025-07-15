#!/usr/bin/env python3
"""
Debug script to check if recordings are properly displayed in frontend
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.recording.recording_service import RecordingService
from app.services.background_queue_service import background_queue_service
from app.dependencies import websocket_manager
from app.database import SessionLocal
from app.models import Stream, Recording, Streamer
from datetime import datetime

async def check_active_recordings():
    """Check if there are any active recordings"""
    print("Checking active recordings...")
    
    # Initialize recording service
    with SessionLocal() as db:
        recording_service = RecordingService(db)
        
        # Check active recordings
        active_recordings = await recording_service.get_active_recordings()
        print(f"Active recordings: {len(active_recordings)}")
        
        for stream_id, recording_info in active_recordings.items():
            print(f"  Stream {stream_id}: {recording_info}")
            
            # Send WebSocket update for this recording
            try:
                await recording_service._send_recording_job_update(
                    recording_info.get('streamer_name', 'unknown'),
                    {
                        'status': 'running',
                        'streamer_name': recording_info.get('streamer_name', 'unknown'),
                        'stream_id': stream_id,
                        'recording_id': recording_info.get('recording_id', 0),
                        'progress': 50,
                        'started_at': recording_info.get('start_time', datetime.now()).isoformat()
                    }
                )
                print(f"✅ Sent recording job update for stream {stream_id}")
            except Exception as e:
                print(f"❌ Failed to send recording job update for stream {stream_id}: {e}")
        
        # Check background queue
        try:
            stats = await background_queue_service.get_queue_stats()
            print(f"Background queue stats: {stats}")
            
            active_tasks = await background_queue_service.get_active_tasks()
            print(f"Active background tasks: {len(active_tasks)}")
            
            for task in active_tasks:
                print(f"  Task: {task}")
                
        except Exception as e:
            print(f"❌ Failed to get background queue info: {e}")

if __name__ == "__main__":
    asyncio.run(check_active_recordings())
