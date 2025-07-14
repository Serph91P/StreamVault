"""
Recording Task Factory
Creates task chains for recording post-processing with proper dependencies
"""
import logging
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path

from app.services.task_dependency_manager import Task, TaskStatus

logger = logging.getLogger("streamvault")

class RecordingTaskFactory:
    """Factory for creating recording post-processing task chains"""
    
    @staticmethod
    def create_post_processing_chain(
        stream_id: int,
        recording_id: int,
        ts_file_path: str,
        output_dir: str,
        streamer_name: str,
        started_at: str,
        cleanup_ts_file: bool = True
    ) -> List[Task]:
        """Create a complete post-processing task chain for a recording
        
        Args:
            stream_id: Stream ID
            recording_id: Recording ID
            ts_file_path: Path to the .ts file
            output_dir: Output directory
            streamer_name: Name of the streamer
            started_at: Recording start time (ISO format)
            cleanup_ts_file: Whether to cleanup the .ts file after processing
            
        Returns:
            List of tasks with proper dependencies
        """
        tasks = []
        
        # Base task IDs
        base_id = f"stream_{stream_id}_recording_{recording_id}"
        
        # Task IDs
        metadata_task_id = f"{base_id}_metadata"
        chapters_task_id = f"{base_id}_chapters"
        mp4_remux_task_id = f"{base_id}_mp4_remux"
        thumbnail_task_id = f"{base_id}_thumbnail"
        cleanup_task_id = f"{base_id}_cleanup"
        
        # Common payload data
        common_payload = {
            'stream_id': stream_id,
            'recording_id': recording_id,
            'ts_file_path': ts_file_path,
            'output_dir': output_dir,
            'streamer_name': streamer_name,
            'started_at': started_at
        }
        
        # Calculate MP4 output path
        ts_path = Path(ts_file_path)
        mp4_path = str(ts_path.with_suffix('.mp4'))
        
        # 1. Metadata Generation Task (no dependencies)
        metadata_task = Task(
            id=metadata_task_id,
            type='metadata_generation',
            payload={
                **common_payload,
                'mp4_path': mp4_path,  # Metadata needs to know the final MP4 path
                'base_filename': ts_path.stem
            },
            dependencies=set(),
            priority=1  # High priority
        )
        tasks.append(metadata_task)
        
        # 2. Chapters Generation Task (no dependencies)
        chapters_task = Task(
            id=chapters_task_id,
            type='chapters_generation',
            payload={
                **common_payload,
                'mp4_path': mp4_path,
                'base_filename': ts_path.stem
            },
            dependencies=set(),
            priority=1  # High priority
        )
        tasks.append(chapters_task)
        
        # 3. MP4 Remux Task (depends on metadata and chapters)
        mp4_remux_task = Task(
            id=mp4_remux_task_id,
            type='mp4_remux',
            payload={
                **common_payload,
                'mp4_output_path': mp4_path,
                'overwrite': True,
                'include_metadata': True,
                'include_chapters': True
            },
            dependencies={metadata_task_id, chapters_task_id},
            priority=2  # Medium priority
        )
        tasks.append(mp4_remux_task)
        
        # 4. Thumbnail Generation Task (depends on MP4 remux)
        thumbnail_task = Task(
            id=thumbnail_task_id,
            type='thumbnail_generation',
            payload={
                **common_payload,
                'mp4_path': mp4_path,
                'fallback_to_video_extraction': True
            },
            dependencies={mp4_remux_task_id},
            priority=3  # Lower priority
        )
        tasks.append(thumbnail_task)
        
        # 5. Cleanup Task (depends on thumbnail, only if cleanup_ts_file is True)
        if cleanup_ts_file:
            cleanup_task = Task(
                id=cleanup_task_id,
                type='cleanup',
                payload={
                    **common_payload,
                    'files_to_remove': [ts_file_path],
                    'mp4_path': mp4_path
                },
                dependencies={thumbnail_task_id},
                priority=4  # Lowest priority
            )
            tasks.append(cleanup_task)
        
        logger.info(f"Created post-processing chain for stream {stream_id} with {len(tasks)} tasks")
        
        return tasks
    
    @staticmethod
    def create_metadata_only_chain(
        stream_id: int,
        recording_id: int,
        mp4_file_path: str,
        output_dir: str,
        streamer_name: str,
        started_at: str
    ) -> List[Task]:
        """Create a metadata-only task chain for existing MP4 files
        
        Args:
            stream_id: Stream ID
            recording_id: Recording ID
            mp4_file_path: Path to the existing MP4 file
            output_dir: Output directory
            streamer_name: Name of the streamer
            started_at: Recording start time (ISO format)
            
        Returns:
            List of tasks for metadata generation only
        """
        tasks = []
        
        # Base task IDs
        base_id = f"stream_{stream_id}_metadata_only"
        
        # Task IDs
        metadata_task_id = f"{base_id}_metadata"
        chapters_task_id = f"{base_id}_chapters"
        thumbnail_task_id = f"{base_id}_thumbnail"
        
        # Common payload data
        common_payload = {
            'stream_id': stream_id,
            'recording_id': recording_id,
            'mp4_path': mp4_file_path,
            'output_dir': output_dir,
            'streamer_name': streamer_name,
            'started_at': started_at
        }
        
        mp4_path = Path(mp4_file_path)
        
        # 1. Metadata Generation Task
        metadata_task = Task(
            id=metadata_task_id,
            type='metadata_generation',
            payload={
                **common_payload,
                'base_filename': mp4_path.stem
            },
            dependencies=set(),
            priority=1
        )
        tasks.append(metadata_task)
        
        # 2. Chapters Generation Task
        chapters_task = Task(
            id=chapters_task_id,
            type='chapters_generation',
            payload={
                **common_payload,
                'base_filename': mp4_path.stem
            },
            dependencies=set(),
            priority=1
        )
        tasks.append(chapters_task)
        
        # 3. Thumbnail Generation Task
        thumbnail_task = Task(
            id=thumbnail_task_id,
            type='thumbnail_generation',
            payload={
                **common_payload,
                'fallback_to_video_extraction': True
            },
            dependencies=set(),
            priority=2
        )
        tasks.append(thumbnail_task)
        
        logger.info(f"Created metadata-only chain for stream {stream_id} with {len(tasks)} tasks")
        
        return tasks
    
    @staticmethod
    def create_thumbnail_only_task(
        stream_id: int,
        recording_id: int,
        mp4_file_path: str,
        output_dir: str,
        streamer_name: str,
        started_at: str
    ) -> Task:
        """Create a single thumbnail generation task
        
        Args:
            stream_id: Stream ID
            recording_id: Recording ID
            mp4_file_path: Path to the MP4 file
            output_dir: Output directory
            streamer_name: Name of the streamer
            started_at: Recording start time (ISO format)
            
        Returns:
            Single thumbnail generation task
        """
        task_id = f"stream_{stream_id}_thumbnail_only"
        
        return Task(
            id=task_id,
            type='thumbnail_generation',
            payload={
                'stream_id': stream_id,
                'recording_id': recording_id,
                'mp4_path': mp4_file_path,
                'output_dir': output_dir,
                'streamer_name': streamer_name,
                'started_at': started_at,
                'fallback_to_video_extraction': True
            },
            dependencies=set(),
            priority=2
        )
    
    @staticmethod
    def create_repair_chain(
        stream_id: int,
        recording_id: int,
        ts_file_path: str,
        output_dir: str,
        streamer_name: str,
        started_at: str,
        failed_tasks: List[str]
    ) -> List[Task]:
        """Create a repair task chain for failed processing
        
        Args:
            stream_id: Stream ID
            recording_id: Recording ID
            ts_file_path: Path to the .ts file
            output_dir: Output directory
            streamer_name: Name of the streamer
            started_at: Recording start time (ISO format)
            failed_tasks: List of failed task types to retry
            
        Returns:
            List of repair tasks
        """
        tasks = []
        
        # Base task IDs
        base_id = f"stream_{stream_id}_repair_{int(datetime.now().timestamp())}"
        
        # Common payload data
        common_payload = {
            'stream_id': stream_id,
            'recording_id': recording_id,
            'ts_file_path': ts_file_path,
            'output_dir': output_dir,
            'streamer_name': streamer_name,
            'started_at': started_at
        }
        
        ts_path = Path(ts_file_path)
        mp4_path = str(ts_path.with_suffix('.mp4'))
        
        # Create tasks only for failed steps
        dependencies = set()
        
        if 'metadata' in failed_tasks or 'metadata_generation' in failed_tasks:
            metadata_task_id = f"{base_id}_metadata"
            metadata_task = Task(
                id=metadata_task_id,
                type='metadata_generation',
                payload={
                    **common_payload,
                    'mp4_path': mp4_path,
                    'base_filename': ts_path.stem
                },
                dependencies=set(),
                priority=1,
                max_retries=1  # Reduced retries for repair
            )
            tasks.append(metadata_task)
            dependencies.add(metadata_task_id)
        
        if 'chapters' in failed_tasks or 'chapters_generation' in failed_tasks:
            chapters_task_id = f"{base_id}_chapters"
            chapters_task = Task(
                id=chapters_task_id,
                type='chapters_generation',
                payload={
                    **common_payload,
                    'mp4_path': mp4_path,
                    'base_filename': ts_path.stem
                },
                dependencies=set(),
                priority=1,
                max_retries=1
            )
            tasks.append(chapters_task)
            dependencies.add(chapters_task_id)
        
        if 'mp4_remux' in failed_tasks:
            mp4_remux_task_id = f"{base_id}_mp4_remux"
            mp4_remux_task = Task(
                id=mp4_remux_task_id,
                type='mp4_remux',
                payload={
                    **common_payload,
                    'mp4_output_path': mp4_path,
                    'overwrite': True,
                    'include_metadata': True,
                    'include_chapters': True
                },
                dependencies=dependencies,
                priority=2,
                max_retries=1
            )
            tasks.append(mp4_remux_task)
            dependencies = {mp4_remux_task_id}
        
        if 'thumbnail' in failed_tasks or 'thumbnail_generation' in failed_tasks:
            thumbnail_task_id = f"{base_id}_thumbnail"
            thumbnail_task = Task(
                id=thumbnail_task_id,
                type='thumbnail_generation',
                payload={
                    **common_payload,
                    'mp4_path': mp4_path,
                    'fallback_to_video_extraction': True
                },
                dependencies=dependencies,
                priority=3,
                max_retries=1
            )
            tasks.append(thumbnail_task)
        
        logger.info(f"Created repair chain for stream {stream_id} with {len(tasks)} tasks for failed steps: {failed_tasks}")
        
        return tasks
