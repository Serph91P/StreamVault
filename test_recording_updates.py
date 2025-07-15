#!/usr/bin/env python3
"""
Test script to verify recording job updates are sent via WebSocket
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.dependencies import websocket_manager
from app.services.background_queue_service import background_queue_service
from datetime import datetime

async def test_recording_updates():
    """Test recording updates"""
    print("Testing recording job updates...")
    
    # Test recording job update
    recording_info = {
        'status': 'running',
        'streamer_name': 'test_streamer',
        'stream_id': 1,
        'recording_id': 1,
        'progress': 50,
        'started_at': datetime.now().isoformat()
    }
    
    try:
        await websocket_manager.send_recording_job_update(recording_info)
        print("✅ Recording job update sent successfully")
    except Exception as e:
        print(f"❌ Failed to send recording job update: {e}")
    
    # Test background task update  
    task_info = {
        "id": "test_task_1",
        "task_type": "recording",
        "status": "running",
        "progress": 75.0,
        "payload": {"message": "Test recording task"},
        "started_at": datetime.now().isoformat()
    }
    
    try:
        await websocket_manager.send_task_status_update(task_info)
        print("✅ Background task update sent successfully")
    except Exception as e:
        print(f"❌ Failed to send background task update: {e}")
    
    # Test queue stats update
    try:
        stats = await background_queue_service.get_queue_stats()
        await websocket_manager.send_queue_stats_update(stats)
        print("✅ Queue stats update sent successfully")
    except Exception as e:
        print(f"❌ Failed to send queue stats update: {e}")

if __name__ == "__main__":
    asyncio.run(test_recording_updates())
