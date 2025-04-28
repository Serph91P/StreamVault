import os
import json
import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import xml.etree.ElementTree as ET

from app.database import SessionLocal
from app.models import Stream, StreamMetadata, StreamEvent, Streamer
from app.config.settings import settings
from sqlalchemy.orm import Session

logger = logging.getLogger("streamvault")

class MetadataService:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Liefert eine aktive HTTP-Session oder erstellt eine neue."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self) -> None:
        """Schließt die HTTP-Session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def generate_metadata_for_stream(self, stream_id: int, mp4_path: str) -> bool:
        """Generiert alle Metadatendateien für einen Stream.
        
        Args:
            stream_id: ID des Streams
            mp4_path: Pfad zur MP4-Datei
            
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream with ID {stream_id} not found for metadata generation")
                    return False
                
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    logger.warning(f"Streamer not found for stream {stream_id}")
                    return False
                
                # Basispfad für Metadaten
                base_path = Path(mp4_path).parent
                base_filename = Path(mp4_path).stem
                
                # Metadaten-Objekt erstellen oder abrufen
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                if not metadata:
                    metadata = StreamMetadata(stream_id=stream_id)
                    db.add(metadata)
                    db.commit()  # Commit here to ensure it exists for later references
                
                # Aufgaben parallel ausführen
                results = await asyncio.gather(
                    self.generate_json_metadata(db, stream, streamer, base_path, base_filename, metadata),
                    self.generate_nfo_file(db, stream, streamer, base_path, base_filename, metadata),
                    self.extract_thumbnail(mp4_path, stream_id, db),
                    self.ensure_all_chapter_formats(stream_id, mp4_path, db)
                )
                
                db.commit()
                logger.info(f"Generated metadata for stream {stream_id}")
                return all(results)
        except Exception as e:
            logger.error(f"Error generating metadata: {e}", exc_info=True)
            return False
    
    async def generate_json_metadata(
        self, 
        db: Session, 
        stream: Stream, 
        streamer: Streamer, 
        base_path: Path, 
        base_filename: str, 
        metadata: StreamMetadata
    ) -> bool:
        """Erzeugt JSON-Metadatendatei.
        
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            json_path = base_path / f"{base_filename}.info.json"
            
            # Stream-Events abrufen
            events = db.query(StreamEvent).filter(StreamEvent.stream_id == stream.id).all()
                
            # Metadaten erstellen
            meta_dict = {
                "id": stream.id,
                "twitch_id": stream.twitch_stream_id,
                "streamer": {
                    "id": stream.streamer_id,
                    "username": streamer.username,
                    "profile_image": streamer.profile_image_url
                },
                "title": stream.title,
                "category": stream.category_name,
                "started_at": stream.started_at.isoformat() if stream.started_at else None,
                "ended_at": stream.ended_at.isoformat() if stream.ended_at else None,
                "duration": (stream.ended_at - stream.started_at).total_seconds() if stream.ended_at and stream.started_at else None,
                "events": [
                    {
                        "type": event.event_type,
                        "title": event.title,
                        "category": event.category_name,
                        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                        "relative_time": (event.timestamp - stream.started_at).total_seconds() if event.timestamp and stream.started_at else None
                    }
                    for event in events
                ]
            }
            
            # JSON speichern
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(meta_dict, f, indent=2)
            
            metadata.json_path = str(json_path)
            logger.debug(f"Generated JSON metadata for stream {stream.id} at {json_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating JSON metadata: {e}", exc_info=True)
            return False
    
    async def generate_nfo_file(
        self, 
        db: Session, 
        stream: Stream, 
        streamer: Streamer, 
        base_path: Path, 
        base_filename: str, 
        metadata: StreamMetadata
    ) -> bool:
        """Erzeugt NFO-Datei für Kodi/Plex.
        
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            nfo_path = base_path / f"{base_filename}.nfo"
            
            # XML-Struktur erstellen
            root = ET.Element("tvshow")
            
            ET.SubElement(root, "title").text = stream.title or f"{streamer.username} Stream"
            ET.SubElement(root, "originaltitle").text = stream.title or f"{streamer.username} Stream"
            ET.SubElement(root, "showtitle").text = f"{streamer.username} Streams"
            
            # Datumsformat für Kodi
            if stream.started_at:
                aired = stream.started_at.strftime("%Y-%m-%d")
                ET.SubElement(root, "aired").text = aired
                ET.SubElement(root, "dateadded").text = stream.started_at.strftime("%Y-%m-%d %H:%M:%S")
            
            # Sprache
            ET.SubElement(root, "language").text = stream.language or "en"
            
            # Stream Info
            plot = f"{streamer.username} streamed"
            if stream.category_name:
                plot += f" {stream.category_name}"
            if stream.started_at:
                plot += f" on {stream.started_at.strftime('%Y-%m-%d')}"
            plot += "."
            
            ET.SubElement(root, "plot").text = plot
            ET.SubElement(root, "outline").text = plot
            
            # Genre/Kategorie
            if stream.category_name:
                ET.SubElement(root, "genre").text = stream.category_name
            
            # Streamer als "actor"
            actor = ET.SubElement(root, "actor")
            ET.SubElement(actor, "name").text = streamer.username
            if streamer.profile_image_url:
                ET.SubElement(actor, "thumb").text = streamer.profile_image_url
            ET.SubElement(actor, "role").text = "Streamer"
            
            # Thumbnail
            if streamer.profile_image_url:
                ET.SubElement(root, "thumb").text = streamer.profile_image_url
            
            # XML schreiben
            tree = ET.ElementTree(root)
            tree.write(str(nfo_path), encoding="utf-8", xml_declaration=True)
            
            metadata.nfo_path = str(nfo_path)
            logger.debug(f"Generated NFO file for stream {stream.id} at {nfo_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating NFO file: {e}", exc_info=True)
            return False
    
    async def extract_thumbnail(
        self, 
        video_path: str, 
        stream_id: Optional[int] = None, 
        db: Optional[Session] = None
    ) -> Optional[str]:
        """Extrahiert das erste Frame des Videos als Thumbnail.
        
        Args:
            video_path: Pfad zur Videodatei
            stream_id: Optional, ID des Streams für Metadaten-Update
            db: Optional, Datenbank-Session
            
        Returns:
            Optional[str]: Pfad zum Thumbnail oder None bei Fehler
        """
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            logger.warning(f"Video file not found for thumbnail extraction: {video_path}")
            return None
        
        try:
            thumbnail_path = video_path_obj.with_suffix('.jpg').with_stem(f"{video_path_obj.stem}_thumbnail")
            
            # FFmpeg-Befehl zum Extrahieren des ersten Frames
            cmd = [
                "ffmpeg",
                "-i", str(video_path_obj),
                "-vf", r"select=eq(n\,0)",  # Erstes Frame auswählen
                "-q:v", "2",               # Hohe Qualität
                "-f", "image2",
                "-vframes", "1",
                "-y",                      # Überschreiben bestehender Dateien
                str(thumbnail_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Prüfen, ob Thumbnail erstellt wurde
            if thumbnail_path.exists() and thumbnail_path.stat().st_size > 0:
                logger.info(f"Successfully extracted thumbnail to {thumbnail_path}")
                
                # Metadata aktualisieren, wenn Stream-ID vorhanden
                if stream_id and db:
                    metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                    if not metadata:
                        metadata = StreamMetadata(stream_id=stream_id)
                        db.add(metadata)
                    
                    metadata.thumbnail_path = str(thumbnail_path)
                    db.commit()
                
                return str(thumbnail_path)
            else:
                logger.warning(f"Thumbnail extraction failed or produced empty file: {thumbnail_path}")
                if stderr:
                    logger.debug(f"FFmpeg stderr: {stderr.decode('utf-8', errors='ignore')}")
        except Exception as e:
            logger.error(f"Error extracting thumbnail: {e}", exc_info=True)
        
        return None
    
    async def get_stream_thumbnail_url(self, username: str, width: int = 1280, height: int = 720) -> str:
        """Generiert Twitch-Vorschaubild-URL für einen Stream.
        
        Returns:
            str: URL zum Twitch-Vorschaubild
        """
        return f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{username}-{width}x{height}.jpg"
    
    async def download_twitch_thumbnail(
        self, 
        streamer_username: str, 
        stream_id: int, 
        output_dir: str
    ) -> Optional[str]:
        """Lädt das Twitch-Stream-Thumbnail herunter.
        
        Returns:
            Optional[str]: Pfad zum heruntergeladenen Thumbnail oder None bei Fehler
        """
        try:
            # Verzeichnis erstellen
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            thumbnail_path = output_path / f"{streamer_username}_thumbnail.jpg"
            
            # URL generieren
            url = await self.get_stream_thumbnail_url(streamer_username)
            
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    with open(thumbnail_path, 'wb') as f:
                        f.write(await response.read())
                    
                    # Metadata aktualisieren
                    with SessionLocal() as db:
                        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                        if not metadata:
                            metadata = StreamMetadata(stream_id=stream_id)
                            db.add(metadata)
                        
                        metadata.thumbnail_path = str(thumbnail_path)
                        metadata.thumbnail_url = url
                        db.commit()
                    
                    logger.info(f"Downloaded Twitch thumbnail for stream {stream_id} to {thumbnail_path}")
                    return str(thumbnail_path)
                else:
                    logger.warning(f"Failed to download Twitch thumbnail, status: {response.status}")
        except Exception as e:
            logger.error(f"Error downloading Twitch thumbnail: {e}", exc_info=True)
        
        return None
    
    async def ensure_all_chapter_formats(
        self, 
        stream_id: int, 
        mp4_path: str, 
        db: Optional[Session] = None
    ) -> Optional[Dict[str, str]]:
        """Stellt sicher, dass Kapitel in allen gängigen Formaten erstellt werden.
        
        Args:
            stream_id: ID des Streams
            mp4_path: Pfad zur MP4-Datei
            db: Optional, Datenbank-Session
            
        Returns:
            Optional[Dict[str, str]]: Dictionary mit Pfaden zu allen erstellten Kapitelformaten oder None bei Fehler
        """
        try:
            # Verwende übergebene Session oder erstelle eine neue
            close_db = False
            if db is None:
                db = SessionLocal()
                close_db = True
                
            try:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream with ID {stream_id} not found for chapter generation")
                    return None
                
                # Stream-Events abrufen (Kategorie-Wechsel usw.)
                events = db.query(StreamEvent).filter(
                    StreamEvent.stream_id == stream_id
                ).order_by(StreamEvent.timestamp).all()
                
                if not events or len(events) < 1:
                    logger.warning(f"No events found for stream {stream_id}, skipping chapter generation")
                    return None
                
                # Basispfade für Kapitel
                mp4_path_obj = Path(mp4_path)
                base_path = mp4_path_obj.parent
                base_filename = mp4_path_obj.stem
                
                # 1. WebVTT-Kapitel (für Plex/Browser)
                vtt_path = base_path / f"{base_filename}.vtt"
                await self._generate_vtt_chapters(stream, events, vtt_path)
                
                # 2. Exakte Dateinamen-Kopie für Plex
                exact_vtt_path = mp4_path_obj.with_suffix('.vtt')
                if exact_vtt_path != vtt_path:
                    import shutil
                    shutil.copy2(vtt_path, exact_vtt_path)
                
                # 3. SRT-Kapitel (für Kodi/einige Player)
                srt_path = base_path / f"{base_filename}.srt"
                await self._generate_srt_chapters(stream, events, srt_path)
                
                # 4. FFmpeg Chapters-Datei
                ffmpeg_chapters_path = base_path / f"{base_filename}-ffmpeg-chapters.txt"
                await self._generate_ffmpeg_chapters(stream, events, ffmpeg_chapters_path)
                
                # 5. Emby/Jellyfin XML Chapters
                xml_chapters_path = base_path / f"{base_filename}.xml"
                await self._generate_xml_chapters(stream, events, xml_chapters_path)
                
                # Metadaten aktualisieren
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                if metadata:
                    metadata.chapters_vtt_path = str(vtt_path)
                    metadata.chapters_srt_path = str(srt_path)
                    metadata.chapters_ffmpeg_path = str(ffmpeg_chapters_path)
                    db.commit()
                
                logger.info(f"Generated all chapter formats for stream {stream_id}")
                return {
                    "vtt": str(vtt_path),
                    "srt": str(srt_path),
                    "ffmpeg": str(ffmpeg_chapters_path),
                    "xml": str(xml_chapters_path)
                }
            finally:
                if close_db:
                    db.close()
        except Exception as e:
            logger.error(f"Error generating all chapter formats: {e}", exc_info=True)
            return None
    
    async def _generate_vtt_chapters(self, stream: Stream, events: List[StreamEvent], output_path: Path) -> bool:
        """Erzeugt WebVTT-Kapitel-Datei.
        
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            # Sort events by timestamp to ensure proper order
            events = sorted(events, key=lambda x: x.timestamp)
            
            # Calculate stream duration and handle pre-stream events
            stream_duration, events = self._prepare_events_and_duration(stream, events)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT - Generated by StreamVault\n\n")
                
                # Always create at least one meaningful chapter
                if len(events) <= 1:
                    # Just one event - create a chapter for the entire stream
                    self._write_single_chapter(f, events, stream_duration)
                else:
                    # Multiple events - create chapters for each event
                    self._write_multiple_chapters(f, events, stream)
                
                logger.info(f"WebVTT chapters file created at {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating WebVTT chapters: {e}", exc_info=True)
            return False
    
    def _prepare_events_and_duration(
        self, 
        stream: Stream, 
        events: List[StreamEvent]
    ) -> Tuple[float, List[StreamEvent]]:
        """Bereitet Events vor und berechnet die Stream-Dauer.
        
        Returns:
            Tuple[float, List[StreamEvent]]: Stream-Dauer in Sekunden und vorbereitete Events
        """
        # Calculate stream duration
        duration = 0
        if stream.started_at and stream.ended_at:
            duration = (stream.ended_at - stream.started_at).total_seconds()
            logger.debug(f"Stream duration: {duration} seconds")
        
        # Add verification for events with timestamps before stream start
        if stream.started_at:
            # Process pre-stream events if they exist
            has_pre_stream_events = any(event.timestamp < stream.started_at for event in events)
            
            # If all events are pre-stream, artificially add stream start event
            if has_pre_stream_events and all(event.timestamp < stream.started_at for event in events):
                logger.info(f"All events for stream {stream.id} are pre-stream, adding stream start event")
                
                # Create an artificial stream start event
                start_event = type('Event', (), {
                    'timestamp': stream.started_at,
                    'title': stream.title or "Stream Start",
                    'category_name': stream.category_name or "Unknown",
                    'event_type': 'stream.start'
                })
                events.append(start_event)
                events = sorted(events, key=lambda x: x.timestamp)
        
        return duration, events
    
    def _write_single_chapter(self, file_obj: Any, events: List[StreamEvent], duration: float) -> None:
        """Schreibt ein einzelnes Kapitel für den gesamten Stream.
        
        Args:
            file_obj: Geöffnetes Datei-Objekt
            events: Liste der Events
            duration: Stream-Dauer in Sekunden
        """
        start_offset = 0
        end_offset = duration if duration > 0 else 127  # Default 2 minutes + 7 seconds if no duration info
    
        start_str = self._format_timestamp_vtt(start_offset)
        end_str = self._format_timestamp_vtt(end_offset)
        
        title = events[0].title or "Stream" if events else "Stream"
        if events and events[0].category_name:
            title += f" ({events[0].category_name})"
        
        file_obj.write(f"{start_str} --> {end_str}\n")
        file_obj.write(f"{title}\n\n")
        
        logger.info(f"Created single chapter covering entire stream duration: {start_offset} to {end_offset} seconds")
    
    def _write_multiple_chapters(self, file_obj: Any, events: List[StreamEvent], stream: Stream) -> None:
        """Schreibt mehrere Kapitel für verschiedene Events.
        
        Args:
            file_obj: Geöffnetes Datei-Objekt
            events: Liste der Events
            stream: Stream-Objekt
        """
        for i, event in enumerate(events):
            # Determine start and end times
            start_offset, end_offset = self._calculate_chapter_timestamps(i, event, events, stream)
            
            # Format timestamps
            start_str = self._format_timestamp_vtt(start_offset)
            end_str = self._format_timestamp_vtt(end_offset)
            
            # Create title
            title = event.title or "Stream"
            if event.category_name:
                title += f" ({event.category_name})"
            
            # Write chapter
            file_obj.write(f"{start_str} --> {end_str}\n")
            file_obj.write(f"{title}\n\n")
            
            logger.debug(f"Created chapter from {start_offset} to {end_offset} seconds: {title}")
    
    def _calculate_chapter_timestamps(
        self, 
        index: int, 
        event: StreamEvent, 
        events: List[StreamEvent], 
        stream: Stream
    ) -> Tuple[float, float]:
        """Berechnet Start- und Endzeit eines Kapitels.
        
        Args:
            index: Index des aktuellen Events
            event: Aktuelles Event
            events: Liste aller Events
            stream: Stream-Objekt
            
        Returns:
            Tuple[float, float]: Start- und Endzeit in Sekunden
        """
        # Determine start time - ensure non-negative
        if stream.started_at:
            if event.timestamp < stream.started_at:
                # Handle pre-stream events by setting offset to 0
                start_offset = 0
            else:
                start_offset = max(0, (event.timestamp - stream.started_at).total_seconds())
        else:
            start_offset = 0
        
        # Determine end time (next event or stream end)
        if index < len(events) - 1:
            next_event = events[index+1]
            if stream.started_at:
                if next_event.timestamp < stream.started_at:
                    # Another pre-stream event
                    end_offset = 0
                else:
                    end_offset = max(start_offset + 1, (next_event.timestamp - stream.started_at).total_seconds())
            else:
                end_offset = start_offset + 60  # Default 1 minute if no timestamps
        elif stream.ended_at and stream.started_at:
            end_offset = (stream.ended_at - stream.started_at).total_seconds()
        else:
            end_offset = start_offset + 127  # Default 2 minutes + 7 seconds
        
        # Ensure valid chapter duration (minimum 1 second)
        if end_offset <= start_offset:
            end_offset = start_offset + 1
            
        return start_offset, end_offset
    
    async def _generate_srt_chapters(self, stream: Stream, events: List[StreamEvent], output_path: Path) -> bool:
        """Erzeugt SRT-Kapitel-Datei.
        
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            # Sort events by timestamp
            events = sorted(events, key=lambda x: x.timestamp)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, event in enumerate(events):
                    # Berechne Start- und Endzeit
                    start_offset, end_offset = self._calculate_srt_timestamps(i, event, events, stream)
                    
                    # SRT-Format: HH:MM:SS,mmm
                    start_str = self._format_timestamp_srt(start_offset)
                    end_str = self._format_timestamp_srt(end_offset)
                    
                    # Kapitel-Titel erstellen
                    title = event.title or "Stream"
                    if event.category_name:
                        title += f" ({event.category_name})"
                    
                    # Kapitel-Eintrag schreiben
                    f.write(f"{i+1}\n")
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{title}\n\n")
                
                logger.info(f"SRT chapters file created at {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating SRT chapters: {e}", exc_info=True)
            return False
    
    def _calculate_srt_timestamps(
        self, 
        index: int, 
        event: StreamEvent, 
        events: List[StreamEvent], 
        stream: Stream
    ) -> Tuple[float, float]:
        """Berechnet Start- und Endzeit eines SRT-Kapitels.
        
        Returns:
            Tuple[float, float]: Start- und Endzeit in Sekunden
        """
        # Start-Zeit des Events
        start_time = event.timestamp
        
        # End-Zeit ist entweder der nächste Event oder das Stream-Ende
        if index < len(events) - 1:
            end_time = events[index+1].timestamp
        elif stream.ended_at:
            end_time = stream.ended_at
        else:
            # Falls kein Ende bekannt ist, nehmen wir 24h nach Start
            end_time = start_time + timedelta(hours=24)
        
        # Berechne Offset in Sekunden - ensure non-negative values
        if stream.started_at:
            # For pre-stream events, set their start time to 0 but keep their original duration
            if start_time < stream.started_at:
                start_offset = 0
            else:
                start_offset = max(0, (start_time - stream.started_at).total_seconds())
            
            # Always ensure end offset is after start offset and at least 1 second duration
            end_offset = max(start_offset + 1, (end_time - stream.started_at).total_seconds())
        else:
            # Fallback, falls start_time nicht bekannt ist
            start_offset = 0
            end_offset = 24 * 60 * 60  # 24 Stunden
            
        return start_offset, end_offset
    
    async def _generate_ffmpeg_chapters(self, stream: Stream, events: List[StreamEvent], output_path: Path) -> bool:
        """Erzeugt ffmpeg-kompatible Kapitel-Datei.
        
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(";FFMETADATA1\n")
                
                # Stream-Metadaten
                if stream.title:
                    f.write(f"title={stream.title}\n")
                
                # Streamer-Informationen abrufen (Stream hat nur streamer_id, nicht streamer)
                streamer_username = None
                with SessionLocal() as db:
                    streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                    if streamer:
                        streamer_username = streamer.username
                
                if streamer_username:
                    f.write(f"artist={streamer_username}\n")
                
                if stream.started_at:
                    f.write(f"date={stream.started_at.strftime('%Y-%m-%d')}\n")
                
                # Sortierte Events, um Duplikate zu eliminieren
                sorted_events = sorted(events, key=lambda x: x.timestamp)
                filtered_events = []
                
                # Entferne Events mit gleicher Kategorie in Folge
                last_category = None
                for event in sorted_events:
                    if event.category_name != last_category:
                        filtered_events.append(event)
                        last_category = event.category_name
                
                # Wenn wir keine Events haben, füge ein Standard-Kapitel hinzu
                if not filtered_events and stream.category_name:
                    # Create a dummy event for the entire stream
                    dummy_event = type('Event', (), {
                        'timestamp': stream.started_at,
                        'title': stream.title,
                        'category_name': stream.category_name
                    })
                    filtered_events.append(dummy_event)
                
                for i, event in enumerate(filtered_events):
                    # Berechne Start- und Endzeit
                    start_offset_ms, end_offset_ms = self._calculate_ffmpeg_timestamps(i, event, filtered_events, stream)
                    
                    # Kapitel-Titel erstellen
                    if event.category_name:
                        title = f"{event.category_name}"
                    elif event.title:
                        title = f"{event.title}"
                    else:
                        title = "Stream"
                    
                    # Kapitel-Eintrag schreiben
                    f.write("\n[CHAPTER]\n")
                    f.write("TIMEBASE=1/1000\n")
                    f.write(f"START={start_offset_ms}\n")
                    f.write(f"END={end_offset_ms}\n")
                    f.write(f"title={title}\n")
                
                logger.info(f"ffmpeg chapters file created at {output_path}")
                return True
            
        except Exception as e:
            logger.error(f"Error generating ffmpeg chapters: {e}", exc_info=True)
            return False
    
    def _calculate_ffmpeg_timestamps(
        self, 
        index: int, 
        event: Any, 
        events: List[Any], 
        stream: Stream
    ) -> Tuple[int, int]:
        """Berechnet Start- und Endzeit eines FFmpeg-Kapitels in Millisekunden.
        
        Returns:
            Tuple[int, int]: Start- und Endzeit in Millisekunden
        """
        # Start-Zeit des Events
        start_time = event.timestamp
        
        # End-Zeit ist entweder der nächste Event oder das Stream-Ende
        if index < len(events) - 1:
            end_time = events[index+1].timestamp
        elif stream.ended_at:
            end_time = stream.ended_at
        else:
            # Falls kein Ende bekannt ist, nehmen wir 24h nach Start
            end_time = start_time + timedelta(hours=24)
        
        # Berechne Offset in Millisekunden für ffmpeg (mindestens 1000 ms Dauer)
        if stream.started_at:
            start_offset_ms = int(max(0, (start_time - stream.started_at).total_seconds() * 1000))
            end_offset_ms = int(max(start_offset_ms + 1000, (end_time - stream.started_at).total_seconds() * 1000))
        else:
            # Fallback, falls start_time nicht bekannt ist
            start_offset_ms = 0
            end_offset_ms = 24 * 60 * 60 * 1000  # 24 Stunden
            
        return start_offset_ms, end_offset_ms
    
    async def _generate_xml_chapters(self, stream: Stream, events: List[StreamEvent], output_path: Path) -> bool:
        """Erzeugt XML-Kapitel-Datei für Emby/Jellyfin.
        
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            # XML-Struktur erstellen
            root = ET.Element("Chapters")
            
            for i, event in enumerate(events):
                # Berechne Start- und Endzeit
                start_offset_ms, end_offset_ms = self._calculate_ffmpeg_timestamps(i, event, events, stream)
                
                # Kapitel-Element erstellen
                chapter = ET.SubElement(root, "Chapter")
                chapter_name = event.title or "Stream"
                if event.category_name:
                    chapter_name += f" ({event.category_name})"
                
                ET.SubElement(chapter, "Name").text = chapter_name
                
                # Start- und Endzeit in Millisekunden
                ET.SubElement(chapter, "StartTime").text = str(int(start_offset_ms))
                ET.SubElement(chapter, "EndTime").text = str(int(end_offset_ms))
            
            # XML schreiben
            tree = ET.ElementTree(root)
            tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
            
            logger.info(f"XML chapters file created at {output_path} with {len(events)} chapters")
            return True
        except Exception as e:
            logger.error(f"Error generating XML chapters: {e}", exc_info=True)
            return False
    
    def _format_timestamp_vtt(self, seconds: float) -> str:
        """Formatiert Sekunden ins WebVTT-Format (HH:MM:SS.mmm).
        
        Returns:
            str: Formatierter Zeitstempel
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def _format_timestamp_srt(self, seconds: float) -> str:
        """Formatiert Sekunden ins SRT-Format (HH:MM:SS,mmm).
        
        Returns:
            str: Formatierter Zeitstempel
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
    
    async def import_manual_chapters(
        self, 
        stream_id: int, 
        chapters_txt_path: str, 
        mp4_path: str
    ) -> Optional[Dict[str, str]]:
        """Importiert manuell erstellte Kapitel aus einer Textdatei und erstellt alle Formate.
        
        Returns:
            Optional[Dict[str, str]]: Dictionary mit Pfaden zu allen erstellten Kapitelformaten oder None bei Fehler
        """
        try:
            chapters_path = Path(chapters_txt_path)
            if not chapters_path.exists():
                logger.warning(f"Chapters text file not found: {chapters_txt_path}")
                return None
                
            # Basispfade für Kapitel
            mp4_path_obj = Path(mp4_path)
            base_path = mp4_path_obj.parent
            base_filename = mp4_path_obj.stem
            
            # FFmpeg Chapters-Datei
            ffmpeg_chapters_path = base_path / f"{base_filename}-ffmpeg-chapters.txt"
            
            # Kapitel aus der Textdatei lesen
            chapters = []
            with open(chapters_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Format: 0:23:20 Start
                    import re
                    match = re.match(r"(\d+):(\d{2}):(\d{2}) (.*)", line.strip())
                    if match:
                        hrs = int(match.group(1))
                        mins = int(match.group(2))
                        secs = int(match.group(3))
                        title = match.group(4)
                        
                        # Zeit in Millisekunden umrechnen
                        total_seconds = (hrs * 3600) + (mins * 60) + secs
                        timestamp_ms = total_seconds * 1000
                        
                        chapters.append({
                            "title": title,
                            "startTime": timestamp_ms
                        })
            
            # Keine Kapitel gefunden
            if not chapters:
                logger.warning(f"No chapters found in {chapters_path}")
                return None
                
            # Stream-Events aus den manuellen Kapiteln erstellen
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream with ID {stream_id} not found")
                    return None
                    
                # Bestehende Events löschen
                db.query(StreamEvent).filter(StreamEvent.stream_id == stream_id).delete()
                
                # Neue Events aus manuellen Kapiteln erstellen
                for i, chapter in enumerate(chapters):
                    # Zeitstempel berechnen
                    if stream.started_at:
                        timestamp = stream.started_at + timedelta(milliseconds=chapter["startTime"])
                    else:
                        # Fallback, wenn keine Startzeit bekannt ist
                        timestamp = datetime.now() - timedelta(seconds=chapter["startTime"]/1000)
                    
                    # Event erstellen
                    event = StreamEvent(
                        stream_id=stream_id,
                        event_type="manual.chapter",
                        title=chapter["title"],
                        timestamp=timestamp
                    )
                    db.add(event)
                
                db.commit()
                
                # Alle Kapitelformate mit den neuen Events erstellen
                return await self.ensure_all_chapter_formats(stream_id, mp4_path, db)
        except Exception as e:
            logger.error(f"Error importing manual chapters: {e}", exc_info=True)
            return None

    async def embed_all_metadata(self, mp4_path: str, chapters_path: str, stream_id: int) -> bool:
        """Bettet sowohl Kapitel als auch alle anderen Metadaten in einem Durchgang ein.
        
        Args:
            mp4_path: Pfad zur MP4-Datei
            chapters_path: Pfad zur FFmpeg-Kapitel-Datei
            stream_id: Stream-ID für zusätzliche Metadaten
        
        Returns:
            bool: True bei Erfolg, False bei Fehler
        """
        try:
            mp4_path_obj = Path(mp4_path)
            
            if not mp4_path_obj.exists():
                logger.warning(f"MP4 file not found for metadata embedding: {mp4_path}")
                return False
            
            # Initialisiere chapters_path_obj
            chapters_path_obj = Path(chapters_path) if chapters_path else None
            
            # Stream und Streamer Informationen abrufen
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream {stream_id} not found for metadata embedding")
                    return False
                
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    logger.warning(f"Streamer not found for stream {stream_id}")
                    return False
            
            # Erstelle temporäre Metadaten-Datei mit allen Metadaten
            meta_path = mp4_path_obj.with_name(f"{mp4_path_obj.stem}-combined-metadata.txt")
            
            with open(meta_path, 'w', encoding='utf-8') as f:
                f.write(";FFMETADATA1\n")
            
                # Grundlegende Metadaten
                metadata = {
                    "title": stream.title or f"{streamer.username} Stream",
                    "artist": streamer.username,
                    "album_artist": streamer.username,
                    "album": f"{streamer.username} Streams",
                    "genre": stream.category_name or "Livestream",
                    "date": stream.started_at.strftime("%Y-%m-%d") if stream.started_at else datetime.now().strftime("%Y-%m-%d"),
                    "comment": f"Stream recorded by StreamVault | Category: {stream.category_name or 'Unknown'}",
                    "show": f"{streamer.username} Streams",
                    "network": "Twitch",
                    "language": stream.language or "en",
                    # Plex-spezifische Tags
                    "media_type": "tvshow",
                    "year": stream.started_at.strftime("%Y") if stream.started_at else datetime.now().strftime("%Y"),
                    "episode_id": f"S{stream.started_at.strftime('%Y%m%d') if stream.started_at else datetime.now().strftime('%Y%m%d')}",
                    "season_number": stream.started_at.strftime("%Y%m") if stream.started_at else datetime.now().strftime("%Y%m"),
                    "episode_sort": stream.started_at.strftime("%d") if stream.started_at else datetime.now().strftime("%d"),
                    "encoded_by": "StreamVault",
                    "encoding_tool": "StreamVault"
                }
            
                # Metadaten schreiben
                for key, value in metadata.items():
                    if value:  # Nur schreiben, wenn ein Wert vorhanden ist
                        # Escape special characters
                        value_escaped = str(value).replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\\", "\\\\")
                        f.write(f"{key}={value_escaped}\n")
            
                # Kapitel hinzufügen, wenn Kapitel-Datei existiert
                if chapters_path_obj and chapters_path_obj.exists() and chapters_path_obj.stat().st_size > 0:
                    with open(chapters_path_obj, 'r', encoding='utf-8') as cf:
                        chapter_lines = cf.readlines()
                    
                    # Nur die [CHAPTER] Abschnitte hinzufügen, Header überspringen
                    in_header = True
                    for line in chapter_lines:
                        if line.strip() == "" and in_header:
                            in_header = False
                        elif not in_header:
                            f.write(line)
                else:
                    logger.warning(f"No valid chapters file available: {chapters_path}")
            
            # Temporäre Ausgabedatei
            output_path = mp4_path_obj.with_name(f"{mp4_path_obj.stem}_metadata_complete{mp4_path_obj.suffix}")
            
            # FFmpeg-Befehl zum Einbetten aller Metadaten
            cmd = [
                "ffmpeg",
                "-i", str(mp4_path_obj),
                "-i", str(meta_path),
                "-map_metadata", "1",   # Metadaten aus der zweiten Datei
                "-map_chapters", "1",   # Kapitel aus der zweiten Datei
                "-codec", "copy",       # Keine Neukodierung
                "-map", "0",            # Alle Streams beibehalten
                "-movflags", "+faststart+write_colr",  # Optimierung für Web-Streaming
                "-metadata:s:v:0", "title=Video",
                "-metadata:s:a:0", "title=Audio",
                "-y",                   # Überschreiben falls die Datei existiert
                str(output_path)
            ]
            
            logger.debug(f"Running FFmpeg to embed all metadata: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                # Validiere die Ausgabedatei
                check_cmd = [
                    "ffprobe",
                    "-v", "error", 
                    "-show_entries",
                    "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(output_path)
                ]
                
                check_process = await asyncio.create_subprocess_exec(
                    *check_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                check_stdout, check_stderr = await check_process.communicate()
                
                if check_process.returncode == 0 and check_stdout:
                    # Ersetze die ursprüngliche Datei mit der neuen
                    output_path.replace(mp4_path_obj)
                    logger.info(f"Successfully embedded all metadata into {mp4_path}")
                    
                    # Lösche temporäre Dateien
                    if meta_path.exists():
                        meta_path.unlink()
                    
                    return True
                else:
                    stderr_text = check_stderr.decode('utf-8', errors='ignore') if check_stderr else "No error output"
                    logger.error(f"Output file validation failed: {stderr_text}")
                    return False
            else:
                stderr_text = stderr.decode('utf-8', errors='ignore') if stderr else "No error output"
                logger.error(f"Failed to embed metadata: {stderr_text}")
                return False
        except Exception as e:
            logger.error(f"Error embedding all metadata: {e}", exc_info=True)
            return False


    def _format_xml_time(self, seconds: float) -> str:
        """Formatiert Sekunden in das XML-Format für MP4Box/Matroska: HH:MM:SS.nnnnnnnnn.
        
        Returns:
            str: Formatierter Zeitstempel
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:09.6f}"
