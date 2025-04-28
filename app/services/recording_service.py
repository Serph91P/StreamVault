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
from sqlalchemy import extract

from app.database import SessionLocal
from app.models import Streamer, RecordingSettings, StreamerRecordingSettings, Stream, StreamEvent, StreamMetadata
from app.config.settings import settings
from app.services.metadata_service import MetadataService
from app.dependencies import websocket_manager

logger = logging.getLogger("streamvault")

# At the top of the file, add this to make RecordingService a singleton
class RecordingService:
    _instance = None  # Make this a class attribute
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RecordingService, cls).__new__(cls)
            cls._instance.active_recordings = {}
            cls._instance.lock = asyncio.Lock()
            cls._instance.metadata_service = MetadataService()
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not hasattr(self, 'initialized'):
            self.initialized = True
            # The actual initialization is now in __new__

    async def get_active_recordings(self) -> List[Dict[str, Any]]:
        """Get a list of all active recordings"""
        async with self.lock:
            # Add verbose logging for debugging
            logger.debug(f"RECORDING STATUS: get_active_recordings called, keys: {list(self.active_recordings.keys())}")
            
            result = [
                {
                    "streamer_id": int(streamer_id),  # Ensure integer type
                    "streamer_name": info["streamer_name"],
                    "started_at": info["started_at"].isoformat() if isinstance(info["started_at"], datetime) else info["started_at"],
                    "duration": (datetime.now() - info["started_at"]).total_seconds() if isinstance(info["started_at"], datetime) else 0,
                    "output_path": info["output_path"],
                    "quality": info["quality"]
                }
                for streamer_id, info in self.active_recordings.items()
            ]
            
            logger.debug(f"RECORDING STATUS: Returning {len(result)} active recordings")
            return result

    async def start_recording(self, streamer_id: int, stream_data: Dict[str, Any]) -> bool:
        """Start recording a stream"""
        async with self.lock:
            # Convert streamer_id to integer for consistency
            streamer_id = int(streamer_id)
            
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
                        
                        # More verbose and consistent logging
                        logger.info(f"Recording started - Added to active_recordings with key {streamer_id}")
                        logger.info(f"Current active recordings: {list(self.active_recordings.keys())}")
                        
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
    
    async def force_start_recording_offline(self, streamer_id: int, stream_data: dict = None) -> bool:
        """
        Startet eine Aufnahme für einen Stream, auch wenn das online Event nicht erkannt wurde.
        Erstellt alle notwendigen Datenbankeinträge, als ob die Anwendung das Event mitbekommen hätte.
        
        Args:
            streamer_id: ID des Streamers
            stream_data: Optionale Stream-Daten, falls bereits bekannt
            
        Returns:
            bool: True wenn erfolgreich, False wenn nicht
        """
        try:
            with SessionLocal() as db:
                streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {streamer_id}")
                    return False
            
                # Prüfen, ob der Streamer tatsächlich live ist (API-Abfrage)
                is_actually_live = False
                twitch_stream_id = None
                title = streamer.title
                category_name = streamer.category_name
                language = streamer.language
            
                # Wenn keine Stream-Daten übergeben wurden, versuchen wir sie von Twitch zu holen
                if not stream_data:
                    try:
                        # Import hier, um zirkuläre Abhängigkeiten zu vermeiden
                        from app.services.streamer_service import StreamerService
                    
                        # Temporäre Session für API-Abfrage
                        streamer_service = StreamerService(db=db, websocket_manager=websocket_manager)
                    
                        # Twitch-API abfragen, um zu prüfen, ob der Streamer tatsächlich live ist
                        stream_info = await streamer_service.get_stream_info(streamer.twitch_id)
                    
                        if stream_info:
                            is_actually_live = True
                            twitch_stream_id = stream_info.get("id")
                            title = stream_info.get("title") or streamer.title
                            category_name = stream_info.get("game_name") or streamer.category_name
                            language = stream_info.get("language") or streamer.language
                            
                            # Stream-Daten für die Aufnahme vorbereiten
                            stream_data = {
                                "id": twitch_stream_id,
                                "broadcaster_user_id": streamer.twitch_id,
                                "broadcaster_user_name": streamer.username,
                                "started_at": stream_info.get("started_at") or datetime.now(timezone.utc).isoformat(),
                                "title": title,
                                "category_name": category_name,
                                "language": language
                            }
                    except Exception as e:
                        logger.warning(f"Failed to get stream info from Twitch API: {e}")
                        # Wir setzen is_actually_live auf True, da der Benutzer explizit eine Aufnahme erzwingen möchte
                        is_actually_live = True
                else:
                    # Wenn Stream-Daten übergeben wurden, nehmen wir an, dass der Stream live ist
                    is_actually_live = True
                    twitch_stream_id = stream_data.get("id", f"manual_{int(datetime.now().timestamp())}")
            
                # Wenn der Stream nicht live ist, aber der Benutzer trotzdem eine Aufnahme erzwingen möchte
                if not is_actually_live:
                    logger.warning(f"Streamer {streamer.username} appears to be offline, but forcing recording anyway")
                
                    # Generiere eine eindeutige Stream-ID
                    twitch_stream_id = f"manual_{int(datetime.now().timestamp())}"
                
                    # Erstelle minimale Stream-Daten
                    if not stream_data:
                        stream_data = {
                            "id": twitch_stream_id,
                            "broadcaster_user_id": streamer.twitch_id,
                            "broadcaster_user_name": streamer.username,
                            "started_at": datetime.now(timezone.utc).isoformat(),
                            "title": title or f"{streamer.username} Stream",
                            "category_name": category_name or "Unknown",
                            "language": language or "en"
                        }
            
                # Aktualisiere den Streamer-Status auf "live"
                streamer.is_live = True
                streamer.last_updated = datetime.now(timezone.utc)
            
                # Aktualisiere Streamer-Informationen, falls vorhanden
                if title:
                    streamer.title = title
                if category_name:
                    streamer.category_name = category_name
                if language:
                    streamer.language = language
            
                # Prüfe, ob bereits ein aktiver Stream existiert
                existing_stream = db.query(Stream).filter(
                    Stream.streamer_id == streamer_id,
                    Stream.ended_at.is_(None)
                ).order_by(Stream.started_at.desc()).first()
            
                if existing_stream:
                    logger.info(f"Found existing active stream for {streamer.username}, using it")
                    stream = existing_stream
                else:
                    # Erstelle einen neuen Stream-Eintrag
                    started_at = datetime.fromisoformat(stream_data["started_at"].replace('Z', '+00:00')) if "started_at" in stream_data else datetime.now(timezone.utc)
                
                    stream = Stream(
                        streamer_id=streamer_id,
                        twitch_stream_id=twitch_stream_id,
                        title=title or f"{streamer.username} Stream",
                        category_name=category_name,
                        language=language,
                        started_at=started_at,
                        status="online"
                    )
                    db.add(stream)
                    db.flush()  # Um die Stream-ID zu erhalten
                
                    # Erstelle Stream-Events
                    # 1. Stream-Online-Event
                    stream_online_event = StreamEvent(
                        stream_id=stream.id,
                        event_type="stream.online",
                        title=title,
                        category_name=category_name,
                        language=language,
                        timestamp=started_at
                    )
                    db.add(stream_online_event)
                
                    # 2. Kategorie-Event (1 Sekunde vor Stream-Start)
                    if category_name:
                        category_event = StreamEvent(
                            stream_id=stream.id,
                            event_type="channel.update",
                            title=title,
                            category_name=category_name,
                            language=language,
                            timestamp=started_at - timedelta(seconds=1)
                        )
                        db.add(category_event)
            
                db.commit()
            
                # Erstelle Metadaten-Eintrag, falls noch nicht vorhanden
                metadata = db.query(StreamMetadata).filter(
                    StreamMetadata.stream_id == stream.id
                ).first()
            
                if not metadata:
                    metadata = StreamMetadata(stream_id=stream.id)
                    db.add(metadata)
                    db.commit()
            
                # WebSocket-Benachrichtigung senden
                await websocket_manager.send_notification({
                    "type": "stream.online",
                    "data": {
                        "streamer_id": streamer.id,
                        "twitch_id": streamer.twitch_id,
                        "streamer_name": streamer.username,
                        "started_at": stream_data.get("started_at", datetime.now(timezone.utc).isoformat()),
                        "title": title,
                        "category_name": category_name,
                        "language": language
                    }
                })
            
                # Starte die Aufnahme mit der vorhandenen Methode
                recording_started = await self.start_recording(streamer_id, stream_data)
            
                # Speichere die Stream-ID in den Aufnahme-Informationen
                if recording_started and streamer_id in self.active_recordings:
                    self.active_recordings[streamer_id]["stream_id"] = stream.id
                    self.active_recordings[streamer_id]["force_started"] = True
                
                    # Versuche, ein Twitch-Thumbnail herunterzuladen
                    output_dir = os.path.dirname(self.active_recordings[streamer_id]["output_path"])
                    asyncio.create_task(
                        self.metadata_service.download_twitch_thumbnail(
                            streamer.username, 
                            stream.id, 
                            output_dir
                        )
                    )
                
                    logger.info(f"Force offline recording started for {streamer.username}, stream_id: {stream.id}")
                    return True
            
                return recording_started
            
        except Exception as e:
            logger.error(f"Error force starting offline recording: {e}", exc_info=True)
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
                    # Try using TS file directly if MP4 wasn't created
                    if os.path.exists(output_path) and output_path.endswith('.ts'):
                        mp4_path = output_path
                        logger.info(f"Using TS file directly for metadata: {mp4_path}")
                        break
                    return
                await asyncio.sleep(5)
        
            # Zusätzliche Wartezeit, um sicherzustellen, dass die Datei vollständig geschrieben wurde
            await asyncio.sleep(10)
        
            # Überprüfen, ob die MP4-Datei gültig ist
            if mp4_path.endswith('.mp4'):
                is_valid = await self._validate_mp4(mp4_path)
                if not is_valid:
                    logger.warning(f"MP4 file is not valid, attempting repair: {mp4_path}")
                    repaired = await self._repair_mp4(output_path.replace('.mp4', '.ts') if os.path.exists(output_path.replace('.mp4', '.ts')) else output_path, mp4_path)
                    if not repaired:
                        logger.error(f"Could not repair MP4 file: {mp4_path}")
                        return
                
                    # Warte nach der Reparatur
                    await asyncio.sleep(5)
        
            # Make sure we have a valid stream (especially for force-started recordings)
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.error(f"Stream {stream_id} not found for metadata generation")
                    return
            
                # Ensure stream is marked as ended
                if force_started or not stream.ended_at:
                    stream.ended_at = datetime.now(timezone.utc)
                    stream.status = "offline"
                    
                    # Check if there are any stream events
                    events_count = db.query(StreamEvent).filter(StreamEvent.stream_id == stream_id).count()
                    
                    # If no events, add at least one event for the stream's category
                    if events_count == 0 and stream.category_name:
                        logger.info(f"No events found for stream {stream_id}, adding initial category event")
                        
                        # Add an event for the stream's category at stream start time
                        category_event = StreamEvent(
                            stream_id=stream_id,
                            event_type="channel.update",
                            title=stream.title,
                            category_name=stream.category_name,
                            language=stream.language,
                            timestamp=stream.started_at
                        )
                        db.add(category_event)
                        
                        # And also add the stream.online event
                        start_event = StreamEvent(
                            stream_id=stream_id,
                            event_type="stream.online",
                            title=stream.title,
                            category_name=stream.category_name,
                            language=stream.language,
                            timestamp=stream.started_at + timedelta(seconds=1)  # 1 second after start
                        )
                        db.add(start_event)
                    db.commit()
                    logger.info(f"Stream {stream_id} marked as ended for metadata generation")
        
            # Generate metadata
            logger.info(f"Generating metadata for stream {stream_id} at {mp4_path}")
        
            # Use a new MetadataService instance
            metadata_service = MetadataService()
        
            # Generate all metadata in one go
            await metadata_service.generate_metadata_for_stream(stream_id, mp4_path)
        
            # Wait briefly to allow all chapter files to be written
            await asyncio.sleep(2)
        
            # Find the FFmpeg chapters file
            ffmpeg_chapters_path = mp4_path.replace('.mp4', '-ffmpeg-chapters.txt')
        
            # Embed all metadata and chapters in a single operation
            if os.path.exists(ffmpeg_chapters_path) and os.path.getsize(ffmpeg_chapters_path) > 0:
                logger.info(f"Embedding all metadata and chapters into MP4 file for stream {stream_id}")
                await metadata_service.embed_all_metadata(mp4_path, ffmpeg_chapters_path, stream_id)
            else:
                logger.warning(f"FFmpeg chapters file not found or empty: {ffmpeg_chapters_path}")
                logger.info(f"Embedding basic metadata without chapters")
                await metadata_service.embed_all_metadata(mp4_path, "", stream_id)
        
            # Close the metadata session
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
        if not stream_events:
            return None
        
        # Ensure we have at least a start and end chapter, even if there's only one event
        if len(stream_events) == 1:
            # Create a duplicate event for the end
            end_event = copy.copy(stream_events[0])
            # Set the timestamp to stream duration
            end_event.timestamp = stream_events[0].timestamp + timedelta(seconds=duration)
            stream_events.append(end_event)
            
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
                if event.category_name:
                    title = f"📌 CHAPTER: {event.category_name}"
                else:
                    title = f"📌 TITLE: {event.title or 'Stream'}"
                
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
        
        # Check if we should use category as chapter title
        use_category_as_title = False
        with SessionLocal() as db:
            settings = db.query(RecordingSettings).first()
            if settings:
                use_category_as_title = settings.use_category_as_chapter_title if hasattr(settings, 'use_category_as_chapter_title') else False
        
        subtitle_path = output_path.replace('.mp4', '.srt')
        
        with open(subtitle_path, 'w', encoding='utf-8') as f:
            for i, event in enumerate(events):
                start_time = event.timestamp.timestamp()
                # End time is either the next event or the end of the stream
                end_time = events[i+1].timestamp.timestamp() if i < len(events)-1 else duration
                
                # Format for SRT
                start_str = self._format_srt_timestamp(start_time)
                end_str = self._format_srt_timestamp(end_time)
                
                # Create subtitle text based on settings
                if use_category_as_title and event.category_name:
                    title = f"📌 CHAPTER: {event.category_name}"
                else:
                    if event.category_name and not use_category_as_title:
                        title = f"📌 TITLE: {event.title or 'Stream'} ({event.category_name})"
                    else:
                        title = f"📌 TITLE: {event.title or 'Stream'}"
                
                # Write subtitle entry
                f.write(f"{i+1}\n")
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{title}\n\n")
        
        logger.info(f"Created subtitle chapter file at {subtitle_path}")
        return subtitle_path
    
    def _format_timestamp(self, seconds):
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
        """Remux TS file to MP4 without re-encoding to preserve quality"""
        try:
            # Verbesserte Remux-Einstellungen für bessere Kompatibilität
            cmd = [
                "ffmpeg",
                "-i", ts_path,
                "-c", "copy",          # Copy streams without re-encoding
                "-map", "0:v",         # Map video streams
                "-map", "0:a",         # Map audio streams
                "-ignore_unknown",     # Ignore unknown streams
                "-movflags", "+faststart+write_colr",  # Optimize for web streaming and color metadata
                "-metadata", f"encoded_by=StreamVault",
                "-metadata", f"encoding_tool=StreamVault",
                "-y",                  # Overwrite output
                mp4_path
            ]
        
            logger.debug(f"Starting enhanced FFmpeg remux: {' '.join(cmd)}")
        
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            stdout, stderr = await process.communicate()
        
            if process.returncode == 0:
                logger.info(f"Successfully remuxed {ts_path} to {mp4_path}")
            
                # Überprüfen, ob die MP4-Datei korrekt erstellt wurde
                if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                    # Überprüfen, ob die moov-Atom vorhanden ist
                    moov_check_cmd = [
                        "ffprobe", 
                        "-v", "error", 
                        "-show_entries", 
                        "format=duration", 
                        "-of", "default=noprint_wrappers=1:nokey=1", 
                        mp4_path
                    ]
                
                    moov_check = await asyncio.create_subprocess_exec(
                        *moov_check_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                
                    moov_stdout, moov_stderr = await moov_check.communicate()
                
                    if moov_check.returncode == 0 and moov_stdout:
                        # MP4 ist gültig, löschen der TS-Datei
                        os.remove(ts_path)
                        logger.info("Enhanced remux completed successfully. Chapters will be added after stream ends.")
                        return True
                    else:
                        logger.warning(f"MP4 file may not be properly finalized. Will try repair: {moov_stderr.decode('utf-8', errors='ignore')}")
                        # Versuchen, die MP4-Datei zu reparieren
                        return await self._repair_mp4(ts_path, mp4_path)
                else:
                    logger.error(f"MP4 file not created or empty: {mp4_path}")
                    return False
            else:
                stderr_text = stderr.decode('utf-4', errors='ignore')
                logger.error(f"FFmpeg remux failed with code {process.returncode}: {stderr_text}")
            
                # Try with even more basic parameters if the first attempt failed
                if "Could not find tag for codec timed_id3" in stderr_text:
                    logger.info("Retrying with more restricted stream mapping due to timed_id3 error")
                    return await self._remux_to_mp4_fallback(ts_path, mp4_path)
            
                return False
        except Exception as e:
            logger.error(f"Error during remux: {e}", exc_info=True)
            return False

    async def _remux_to_mp4_fallback(self, ts_path: str, mp4_path: str) -> bool:
        """Fallback method for remuxing with even more restrictive options"""
        try:
            # Simpler command with explicit stream selection to avoid codec issues
            cmd = [
                "ffmpeg",
                "-i", ts_path,
                "-c", "copy",          # Copy streams without re-encoding
                "-map", "0:v:0",       # Map only the first video stream
                "-map", "0:a:0",       # Map only the first audio stream
                "-ignore_unknown",     # Ignore unknown streams
                "-movflags", "+faststart",  # Optimize for web streaming
                "-y",                  # Overwrite output
                mp4_path
            ]
        
            logger.debug(f"Starting fallback FFmpeg remux: {' '.join(cmd)}")
        
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            stdout, stderr = await process.communicate()
        
            if process.returncode == 0:
                logger.info(f"Successfully remuxed {ts_path} to {mp4_path} using fallback method")
                # Delete TS file after successful conversion
                os.remove(ts_path)
                return True
            else:
                stderr_text = stderr.decode('utf-8', errors='ignore')
                logger.error(f"FFmpeg fallback remux failed with code {process.returncode}: {stderr_text}")
            
                # Save the TS file in case it's valuable
                logger.warning(f"Keeping original TS file at {ts_path} for recovery")
                return False
        except Exception as e:
            logger.error(f"Error during fallback remux: {e}", exc_info=True)
            return False

    async def _repair_mp4(self, ts_path: str, mp4_path: str) -> bool:
        """Versucht, eine beschädigte MP4-Datei zu reparieren"""
        try:
            # Temporäre Datei für die reparierte Version
            repaired_path = mp4_path + ".repaired.mp4"
        
            # Verwende qt-faststart oder MP4Box zur Reparatur
            cmd = [
                "ffmpeg",
                "-i", ts_path,
                "-c", "copy",
                "-movflags", "+faststart+frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4",
                "-y",
                repaired_path
            ]
        
            logger.debug(f"Attempting to repair MP4: {' '.join(cmd)}")
        
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        
            stdout, stderr = await process.communicate()
        
            if process.returncode == 0 and os.path.exists(repaired_path) and os.path.getsize(repaired_path) > 0:
                # Ersetze die ursprüngliche Datei mit der reparierten Version
                os.replace(repaired_path, mp4_path)
                logger.info(f"Successfully repaired MP4 file: {mp4_path}")
            
                # Lösche die TS-Datei, wenn die Reparatur erfolgreich war
                os.remove(ts_path)
                return True
            else:
                logger.error(f"Failed to repair MP4 file: {stderr.decode('utf-8', errors='ignore')}")
            
                # Behalte die TS-Datei für die manuelle Wiederherstellung
                logger.warning(f"Keeping original TS file at {ts_path} for recovery")
                return False
        except Exception as e:
            logger.error(f"Error repairing MP4: {e}", exc_info=True)
            return False

    def _generate_filename(self, streamer: Streamer, stream_data: Dict[str, Any], template: str) -> str:
        """Generate a filename from template with variables"""
        now = datetime.now()
        
        # Sanitize values for filesystem safety
        title = self._sanitize_filename(stream_data.get("title", "untitled"))
        game = self._sanitize_filename(stream_data.get("category_name", "unknown"))
        streamer_name = self._sanitize_filename(streamer.username)
        
        # Get episode number (count of streams in current month)
        episode = "01"  # Default value
        try:
            with SessionLocal() as db:
                # Count streams in the current month for this streamer
                stream_count = db.query(Stream).filter(
                    Stream.streamer_id == streamer.id,
                    extract('year', Stream.started_at) == now.year,
                    extract('month', Stream.started_at) == now.month
                ).count()
                
                # Add 1 for the current stream
                episode = f"{stream_count + 1:02d}"
                logger.debug(f"Calculated episode number for {streamer.username}: {episode}")
        except Exception as e:
            logger.error(f"Error getting episode number: {e}", exc_info=True)
        
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
            "season": f"S{now.year}-{now.month:02d}",
            "episode": episode
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

FILENAME_PRESETS = {
    "default": "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
    "plex": "{streamer}/Season {year}{month}/{streamer} - S{year}{month}E{day} - {title}",
    "emby": "{streamer}/S{year}{month}/{streamer} - S{year}{month}E{day} - {title}",
    "jellyfin": "{streamer}/Season {year}{month}/{streamer} - {year}.{month}.{day} - {title}",
    "kodi": "{streamer}/Season {year}{month}/{streamer} - s{year}e{month}{day} - {title}",
    "chronological": "{year}/{month}/{day}/{streamer} - {title} - {hour}-{minute}"
}
