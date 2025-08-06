"""
Simple Recovery Service

Erstellt einfache metadata_generation Tasks ohne Dependencies,
da diese zuverlässig funktionieren im Gegensatz zu komplexen Dependency-Chains.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger("streamvault")


async def run_simple_reliable_recovery() -> Dict[str, Any]:
    """
    Führt einfache, zuverlässige Recovery durch
    
    Verwendet nur Single metadata_generation Tasks ohne Dependencies,
    da diese im Gegensatz zu komplexen Chains zuverlässig funktionieren.
    """
    results = {
        "start_time": datetime.now(timezone.utc).isoformat(),
        "simple_recovery": None,
        "total_recoveries": 0,
        "success": False
    }
    
    try:
        logger.info("🔧 Starting simple reliable recovery...")
        
        # Finde fehlgeschlagene Recordings mit Unified Recovery Service
        from ..services.recording.unified_recovery_service import get_unified_recovery_service
        unified_service = await get_unified_recovery_service()
        
        # Führe nur Scan aus (dry_run=True) um fehlgeschlagene Recordings zu finden
        unified_stats = await unified_service.comprehensive_recovery_scan(
            max_age_hours=72, 
            dry_run=True  # Nur scannen, nicht die komplexen Chains erstellen
        )
        
        failed_count = unified_stats.failed_post_processing
        logger.info(f"🔍 Found {failed_count} failed post-processing recordings")
        
        if failed_count > 0:
            # Erstelle einfache metadata_generation Tasks für jedes fehlgeschlagene Recording
            recovery_triggered = await create_simple_recovery_tasks()
            
            results["simple_recovery"] = {
                "success": True,
                "failed_found": failed_count,
                "recovery_triggered": recovery_triggered,
                "method": "simple_metadata_generation"
            }
            results["total_recoveries"] = recovery_triggered
            
            logger.info(f"✅ Simple recovery: {recovery_triggered} metadata_generation tasks created")
        else:
            results["simple_recovery"] = {
                "success": True,
                "failed_found": 0,
                "recovery_triggered": 0,
                "method": "simple_metadata_generation"
            }
            logger.info("ℹ️ No failed recordings found")
        
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = True
        
        logger.info(f"🎉 Simple recovery completed: {results['total_recoveries']} tasks created")
        return results
        
    except Exception as e:
        results["end_time"] = datetime.now(timezone.utc).isoformat()
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"❌ Simple recovery failed: {e}")
        return results


async def create_simple_recovery_tasks() -> int:
    """
    Erstellt einfache metadata_generation Tasks für fehlgeschlagene Recordings
    
    Returns:
        Anzahl der erstellten Tasks
    """
    from ..services.init.background_queue_init import get_background_queue_service
    from ..database import get_db_session
    from ..models import Recording, Stream, Streamer
    from ..services.queues.task_progress_tracker import TaskPriority
    
    recovery_count = 0
    
    try:
        queue_service = get_background_queue_service()
        
        # Finde alle Recordings ohne MP4-Datei
        with get_db_session() as db:
            # SQL Query um Recordings zu finden wo TS existiert aber MP4 fehlt
            recordings = db.query(Recording).join(Stream).join(Streamer).filter(
                Recording.recording_path.isnot(None),
                Stream.is_active == False  # Nur inaktive Streams
            ).all()
            
            for recording in recordings:
                try:
                    if not recording.recording_path:
                        continue
                        
                    # Prüfe ob TS existiert aber MP4 fehlt
                    import os
                    from pathlib import Path
                    
                    recording_path = Path(recording.recording_path)
                    if not recording_path.exists():
                        continue
                        
                    # Prüfe MP4
                    mp4_path = recording_path.parent / f"{recording_path.stem}.mp4"
                    if mp4_path.exists():
                        continue  # MP4 existiert bereits
                        
                    # MP4 fehlt - erstelle metadata_generation Task
                    payload = {
                        'recording_id': recording.id,
                        'stream_id': recording.stream_id,
                        'streamer_name': recording.stream.streamer.name,
                        'recording_path': str(recording.recording_path),
                        'simple_recovery': True,
                        'recovery_timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Enqueue einfachen Task (OHNE Dependencies)
                    task_id = await queue_service.enqueue_task(
                        task_type='metadata_generation',
                        payload=payload,
                        priority=TaskPriority.LOW  # Niedrige Priorität für Recovery
                    )
                    
                    recovery_count += 1
                    logger.info(f"✅ Created simple recovery task {task_id} for recording {recording.id} ({recording.stream.streamer.name})")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to create recovery task for recording {recording.id}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"❌ Failed to create simple recovery tasks: {e}")
        
    return recovery_count
