"""
RecordingStateManager - Active recordings tracking and persistence

Extracted from recording_service.py ULTRA-BOSS (1084 lines)
Handles active recordings state, task tracking, and recovery after restarts.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from app.services.core.state_persistence_service import state_persistence_service

logger = logging.getLogger("streamvault")


class RecordingStateManager:
    """Manages active recording state and persistence"""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager

        # Active recordings tracking
        self.active_recordings: Dict[int, Dict[str, Any]] = {}
        self.recording_tasks: Dict[int, asyncio.Task] = {}

    def add_active_recording(self, recording_id: int, recording_data: Dict[str, Any]) -> None:
        """Add recording to active tracking"""
        self.active_recordings[recording_id] = {
            **recording_data,
            'started_at': datetime.utcnow().isoformat(),
            'status': 'recording'
        }
        logger.info(f"Added recording {recording_id} to active tracking")

    def remove_active_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Remove recording from active tracking"""
        recording_data = self.active_recordings.pop(recording_id, None)
        if recording_data:
            logger.info(f"Removed recording {recording_id} from active tracking")
        return recording_data

    def get_active_recording(self, recording_id: int) -> Optional[Dict[str, Any]]:
        """Get active recording data"""
        return self.active_recordings.get(recording_id)

    def update_active_recording(self, recording_id: int, update_data: Dict[str, Any]) -> None:
        """Update active recording data"""
        if recording_id in self.active_recordings:
            self.active_recordings[recording_id].update(update_data)
            logger.debug(f"Updated active recording {recording_id} data")

    def get_active_recordings(self) -> Dict[int, Dict[str, Any]]:
        """Get all active recordings"""
        return self.active_recordings.copy()

    def get_active_recording_count(self) -> int:
        """Get count of active recordings"""
        return len(self.active_recordings)

    # Task management

    def add_recording_task(self, recording_id: int, task: asyncio.Task) -> None:
        """Add recording task to tracking"""
        self.recording_tasks[recording_id] = task
        logger.debug(f"Added recording task {recording_id} to tracking")

    def remove_recording_task(self, recording_id: int) -> Optional[asyncio.Task]:
        """Remove recording task from tracking"""
        task = self.recording_tasks.pop(recording_id, None)
        if task:
            logger.debug(f"Removed recording task {recording_id} from tracking")
        return task

    def get_recording_task(self, recording_id: int) -> Optional[asyncio.Task]:
        """Get recording task"""
        return self.recording_tasks.get(recording_id)

    def get_active_tasks(self) -> Dict[int, asyncio.Task]:
        """Get all active recording tasks"""
        return self.recording_tasks.copy()

    def cancel_recording_task(self, recording_id: int) -> bool:
        """Cancel recording task"""
        task = self.recording_tasks.get(recording_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"Cancelled recording task {recording_id}")
            return True
        return False

    def cancel_all_tasks(self) -> List[int]:
        """Cancel all recording tasks"""
        cancelled_tasks = []
        for recording_id, task in self.recording_tasks.items():
            if not task.done():
                task.cancel()
                cancelled_tasks.append(recording_id)

        if cancelled_tasks:
            logger.info(f"Cancelled {len(cancelled_tasks)} recording tasks")

        return cancelled_tasks

    def cleanup_finished_tasks(self) -> List[int]:
        """Clean up finished recording tasks"""
        finished_tasks = []

        for recording_id, task in list(self.recording_tasks.items()):
            if task.done():
                self.recording_tasks.pop(recording_id)
                finished_tasks.append(recording_id)

        if finished_tasks:
            logger.debug(f"Cleaned up {len(finished_tasks)} finished recording tasks")

        return finished_tasks

    # State persistence

    async def save_state_to_persistence(self) -> None:
        """Save active recordings state to persistence"""
        try:
            if not state_persistence_service:
                logger.warning("State persistence service not available")
                return

            persistence_data = {
                'active_recordings': {},
                'timestamp': datetime.utcnow().isoformat()
            }

            # Convert active recordings to serializable format
            for recording_id, recording_data in self.active_recordings.items():
                persistence_data['active_recordings'][str(recording_id)] = {
                    k: v for k, v in recording_data.items()
                    if isinstance(v, (str, int, float, bool, type(None)))
                }

            # Note: save_state method removed - persistence now happens via ActiveRecordingState table
            # Each recording is saved individually via save_active_recording
            logger.debug("State persistence handled via ActiveRecordingState table")

        except Exception as e:
            logger.error(f"Failed to save state to persistence: {e}")

    async def load_state_from_persistence(self) -> Dict[str, Any]:
        """Load active recordings state from persistence"""
        try:
            if not state_persistence_service:
                logger.warning("State persistence service not available")
                return {}

            state_data = await state_persistence_service.load_state()
            if state_data:
                logger.info(f"Loaded {len(state_data)} recordings from persistence")
                # Convert List[ActiveRecordingState] to Dict format expected by recovery logic
                return {recording.stream_id: recording for recording in state_data}

            return {}

        except Exception as e:
            logger.error(f"Failed to load state from persistence: {e}")
            return {}

    async def recover_active_recordings_from_persistence(self, database_service) -> List[int]:
        """Recover active recordings from persistence"""
        recovered_recordings = []

        try:
            # Load from persistence
            persisted_recordings = await self.load_state_from_persistence()

            if not persisted_recordings:
                logger.info("No recordings to recover from persistence")
                return recovered_recordings

            # Get active recordings from database
            active_db_recordings = await database_service.get_active_recordings_from_db()
            active_db_ids = {r.id for r in active_db_recordings}

            # Recover recordings that are both in persistence and database
            for recording_id_str, recording_data in persisted_recordings.items():
                try:
                    recording_id = int(recording_id_str)

                    if recording_id in active_db_ids:
                        # Recovery logic for individual recording
                        success = await self._recover_single_recording(
                            recording_id, recording_data, database_service
                        )

                        if success:
                            recovered_recordings.append(recording_id)
                            logger.info(f"Successfully recovered recording {recording_id}")
                        else:
                            logger.warning(f"Failed to recover recording {recording_id}")
                    else:
                        logger.info(f"Recording {recording_id} not found in database, skipping recovery")

                except Exception as e:
                    logger.error(f"Error recovering recording {recording_id_str}: {e}")

            if recovered_recordings:
                logger.info(f"Recovered {len(recovered_recordings)} recordings from persistence")

        except Exception as e:
            logger.error(f"Failed to recover recordings from persistence: {e}")

        return recovered_recordings

    async def _recover_single_recording(
        self, recording_id: int, recording_data: Dict[str, Any], database_service
    ) -> bool:
        """Recover a single recording"""
        try:
            # Get recording from database
            recording = await database_service.get_recording(recording_id)
            if not recording:
                logger.warning(f"Recording {recording_id} not found in database")
                return False

            # Check if recording file still exists
            file_path = recording_data.get('file_path') or recording.path
            if file_path and not Path(file_path).exists():
                logger.warning(f"Recording file {file_path} no longer exists")
                # Mark recording as failed
                await database_service.mark_recording_failed(
                    recording_id, "Recording file lost during recovery"
                )
                return False

            # Add to active recordings
            self.add_active_recording(recording_id, {
                'file_path': file_path,
                'streamer_id': recording.stream.streamer_id if recording.stream else None,
                'stream_id': recording.stream_id,
                'recovered': True,
                **recording_data
            })

            return True

        except Exception as e:
            logger.error(f"Failed to recover recording {recording_id}: {e}")
            return False

    def get_recording_statistics(self) -> Dict[str, Any]:
        """Get recording statistics"""
        active_count = self.get_active_recording_count()
        task_count = len(self.recording_tasks)

        return {
            'active_recordings': active_count,
            'active_tasks': task_count
        }

    def clear_all_state(self) -> None:
        """Clear all state (for shutdown)"""
        self.active_recordings.clear()
        self.recording_tasks.clear()
        logger.info("Cleared all recording state")
