"""
File operations for the recording service.

This module handles all file-related operations like remuxing and cleanup.
"""
import os
import json
import asyncio
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
import logging

from app.models import Stream, StreamMetadata
from app.database import SessionLocal
from app.services.media.metadata_service import MetadataService
from app.utils.file_utils import cleanup_temporary_files
# FFmpeg utilities now handled by background queue system

logger = logging.getLogger("streamvault")

async def intelligent_ts_cleanup(output_path: str, max_wait_time: int = 1800, psutil_available: bool = False):
    """Intelligent cleanup that monitors FFmpeg processes and file system for TS to MP4 completion.
    
    This monitors:
    1. Running FFmpeg processes that might be remuxing our files
    2. File system changes (TS file stable, MP4 file growing)
    3. Process completion signals
    
    Args:
        output_path: Path to the TS file
        max_wait_time: Maximum time to wait for processing (default: 30 minutes)
        psutil_available: Whether psutil module is available
    """
    try:
        if not output_path.endswith('.ts') or not os.path.exists(output_path):
            return
                
        mp4_path = output_path.replace('.ts', '.mp4')
        start_time = datetime.now()
        check_interval = 10  # Check every 10 seconds
        
        logger.info(f"Starting intelligent process-aware TS cleanup for {output_path}")
        
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Check if MP4 file exists and is stable
            if os.path.exists(mp4_path):
                mp4_size = os.path.getsize(mp4_path)
                
                # Check if any FFmpeg processes are working on our files
                active_ffmpeg_processes = await check_ffmpeg_processes_for_file(output_path, mp4_path) if psutil_available else []
                
                if not active_ffmpeg_processes:
                    # No FFmpeg processes working on our files, check if MP4 is stable
                    await asyncio.sleep(5)  # Wait a bit
                    
                    if os.path.exists(mp4_path):
                        new_mp4_size = os.path.getsize(mp4_path)
                        
                        if new_mp4_size == mp4_size and new_mp4_size > 1024 * 1024:  # Stable and > 1MB
                            # Final verification: try to read the MP4 file
                            try:
                                with open(mp4_path, 'rb') as f:
                                    f.read(1024)  # Try to read first 1KB
                                
                                # MP4 is ready and stable, safe to remove TS
                                os.remove(output_path)
                                logger.info(f"Process-aware cleanup: Removed TS file {output_path} (waited {elapsed:.0f}s)")
                                return True
                                
                            except Exception as e:
                                logger.warning(f"MP4 file not readable yet, will retry: {e}")
                else:
                    logger.debug(f"FFmpeg processes still active for our files: {len(active_ffmpeg_processes)} processes")
            
            # Check if we've exceeded max wait time
            if elapsed > max_wait_time:
                logger.warning(f"Process-aware cleanup timeout ({max_wait_time}s), keeping TS file: {output_path}")
                return False
            
            # Wait before next check
            await asyncio.sleep(check_interval)
        
    except Exception as e:
        logger.error(f"Error in process-aware TS cleanup for {output_path}: {e}", exc_info=True)

async def check_ffmpeg_processes_for_file(ts_path: str, mp4_path: str) -> List[Dict[str, Any]]:
    """Check for running FFmpeg processes that might be working on our files.
    
    This uses psutil if available. If not, it returns an empty list.
    
    Args:
        ts_path: Path to the TS file
        mp4_path: Path to the MP4 file
            
    Returns:
        List of process information for active FFmpeg processes on our files
    """
    try:
        import psutil
        active_processes = []
        
        # Get the base filename without extension for matching
        ts_basename = os.path.basename(ts_path)
        mp4_basename = os.path.basename(mp4_path)
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                if not proc_info['name']:
                    continue
                    
                # Check if this is an FFmpeg process
                if 'ffmpeg' in proc_info['name'].lower():
                    cmdline = proc_info.get('cmdline', [])
                    if cmdline:
                        cmdline_str = ' '.join(cmdline)
                        
                        # Check if this FFmpeg process is working with our files
                        if ts_basename in cmdline_str or mp4_basename in cmdline_str:
                            active_processes.append({
                                'pid': proc_info['pid'],
                                'name': proc_info['name'],
                                'cmdline': cmdline_str[:200]  # Truncate for logging
                            })
                            logger.debug(f"Found active FFmpeg process: PID {proc_info['pid']}")
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process might have ended or we don't have permission
                continue
        
        return active_processes
        
    except ImportError:
        return []
    except Exception as e:
        logger.error(f"Error checking FFmpeg processes: {e}")
        return []

async def find_existing_mp4(recording_dir: str, mp4_path: str) -> Optional[str]:
    """
    Find existing MP4 file in recording directory
    
    Returns:
        Optional[str]: Path to existing MP4 file or None if not found
    """
    try:
        # Check if MP4 already exists
        if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 1000000:  # > 1MB
            logger.info(f"Using existing MP4 file: {mp4_path}")
            return mp4_path
                
        # Look for any MP4 files in recording directory
        recording_path = Path(recording_dir)
        mp4_files = list(recording_path.glob("*.mp4"))
        
        if mp4_files:
            # Use the largest MP4 file
            largest_mp4 = max(mp4_files, key=lambda p: p.stat().st_size)
            if largest_mp4.stat().st_size > 1000000:  # > 1MB
                logger.info(f"Found existing MP4 file: {largest_mp4}")
                return str(largest_mp4)
                
        logger.warning(f"No valid MP4 file found in {recording_dir}")
        return None
            
    except Exception as e:
        logger.error(f"Error in find_existing_mp4 for {recording_dir}: {e}", exc_info=True)
        return None


