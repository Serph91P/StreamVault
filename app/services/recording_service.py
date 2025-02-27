import os
import asyncio
import logging
import subprocess
import re
import signal
from datetime import datetime
from typing import Dict, Optional, List, Any

from app.database import SessionLocal
from app.models import Streamer, RecordingSettings, StreamerRecordingSettings, Stream, StreamEvent
from app.config.settings import settings

logger = logging.getLogger("streamvault")

class RecordingService:
    def __init__(self):
        self.active_recordings = {}  # streamer_id: process
        self.lock = asyncio.Lock()
    
    async def start_recording(self, streamer_id: int, stream_data: Dict[str, Any]) -> bool:
        """Start recording a stream"""
        async with self.lock:
            if streamer_id in self.active_recordings:
                logger.debug(f"Recording already active for streamer {streamer_id}")
                return False
                
            try:
                with SessionLocal() as db:
                    streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                    if not streamer:
                        logger.error(f"Streamer not found: {streamer_id}")
                        return False
                        
                    global_settings = db.query(RecordingSettings).first()
                    if not global_settings or not global_settings.enabled:
                        logger.debug("Recording disabled in global settings")
                        return False
                        
                    streamer_settings = db.query(StreamerRecordingSettings).filter(
                        StreamerRecordingSettings.streamer_id == streamer_id
                    ).first()
                    
                    if not streamer_settings or not streamer_settings.enabled:
                        logger.debug(f"Recording disabled for streamer {streamer.username}")
                        return False
                    
                    # Get quality setting
                    quality = streamer_settings.quality or global_settings.default_quality
                    
                    # Generate output filename
                    filename = self._generate_filename(
                        streamer=streamer,
                        stream_data=stream_data,
                        template=streamer_settings.custom_filename or global_settings.filename_template
                    )
                    
                    output_path = os.path.join(global_settings.output_directory, filename)
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    # Start streamlink process
                    process = await self._start_streamlink(
                        streamer_name=streamer.username,
                        quality=quality,
                        output_path=output_path
                    )
                    
                    if process:
                        self.active_recordings[streamer_id] = {
                            "process": process,
                            "started_at": datetime.now(),
                            "output_path": output_path,
                            "streamer_name": streamer.username,
                            "quality": quality
                        }
                        logger.info(f"Started recording for {streamer.username} at {quality} quality to {output_path}")
                        return True
                        
                    return False
            except Exception as e:
                logger.error(f"Error starting recording: {e}", exc_info=True)
                return False
    
    async def stop_recording(self, streamer_id: int) -> bool:
        """Stop an active recording"""
        async with self.lock:
            if streamer_id not in self.active_recordings:
                logger.debug(f"No active recording for streamer {streamer_id}")
                return False
                
            try:
                recording_info = self.active_recordings.pop(streamer_id)
                process = recording_info["process"]
                
                # Gracefully terminate the process
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=10)
                    except asyncio.TimeoutError:
                        process.kill()
                
                logger.info(f"Stopped recording for {recording_info['streamer_name']}")
                return True
            except Exception as e:
                logger.error(f"Error stopping recording: {e}", exc_info=True)
                return False
    
    async def _start_streamlink(self, streamer_name: str, quality: str, output_path: str) -> Optional[asyncio.subprocess.Process]:
        """Start streamlink process for recording with TS format and post-processing to MP4"""
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
            # Use .ts as intermediate format for better recovery
            ts_output_path = output_path.replace('.mp4', '.ts')
        
            # Streamlink command with optimized settings
            cmd = [
                "streamlink",
                f"twitch.tv/{streamer_name}",
                quality,
                "-o", ts_output_path,
                "--twitch-disable-ads",
                "--hls-live-restart",
                "--hls-segment-threads", "3",
                "--stream-segment-threads", "3",
                "--ringbuffer-size", "32M",
                "--hls-segment-attempts", "5",
                "--hls-timeout", "10",
                "--retry-streams", "3",
                "--retry-max", "5",
                "--retry-open", "3",
                "--hls-segment-queue-threshold", "10",
                "--force"
            ]
        
            logger.debug(f"Starting streamlink: {' '.join(cmd)}")
        
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            # Start monitoring the process output in the background
            asyncio.create_task(self._monitor_process(process, streamer_name, ts_output_path, output_path))
        
            return process
        except Exception as e:
            logger.error(f"Failed to start streamlink: {e}", exc_info=True)
            return None

    async def _monitor_process(self, process: asyncio.subprocess.Process, streamer_name: str, ts_path: str, mp4_path: str) -> None:
        """Monitor recording process and convert TS to MP4 when finished"""
        try:
            stdout, stderr = await process.communicate()
            exit_code = process.returncode
        
            if exit_code == 0 or exit_code == 130:  # 130 is SIGINT (user interruption)
                logger.info(f"Streamlink finished for {streamer_name}, converting TS to MP4")
                # Only remux if TS file exists and has content
                if os.path.exists(ts_path) and os.path.getsize(ts_path) > 0:
                    await self._remux_to_mp4(ts_path, mp4_path)
                else:
                    logger.warning(f"No valid TS file found at {ts_path} for remuxing")
            else:
                stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else "No error output"
                logger.error(f"Streamlink process for {streamer_name} exited with code {exit_code}: {stderr_text}")
                # Try to remux anyway if file exists, it might be partially usable
                if os.path.exists(ts_path) and os.path.getsize(ts_path) > 1000000:  # At least 1MB
                    logger.info(f"Attempting to remux partial recording for {streamer_name}")
                    await self._remux_to_mp4(ts_path, mp4_path)
        except Exception as e:
            logger.error(f"Error monitoring process: {e}", exc_info=True)

    async def _remux_to_mp4(self, ts_path: str, mp4_path: str) -> bool:
        """Remux TS file to MP4 without re-encoding to preserve quality"""
        try:
            cmd = [
                "ffmpeg",
                "-i", ts_path,
                "-c", "copy",  # Copy streams without re-encoding
                "-map", "0",   # Include all streams
                "-movflags", "+faststart",  # Optimize for web streaming
                "-y",          # Overwrite output
                mp4_path
            ]
        
            logger.debug(f"Starting FFmpeg remux: {' '.join(cmd)}")
        
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            stdout, stderr = await process.communicate()
        
            if process.returncode == 0:
                logger.info(f"Successfully remuxed {ts_path} to {mp4_path}")
                # Delete TS file after successful conversion
                os.remove(ts_path)
                return True
            else:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                logger.error(f"FFmpeg remux failed with code {process.returncode}: {stderr_text}")
                return False
        except Exception as e:
            logger.error(f"Error during remux: {e}", exc_info=True)
            return False
FILENAME_PRESETS = {
    "default": "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
    "plex": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{day} - {title}",
    "emby": "{streamer}/S{year}{month}/{streamer} - S{year}{month}E{day} - {title}",
    "jellyfin": "{streamer}/Season {year}{month}/{streamer} - {year}.{month}.{day} - {title}",
    "kodi": "{streamer}/Season {year}-{month}/{streamer} - s{year}e{month}{day} - {title}",
    "chronological": "{year}/{month}/{day}/{streamer} - {title} - {hour}-{minute}"
}

def _generate_filename(self, streamer: Streamer, stream_data: Dict[str, Any], template: str) -> str:
    """Generate a filename from template with variables"""
    now = datetime.now()
    
    # Sanitize values for filesystem safety
    title = self._sanitize_filename(stream_data.get("title", "untitled"))
    game = self._sanitize_filename(stream_data.get("category_name", "unknown"))
    streamer_name = self._sanitize_filename(streamer.username)
    
    # Create a dictionary of replaceable values
    values = {
        "streamer": streamer_name,
        "title": title,
        "game": game,
        "twitch_id": streamer.twitch_id,
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
        "hour": now.strftime("%H"),
        "minute": now.strftime("%M"),
        "second": now.strftime("%S"),
        "timestamp": now.strftime("%Y%m%d_%H%M%S"),
        "datetime": now.strftime("%Y-%m-%d_%H-%M-%S"),
        "id": stream_data.get("id", ""),
        "season": f"S{now.year}-{now.month:02d}"
    }
    
    # Check if template is a preset name
    if template in FILENAME_PRESETS:
        template = FILENAME_PRESETS[template]
    
    # Replace all variables in template
    filename = template
    for key, value in values.items():
        filename = filename.replace(f"{{{key}}}", str(value))
    
    # Ensure the filename ends with .mp4
    if not filename.lower().endswith('.mp4'):
        filename += '.mp4'
        
    return filename
    def _sanitize_filename(self, name: str) -> str:
        """Remove illegal characters from filename"""
        return re.sub(r'[<>:"/\\|?*]', '_', name)
    
    async def get_active_recordings(self) -> List[Dict[str, Any]]:
        """Get a list of all active recordings"""
        async with self.lock:
            return [
                {
                    "streamer_id": streamer_id,
                    "streamer_name": info["streamer_name"],
                    "started_at": info["started_at"].isoformat(),
                    "duration": (datetime.now() - info["started_at"]).total_seconds(),
                    "output_path": info["output_path"],
                    "quality": info["quality"]
                }
                for streamer_id, info in self.active_recordings.items()
            ]
