import os
import json
import aiohttp
import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from app.database import SessionLocal
from app.models import Stream, StreamMetadata, StreamEvent, Streamer
from app.config.settings import settings

logger = logging.getLogger("streamvault")

class MetadataService:
    def __init__(self):
        self.session = None
    
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def generate_metadata_for_stream(self, stream_id: int, mp4_path: str):
        """Generiert alle Metadatendateien für einen Stream"""
        try:
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream with ID {stream_id} not found for metadata generation")
                    return
                
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    logger.warning(f"Streamer not found for stream {stream_id}")
                    return
                
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
                await asyncio.gather(
                    self.generate_json_metadata(stream, streamer, base_path, base_filename, metadata),
                    self.generate_nfo_file(stream, streamer, base_path, base_filename, metadata),
                    self.extract_thumbnail(mp4_path, stream_id),
                    self.generate_chapters_for_stream(stream_id, mp4_path)
                )
                
                db.commit()
                logger.info(f"Generated metadata for stream {stream_id}")
        except Exception as e:
            logger.error(f"Error generating metadata: {e}", exc_info=True)
    
    async def generate_json_metadata(self, stream, streamer, base_path, base_filename, metadata):
        """Erzeugt JSON-Metadatendatei"""
        try:
            json_path = os.path.join(base_path, f"{base_filename}.info.json")
            
            # Stream-Events abrufen
            with SessionLocal() as db:
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
            
            metadata.json_path = json_path
            logger.debug(f"Generated JSON metadata for stream {stream.id} at {json_path}")
        except Exception as e:
            logger.error(f"Error generating JSON metadata: {e}", exc_info=True)
    
    async def generate_nfo_file(self, stream, streamer, base_path, base_filename, metadata):
        """Erzeugt NFO-Datei für Kodi/Plex"""
        try:
            nfo_path = os.path.join(base_path, f"{base_filename}.nfo")
            
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
            tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
            
            metadata.nfo_path = nfo_path
            logger.debug(f"Generated NFO file for stream {stream.id} at {nfo_path}")
        except Exception as e:
            logger.error(f"Error generating NFO file: {e}", exc_info=True)
    
    async def extract_thumbnail(self, video_path: str, stream_id: int = None):
        """Extrahiert das erste Frame des Videos als Thumbnail"""
        if not os.path.exists(video_path):
            logger.warning(f"Video file not found for thumbnail extraction: {video_path}")
            return None
        
        try:
            thumbnail_path = video_path.replace('.mp4', '_thumbnail.jpg')
            
            # FFmpeg-Befehl zum Extrahieren des ersten Frames
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vf", r"select=eq(n\,0)",  # Erstes Frame auswählen
                "-q:v", "2",               # Hohe Qualität
                "-f", "image2",
                "-vframes", "1",
                "-y",                      # Überschreiben bestehender Dateien
                thumbnail_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Prüfen, ob Thumbnail erstellt wurde
            if os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 0:
                logger.info(f"Successfully extracted thumbnail to {thumbnail_path}")
                
                # Metadata aktualisieren, wenn Stream-ID vorhanden
                if stream_id:
                    with SessionLocal() as db:
                        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                        if not metadata:
                            metadata = StreamMetadata(stream_id=stream_id)
                            db.add(metadata)
                        
                        metadata.thumbnail_path = thumbnail_path
                        db.commit()
                
                return thumbnail_path
            else:
                logger.warning(f"Thumbnail extraction failed or produced empty file: {thumbnail_path}")
                if stderr:
                    logger.debug(f"FFmpeg stderr: {stderr.decode('utf-8', errors='ignore')}")
        except Exception as e:
            logger.error(f"Error extracting thumbnail: {e}", exc_info=True)
        
        return None
    
    async def get_stream_thumbnail_url(self, username: str, width: int = 1280, height: int = 720):
        """Generiert Twitch-Vorschaubild-URL für einen Stream"""
        return f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{username}-{width}x{height}.jpg"
    
    async def download_twitch_thumbnail(self, streamer_username: str, stream_id: int, output_dir: str):
        """Lädt das Twitch-Stream-Thumbnail herunter"""
        try:
            # Verzeichnis erstellen
            os.makedirs(output_dir, exist_ok=True)
            thumbnail_path = os.path.join(output_dir, f"{streamer_username}_thumbnail.jpg")
            
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
                        
                        metadata.thumbnail_path = thumbnail_path
                        metadata.thumbnail_url = url
                        db.commit()
                    
                    logger.info(f"Downloaded Twitch thumbnail for stream {stream_id} to {thumbnail_path}")
                    return thumbnail_path
                else:
                    logger.warning(f"Failed to download Twitch thumbnail, status: {response.status}")
        except Exception as e:
            logger.error(f"Error downloading Twitch thumbnail: {e}", exc_info=True)
        
        return None
    
    async def generate_chapters_for_stream(self, stream_id: int, mp4_path: str):
        """Erzeugt Kapitel-Dateien (VTT, SRT, ffmpeg) für einen Stream"""
        try:
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream with ID {stream_id} not found for chapter generation")
                    return
                
                # Stream-Events abrufen (Kategorie-Wechsel usw.)
                events = db.query(StreamEvent).filter(
                    StreamEvent.stream_id == stream_id
                ).order_by(StreamEvent.timestamp).all()
                
                if not events or len(events) < 1:
                    logger.warning(f"No events found for stream {stream_id}, skipping chapter generation")
                    return
                
                # Basispfade für Kapitel
                base_path = Path(mp4_path).parent
                base_filename = Path(mp4_path).stem
                
                # WebVTT-Kapitel erzeugen (für Plex/Browser)
                vtt_path = os.path.join(base_path, f"{base_filename}.chapters.vtt")
                await self._generate_vtt_chapters(stream, events, vtt_path)
                
                # SRT-Kapitel erzeugen (für Kodi/einige Player)
                srt_path = os.path.join(base_path, f"{base_filename}.chapters.srt")
                await self._generate_srt_chapters(stream, events, srt_path)
                
                # FFmpeg Chapters-Datei für zukünftiges Remuxing
                ffmpeg_chapters_path = os.path.join(base_path, f"{base_filename}-ffmpeg-chapters.txt")
                await self._generate_ffmpeg_chapters(stream, events, ffmpeg_chapters_path)
                
                # Metadaten aktualisieren
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                if metadata:
                    metadata.chapters_vtt_path = vtt_path
                    metadata.chapters_srt_path = srt_path
                    metadata.chapters_ffmpeg_path = ffmpeg_chapters_path
                    db.commit()
                
                logger.info(f"Generated chapter files for stream {stream_id}")
        except Exception as e:
            logger.error(f"Error generating chapter files: {e}", exc_info=True)
    
    async def _generate_vtt_chapters(self, stream, events, output_path):
        """Erzeugt WebVTT-Kapitel-Datei"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT - Generated by StreamVault\n\n")
                
                for i, event in enumerate(events):
                    # Start-Zeit des Events
                    start_time = event.timestamp
                    
                    # End-Zeit ist entweder der nächste Event oder das Stream-Ende
                    if i < len(events) - 1:
                        end_time = events[i+1].timestamp
                    elif stream.ended_at:
                        end_time = stream.ended_at
                    else:
                        # Falls kein Ende bekannt ist, nehmen wir 24h nach Start
                        end_time = start_time + timedelta(hours=24)
                    
                    # Berechne Offset in Sekunden
                    if stream.started_at:
                        start_offset = max(0, (start_time - stream.started_at).total_seconds())
                        end_offset = max(0, (end_time - stream.started_at).total_seconds())
                    else:
                        # Fallback, falls start_time nicht bekannt ist
                        start_offset = 0
                        end_offset = 24 * 60 * 60  # 24 Stunden
                    
                    # VTT-Format: HH:MM:SS.mmm
                    start_str = self._format_timestamp_vtt(start_offset)
                    end_str = self._format_timestamp_vtt(end_offset)
                    
                    # Kapitel-Titel erstellen
                    title = event.title or "Stream"
                    if event.category_name:
                        title += f" ({event.category_name})"
                    
                    # Kapitel-Eintrag schreiben
                    f.write(f"{start_str} --> {end_str}\n")
                    f.write(f"{title}\n\n")
                
                logger.info(f"WebVTT chapters file created at {output_path}")
        except Exception as e:
            logger.error(f"Error generating WebVTT chapters: {e}", exc_info=True)
    
    async def _generate_srt_chapters(self, stream, events, output_path):
        """Erzeugt SRT-Kapitel-Datei"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, event in enumerate(events):
                    # Start-Zeit des Events
                    start_time = event.timestamp
                    
                    # End-Zeit ist entweder der nächste Event oder das Stream-Ende
                    if i < len(events) - 1:
                        end_time = events[i+1].timestamp
                    elif stream.ended_at:
                        end_time = stream.ended_at
                    else:
                        # Falls kein Ende bekannt ist, nehmen wir 24h nach Start
                        end_time = start_time + timedelta(hours=24)
                    
                    # Berechne Offset in Sekunden
                    if stream.started_at:
                        start_offset = max(0, (start_time - stream.started_at).total_seconds())
                        end_offset = max(0, (end_time - stream.started_at).total_seconds())
                    else:
                        # Fallback, falls start_time nicht bekannt ist
                        start_offset = 0
                        end_offset = 24 * 60 * 60  # 24 Stunden
                    
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
        except Exception as e:
            logger.error(f"Error generating SRT chapters: {e}", exc_info=True)
    
    async def _generate_ffmpeg_chapters(self, stream, events, output_path):
        """Erzeugt ffmpeg-kompatible Kapitel-Datei"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(";FFMETADATA1\n")
                
                # Stream-Metadaten
                if stream.streamer and stream.streamer.username:
                    f.write(f"artist={stream.streamer.username}\n")
                if stream.title:
                    f.write(f"title={stream.title}\n")
                if stream.started_at:
                    f.write(f"date={stream.started_at.strftime('%Y-%m-%d')}\n")
                
                for i, event in enumerate(events):
                    # Start-Zeit des Events
                    start_time = event.timestamp
                    
                    # End-Zeit ist entweder der nächste Event oder das Stream-Ende
                    if i < len(events) - 1:
                        end_time = events[i+1].timestamp
                    elif stream.ended_at:
                        end_time = stream.ended_at
                    else:
                        # Falls kein Ende bekannt ist, nehmen wir 24h nach Start
                        end_time = start_time + timedelta(hours=24)
                    
                    # Berechne Offset in Millisekunden für ffmpeg
                    if stream.started_at:
                        start_offset_ms = int(max(0, (start_time - stream.started_at).total_seconds() * 1000))
                        end_offset_ms = int(max(0, (end_time - stream.started_at).total_seconds() * 1000))
                    else:
                        # Fallback, falls start_time nicht bekannt ist
                        start_offset_ms = 0
                        end_offset_ms = 24 * 60 * 60 * 1000  # 24 Stunden
                    
                    # Kapitel-Titel erstellen
                    title = event.title or "Stream"
                    if event.category_name:
                        title += f" ({event.category_name})"
                    else:
                        title = "Stream"
                    
                    # Kapitel-Eintrag schreiben
                    f.write("\n[CHAPTER]\n")
                    f.write("TIMEBASE=1/1000\n")
                    f.write(f"START={start_offset_ms}\n")
                    f.write(f"END={end_offset_ms}\n")
                    f.write(f"title={title}\n")
                
                logger.info(f"ffmpeg chapters file created at {output_path}")
        except Exception as e:
            logger.error(f"Error generating ffmpeg chapters: {e}", exc_info=True)
    
    def _format_timestamp_vtt(self, seconds):
        """Formatiert Sekunden ins WebVTT-Format (HH:MM:SS.mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    
    def _format_timestamp_srt(self, seconds):
        """Formatiert Sekunden ins SRT-Format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"