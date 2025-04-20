import os
import asyncio
import logging
import subprocess
import re
import signal
import json
import tempfile
import copy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any

from app.database import SessionLocal
from app.models import Streamer, RecordingSettings, StreamerRecordingSettings, Stream, StreamEvent, StreamMetadata
from app.config.settings import settings
from app.services.metadata_service import MetadataService
from app.dependencies import websocket_manager

logger = logging.getLogger("streamvault")

class RecordingService:
    def __init__(self):
        self.active_recordings = {}  # streamer_id: process
        self.lock = asyncio.Lock()
        self.metadata_service = MetadataService()
    
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
                            "quality": quality,
                            "stream_id": None  # Will be updated when we find/create the stream
                        }
                        logger.info(f"Started recording for {streamer.username} at {quality} quality to {output_path}")
                        await websocket_manager.send_notification({
                            "type": "recording.started",
                            "data": {
                                "streamer_id": streamer_id,
                                "streamer_name": streamer.username,
                                "started_at": datetime.now().isoformat(),
                                "quality": quality,
                                "output_path": output_path
                            }
                        })
                        
                        # Find the current stream record
                        stream = db.query(Stream).filter(
                            Stream.streamer_id == streamer_id,
                            Stream.ended_at.is_(None)
                        ).order_by(Stream.started_at.desc()).first()
                        
                        if stream:
                            # Create metadata record if it doesn't exist
                            metadata = db.query(StreamMetadata).filter(
                                StreamMetadata.stream_id == stream.id
                            ).first()
                            
                            if not metadata:
                                metadata = StreamMetadata(stream_id=stream.id)
                                db.add(metadata)
                                db.commit()
                            
                            # Update our recording info with stream ID
                            self.active_recordings[streamer_id]["stream_id"] = stream.id
                            
                            # Download Twitch thumbnail asynchronously
                            output_dir = os.path.dirname(output_path)
                            asyncio.create_task(
                                self.metadata_service.download_twitch_thumbnail(
                                    streamer.username, 
                                    stream.id, 
                                    output_dir
                                )
                            )
                        
                        return True
                        
                    return False
            except Exception as e:
                logger.error(f"Error starting recording: {e}", exc_info=True)
                return False
    
    async def stop_recording(self, streamer_id: int) -> bool:
        """Stop an active recording and ensure metadata generation"""
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

                await websocket_manager.send_notification({
                    "type": "recording.stopped",
                    "data": {
                        "streamer_id": streamer_id,
                        "streamer_name": recording_info['streamer_name']
                    }
                })
            
                # Stream ID und "force_started" Flag abrufen
                stream_id = recording_info.get("stream_id")
                force_started = recording_info.get("force_started", False)
            
                # Stelle sicher, dass wir einen Stream haben
                if not stream_id and force_started:
                    with SessionLocal() as db:
                        streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                        if streamer:
                            # Für Force-Recordings: Versuche, einen Stream zu finden
                            stream = db.query(Stream).filter(
                                Stream.streamer_id == streamer_id
                            ).order_by(Stream.started_at.desc()).first()
                        
                            if stream:
                                stream_id = stream.id
            
                # Generate metadata after recording stops
                if stream_id:
                    # Allow some time for the remuxing process to complete
                    asyncio.create_task(self._delayed_metadata_generation(
                        stream_id, 
                        recording_info["output_path"],
                        force_started  # Parameter hinzufügen
                    ))
                else:
                    logger.warning(f"No stream_id available for metadata generation: {recording_info}")
            
                return True
            except Exception as e:
                logger.error(f"Error stopping recording: {e}", exc_info=True)
                return False            
    async def force_start_recording(self, streamer_id: int) -> bool:
        """Manuell eine Aufnahme für einen aktiven Stream starten und volle Metadatengenerierung sicherstellen"""
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    return False
            
                # Prüfen, ob der Streamer live ist
                if not streamer.is_live:
                    logger.error(f"Streamer {streamer.username} is not live")
                    return False
            
                # Aktuellen Stream finden oder erstellen
                stream = db.query(Stream).filter(
                    Stream.streamer_id == streamer_id,
                    Stream.ended_at.is_(None)
                ).order_by(Stream.started_at.desc()).first()
            
                if not stream:
                    # Stream-Eintrag erstellen, wenn keiner existiert
                    # (Dies ist wichtig für die Metadaten-Generierung)
                    logger.info(f"Creating new stream record for {streamer.username}")
                    stream = Stream(
                        streamer_id=streamer_id,
                        twitch_stream_id=f"manual_{int(datetime.now().timestamp())}",
                        title=streamer.title or f"{streamer.username} Stream",
                        category_name=streamer.category_name,
                        language=streamer.language,
                        started_at=datetime.now(timezone.utc),
                        status="online"
                    )
                    db.add(stream)
                    db.commit()
                    db.refresh(stream)
                
                    # Stream-Event für den Start erstellen
                    stream_event = StreamEvent(
                        stream_id=stream.id,
                        event_type="stream.online",
                        timestamp=stream.started_at,
                        title=stream.title,
                        category_name=stream.category_name
                    )
                    db.add(stream_event)
                    db.commit()
            
                # Stream-Daten für die Aufnahme vorbereiten
                stream_data = {
                    "id": stream.twitch_stream_id,
                    "broadcaster_user_id": streamer.twitch_id,
                    "broadcaster_user_name": streamer.username,
                    "started_at": stream.started_at.isoformat() if stream.started_at else datetime.now().isoformat(),
                    "title": stream.title,
                    "category_name": stream.category_name,
                    "language": stream.language
                }
            
                # Prüfen, ob wir bereits eine Aufnahme haben
                if streamer_id in self.active_recordings:
                    logger.info(f"Recording already in progress for {streamer.username}")
                    return True
            
                # Aufnahme mit vorhandener Methode starten
                recording_started = await self.start_recording(streamer_id, stream_data)
            
                # Speichere die Stream-ID in den Aufnahme-Informationen
                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                
                    # Stelle sicher, dass Metadaten erstellt werden
                    self.active_recordings[streamer_id]["force_started"] = True
                
                    logger.info(f"Force recording started for {streamer.username}, stream_id: {stream.id}")
                
                    return True
                
                return recording_started
                
        except Exception as e:
            logger.error(f"Error force starting recording: {e}", exc_info=True)
            return False    
    async def _delayed_metadata_generation(self, stream_id: int, output_path: str, force_started: bool = False, delay: int = 5):
        """Wait for remuxing to complete before generating metadata"""
        try:
            await asyncio.sleep(delay)  # Short delay to ensure remuxing has started
        
            # Check if MP4 file exists (remuxing completed)
            mp4_path = output_path
            if output_path.endswith('.ts'):
                mp4_path = output_path.replace('.ts', '.mp4')
        
            # Wait for the MP4 file to exist with a timeout
            start_time = datetime.now()
            while not os.path.exists(mp4_path):
                if (datetime.now() - start_time).total_seconds() > 300:  # 5 minute timeout
                    logger.warning(f"Timed out waiting for MP4 file: {mp4_path}")
                    # Versuche, die TS-Datei direkt zu verwenden, wenn MP4 nicht erstellt wurde
                    if os.path.exists(output_path) and output_path.endswith('.ts'):
                        mp4_path = output_path
                        logger.info(f"Using TS file directly for metadata: {mp4_path}")
                        break
                    return
                await asyncio.sleep(5)
        
            # Stelle sicher, dass wir einen gültigen Stream haben (besonders für Force-Recordings)
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.error(f"Stream {stream_id} not found for metadata generation")
                    return
                
                if force_started or not stream.ended_at:
                    # Für Force-Recordings oder wenn der Stream noch nicht beendet ist
                    stream.ended_at = datetime.now(timezone.utc)
                    stream.status = "offline"
                    db.commit()
                    logger.info(f"Stream {stream_id} marked as ended for metadata generation")
        
            # Generate metadata
            logger.info(f"Generating metadata for stream {stream_id} at {mp4_path}")
        
            # Stelle sicher, dass wir eine neue Instanz des MetadataService verwenden
            metadata_service = MetadataService()
            await metadata_service.generate_metadata_for_stream(stream_id, mp4_path)
        
            # Stelle sicher, dass ein Thumbnail existiert
            from app.services.thumbnail_service import ThumbnailService
            thumbnail_service = ThumbnailService()
            await thumbnail_service.ensure_thumbnail(stream_id, os.path.dirname(mp4_path))
        
            # Nach der Metadatengenerierung zusätzlich Kapitel erstellen
            with SessionLocal() as db:
                # Hole alle Stream-Events für diesen Stream
                events = db.query(StreamEvent).filter(
                    StreamEvent.stream_id == stream_id
                ).order_by(StreamEvent.timestamp).all()
        
                if events:
                    # Suche Start- und Endzeit
                    stream = db.query(Stream).filter(Stream.id == stream_id).first()
                    if stream and stream.started_at and stream.ended_at:
                        duration = (stream.ended_at - stream.started_at).total_seconds()
                        
                        # Erstelle explizit eine SRT-Datei für Kapitel
                        await self._create_subtitle_chapters(events, duration, mp4_path)
                        logger.info(f"Created chapter subtitle file for recording {stream_id}")
                        
                        # Stelle sicher, dass die Kapitel auch im VTT-Format existieren
                        await metadata_service.generate_chapters_for_stream(stream_id, mp4_path)
                        logger.info(f"Created VTT chapter file for recording {stream_id}")
        
            # Schließe die Metadaten-Session
            await metadata_service.close()
        
        except Exception as e:
            logger.error(f"Error in delayed metadata generation: {e}", exc_info=True)
    
    async def _start_streamlink(self, streamer_name: str, quality: str, output_path: str) -> Optional[asyncio.subprocess.Process]:
        """Start streamlink process for recording with TS format and post-processing to MP4"""
        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
            # Use .ts as intermediate format for better recovery
            ts_output_path = output_path.replace('.mp4', '.ts')
    
            # Adjust the quality string for better resolution selection
            adjusted_quality = quality
            if quality == "best":
                # Use a more specific quality selection string to prioritize highest resolution
                adjusted_quality = "1080p60,1080p,best"
        
            # Streamlink command with optimized settings based on current documentation
            cmd = [
                "streamlink",
                f"twitch.tv/{streamer_name}",
                quality,
                "-o", ts_output_path,
                "--twitch-disable-ads",
                "--hls-live-restart",
                "--stream-segment-threads", "3",
                "--ringbuffer-size", "32M",
                "--stream-segment-timeout", "10",
                "--stream-segment-attempts", "5",
                "--stream-timeout", "60",
                "--retry-streams", "3",
                "--retry-max", "5",
                "--retry-open", "3",
                "--hls-segment-stream-data",
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
    
    async def _create_chapters_file(self, stream_events, duration):
        """Create a chapters file from stream events for ffmpeg"""
        if not stream_events or len(stream_events) < 2:  # Need at least 2 events to make chapters
            return None
            
        # Sort events by timestamp
        events = sorted(stream_events, key=lambda x: x.timestamp)
        
        # Create temp file for chapters
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for i, event in enumerate(events):
                start_time = event.timestamp.timestamp()
                # End time is either the next event or the end of the stream
                end_time = events[i+1].timestamp.timestamp() if i < len(events)-1 else duration
                
                # Format times as HH:MM:SS
                start_str = self._format_timestamp(start_time)
                end_str = self._format_timestamp(end_time)
                
                # Create chapter title from event
                title = f"{event.title or 'Stream'}"
                if event.category_name:
                    title += f" - {event.category_name}"
                
                # Write chapter entry
                f.write(f"CHAPTER{i+1:02d}={start_str}\n")
                f.write(f"CHAPTER{i+1:02d}NAME={title}\n")
            
            return f.name

    async def _create_subtitle_chapters(self, stream_events, duration, output_path):
        """Create a subtitle file with chapter markers for better Plex compatibility"""
        if not stream_events:
            return
        
        # Ensure we have at least a start and end chapter, even if there's only one event
        if len(stream_events) == 1:
            # Create a duplicate event for the end
            end_event = copy.copy(stream_events[0])
            # Set the timestamp to stream duration
            end_event.timestamp = stream_events[0].timestamp + timedelta(seconds=duration)
            stream_events.append(end_event)
            
        # Sort events by timestamp
        events = sorted(stream_events, key=lambda x: x.timestamp)
        
        subtitle_path = output_path.replace('.mp4', '.srt')
        
        with open(subtitle_path, 'w', encoding='utf-8') as f:
            for i, event in enumerate(events):
                start_time = event.timestamp.timestamp()
                # End time is either the next event or the end of the stream
                end_time = events[i+1].timestamp.timestamp() if i < len(events)-1 else duration
                
                # Format for SRT
                start_str = self._format_srt_timestamp(start_time)
                end_str = self._format_srt_timestamp(end_time)
                
                # Create subtitle text (focus on category for chapter marking)
                if event.category_name:
                    title = f"📌 CHAPTER: {event.category_name}"
                else:
                    title = f"📌 TITLE: {event.title or 'Stream'}"
                
                # Write subtitle entry
                f.write(f"{i+1}\n")
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{title}\n\n")
        
        logger.info(f"Created subtitlds):
        """Format seconds to HH:MM:SS.ms format for chapters"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
    
    def _format_srt_timestamp(self, seconds):
        """Format seconds to SRT timestamp format HH:MM:SS,mmm"""
        if seconds < 0:
            seconds = 0
            
        hours = int(seconds // 3600)
        seconds %= 3600
        minutes = int(seconds // 60)
        seconds %= 60
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
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
        """Remux TS file to MP4 without re-encoding to preserve quality and embed chapters"""
        try:
            # Check if we should add chapters
            chapter_file = None
            with SessionLocal() as db:
                # Get global recording settings
                settings = db.query(RecordingSettings).first()
                
                if settings and settings.use_chapters:
                    # Find the stream by output path
                    streamer_name = Path(mp4_path).parts[-2] if len(Path(mp4_path).parts) >= 2 else None
                    if streamer_name:
                        # Get the streamer
                        streamer = db.query(Streamer).filter(Streamer.username == streamer_name).first()
                        if streamer:
                            # Find the most recent stream for this streamer
                            stream = db.query(Stream).filter(
                                Stream.streamer_id == streamer.id
                            ).order_by(Stream.started_at.desc()).first()
                            
                            if stream:
                                # Get stream events
                                events = db.query(StreamEvent).filter(
                                    StreamEvent.stream_id == stream.id
                                ).all()
                                
                                if events:
                                    duration = (datetime.now() - stream.started_at).total_seconds()
                                    chapter_file = await self._create_ffmpeg_chapters_file(events, duration, stream)
                                    logger.debug(f"Created chapter file at {chapter_file} with {len(events)} events")
    
            # Build ffmpeg command
            cmd = [
                "ffmpeg",
                "-i", ts_path
            ]
    
            # Add chapter file if available
            if chapter_file and os.path.exists(chapter_file):
                cmd.extend(["-i", chapter_file, "-map_metadata", "1"])
                logger.debug(f"Using chapter file: {chapter_file}")
        
            # Add the rest of the command
            cmd.extend([
                "-c", "copy",  # Copy streams without re-encoding
                "-map", "0:v",  # Map only video streams
                "-map", "0:a",  # Map only audio streams
                "-ignore_unknown",  # Ignore unknown streams
                "-movflags", "+faststart",  # Optimize for web streaming
                "-y",          # Overwrite output
                mp4_path
            ])
    
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
                # Clean up chapter file
                if chapter_file and os.path.exists(chapter_file):
                    # Behalte die Datei für Debugging
                    # os.remove(chapter_file)
                    pass
                
                # Generate metadata immediately after successful remuxing
                # This ensures all chapter files are created
                mp4_base_path = Path(mp4_path).parent
                mp4_filename = Path(mp4_path).stem
                
                # Only if we have a stream ID
                if 'stream' in locals() and stream:
                    # Import MetadataService here to avoid circular imports
                    from app.services.metadata_service import MetadataService
                    metadata_service = MetadataService()
                    
                    # Generate all metadata including chapter files
                    asyncio.create_task(metadata_service.generate_metadata_for_stream(stream.id, mp4_path))
                    logger.info(f"Triggered metadata and chapter generation for {mp4_path}")
                    
                    # Zusätzlich: Kapitel direkt in die MP4-Datei einbetten
                    asyncio.create_task(self._embed_chapters_in_mp4(mp4_path, stream.id))
                
                return True
            else:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                logger.error(f"FFmpeg remux failed with code {process.returncode}: {stderr_text}")
                return False
        except Exception as e:
            logger.error(f"Error during remux: {e}", exc_info=True)
            return False

    async def _embed_chapters_in_mp4(self, mp4_path: str, stream_id: int):
        """Bettet Kapitel direkt in die MP4-Datei ein"""
        try:
            with SessionLocal() as db:
                # Stream-Events abrufen
                events = db.query(StreamEvent).filter(
                    StreamEvent.stream_id == stream_id
                ).order_by(StreamEvent.timestamp).all()
                
                if not events or len(events) < 2:
                    logger.warning(f"Not enough events to create chapters for stream {stream_id}")
                    return
                
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream {stream_id} not found for chapter embedding")
                    return
                
                # Temporäre Datei für Kapitel erstellen
                chapter_file = await self._create_ffmpeg_chapters_file(events, 
                                                                     (stream.ended_at - stream.started_at).total_seconds() if stream.ended_at else 
                                                                     (datetime.now(timezone.utc) - stream.started_at).total_seconds(), 
                                                                     stream)
                
                if not chapter_file or not os.path.exists(chapter_file):
                    logger.warning(f"Failed to create chapter file for stream {stream_id}")
                    return
                
                # Temporäre Ausgabedatei
                output_path = mp4_path.replace('.mp4', '_chaptered.mp4')
                
                # FFmpeg-Befehl zum Einbetten der Kapitel
                cmd = [
                    "ffmpeg",
                    "-i", mp4_path,
                    "-i", chapter_file,
                    "-map_chapters", "1",  # Kapitel aus der zweiten Eingabedatei verwenden
                    "-map", "0",           # Alle Streams aus der ersten Eingabedatei verwenden
                    "-c", "copy",          # Keine Neukodierung
                    "-y",                  # Überschreiben
                    output_path
                ]
                
                logger.debug(f"Embedding chapters with command: {' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    # Ersetze die ursprüngliche Datei
                    os.replace(output_path, mp4_path)
                    logger.info(f"Successfully embedded chapters in {mp4_path}")
                    
                    # Lösche die temporäre Kapiteldatei
                    if os.path.exists(chapter_file):
                        os.remove(chapter_file)
                else:
                    stderr_text = stderr.decode('utf-8', errors='ignore')
                    logger.error(f"Failed to embed chapters: {stderr_text}")
                    
                    # Lösche die temporäre Ausgabedatei bei Fehler
                    if os.path.exists(output_path):
                        os.remove(output_path)
        except Exception as e:
            logger.error(f"Error embedding chapters in MP4: {e}", exc_info=True)
    async def _create_ffmpeg_chapters_file(self, stream_events, duration, stream):
        """Create a chapters file from stream events for ffmpeg"""
        if not stream_events or len(stream_events) < 1:  # Need at least 1 event for chapters
            return None
            
        # Sort events by timestamp
        events = sorted(stream_events, key=lambda x: x.timestamp)
        
        # Create temp file for chapters
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            # Write FFmpeg metadata header
            f.write(";FFMETADATA1\n")
            
            # Add stream metadata
            if stream.title:
                f.write(f"title={stream.title}\n")
            if hasattr(stream, 'streamer') and stream.streamer and stream.streamer.username:
                f.write(f"artist={stream.streamer.username}\n")
            if stream.started_at:
                f.write(f"date={stream.started_at.strftime('%Y-%m-%d')}\n")
            
            # Write chapter entries
            for i, event in enumerate(events):
                start_time = (event.timestamp - stream.started_at).total_seconds() * 1000 if stream.started_at else 0
                start_time = max(0, start_time)  # Ensure non-negative
                
                # End time is either the next event or the end of the stream
                if i < len(events) - 1:
                    end_time = (events[i+1].timestamp - stream.started_at).total_seconds() * 1000 if stream.started_at else duration * 1000
                else:
                    end_time = duration * 1000 if duration else start_time + (3600 * 1000)  # Default 1 hour
                
                # Create chapter title
                title = event.title or "Stream"
                if event.category_name:
                    title += f" ({event.category_name})"
                
                # Write chapter entry in FFmpeg format
                f.write("\n[CHAPTER]\n")
                f.write("TIMEBASE=1/1000\n")
                f.write(f"START={int(start_time)}\n")
                f.write(f"END={int(end_time)}\n")
                f.write(f"title={title}\n")
        
            return f.name

    def _generate_filename(self, streamer: Streamer, stream_data: Dict[str, Any], template: str) -> str:
        """Generate a filename from template with variables"""
        now = datetime.now()
        
        # Sanitize values for filesystem safety - ensure we have strings
        title = self._sanitize_filename(str(stream_data.get("title", "untitled") or "untitled"))
        game = self._sanitize_filename(str(stream_data.get("category_name", "unknown") or "unknown"))
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

FILENAME_PRESETS = {
    "default": "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
    "plex": "{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{day} - {title}",
    "emby": "{streamer}/S{year}{month}/{streamer} - S{year}{month}E{day} - {title}",
    "jellyfin": "{streamer}/Season {year}{month}/{streamer} - {year}.{month}.{day} - {title}",
    "kodi": "{streamer}/Season {year}-{month}/{streamer} - s{year}e{month}{day} - {title}",
    "chronological": "{year}/{month}/{day}/{streamer} - {title} - {hour}-{minute}"
}
