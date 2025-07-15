"""
Optimized State Persistence Service

Optimized version with batch updates and connection pooling
for better performance with PostgreSQL.
"""
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from sqlalchemy import text, select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ActiveRecordingState

logger = logging.getLogger("streamvault")

class OptimizedStatePersistenceService:
    """Optimized version with batch operations and better connection handling"""
    
    def __init__(self):
        self.heartbeat_interval = 60  # seconds
        self.batch_size = 50  # Process in batches
        
    async def batch_update_heartbeats(self, stream_ids: List[int]) -> int:
        """Update heartbeats for multiple streams in a single transaction"""
        if not stream_ids:
            return 0
            
        try:
            with SessionLocal() as db:
                # Single UPDATE statement for all streams
                updated_count = db.execute(
                    update(ActiveRecordingState)
                    .where(ActiveRecordingState.stream_id.in_(stream_ids))
                    .values(last_heartbeat=datetime.now(timezone.utc))
                ).rowcount
                
                db.commit()
                logger.debug(f"Updated {updated_count} heartbeats in batch")
                return updated_count
                
        except Exception as e:
            logger.error(f"Error in batch heartbeat update: {e}")
            return 0
            
    async def cleanup_stale_entries_optimized(self, max_age_seconds: int = 300) -> int:
        """Optimized cleanup with single DELETE statement"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
            
            with SessionLocal() as db:
                # Single DELETE statement
                deleted_count = db.execute(
                    text("""
                        DELETE FROM active_recordings_state 
                        WHERE last_heartbeat < :cutoff_time
                        OR status = 'error'
                    """),
                    {"cutoff_time": cutoff_time}
                ).rowcount
                
                db.commit()
                
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} stale recording entries")
                    
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error in optimized cleanup: {e}")
            return 0
            
    async def get_active_recordings_optimized(self) -> List[Dict[str, Any]]:
        """Optimized query with eager loading"""
        try:
            with SessionLocal() as db:
                # Single query with join
                result = db.execute(
                    text("""
                        SELECT ars.*, s.title, s.category_name
                        FROM active_recordings_state ars
                        JOIN streams s ON ars.stream_id = s.id
                        WHERE ars.status = 'active'
                        ORDER BY ars.started_at DESC
                    """)
                ).fetchall()
                
                return [dict(row._mapping) for row in result]
                
        except Exception as e:
            logger.error(f"Error getting active recordings: {e}")
            return []

# Usage example for better performance
async def optimized_heartbeat_update(active_stream_ids: List[int]):
    """Update heartbeats for all active streams efficiently"""
    service = OptimizedStatePersistenceService()
    
    # Process in batches to avoid large transactions
    for i in range(0, len(active_stream_ids), service.batch_size):
        batch = active_stream_ids[i:i + service.batch_size]
        await service.batch_update_heartbeats(batch)
