import aiohttp
import os
from pathlib import Path
import asyncio
import logging
import time
from PIL import Image
import io
from datetime import datetime

from app.database import SessionLocal
from app.models import Stream, StreamMetadata

logger = logging.getLogger("streamvault")

class ThumbnailService:
    def __init__(self):
        self.session = None
    
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def get_stream_thumbnail(self, username: str, width: int = 1280, height: int = 720):
        """Generiert Twitch-Vorschaubild-URL für einen laufenden Stream"""
        # Füge einen Timestamp-Parameter hinzu, um Caching zu vermeiden
        timestamp = int(time.time())
        return f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{username}-{width}x{height}.jpg?t={timestamp}"    
    async def download_thumbnail(self, stream_id: int, output_dir: str, max_retries=3, retry_delay=2):
        """Lädt das Stream-Thumbnail herunter mit Wiederholungsversuchen"""
        with SessionLocal() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if not stream or not stream.streamer:
                return None
            
            # Verzeichnis erstellen
            os.makedirs(output_dir, exist_ok=True)
            
            # Eindeutigen Dateinamen erstellen mit Stream-ID und Datum
            date_str = stream.started_at.strftime("%Y%m%d") if stream.started_at else datetime.now().strftime("%Y%m%d")
            thumbnail_path = os.path.join(output_dir, f"{stream.streamer.username}_stream_{stream_id}_{date_str}_thumbnail.jpg")
            
            # Mehrere Versuche, um das Thumbnail zu bekommen
            for attempt in range(max_retries):
                try:
                    # URL generieren mit neuem Timestamp bei jedem Versuch
                    url = await self.get_stream_thumbnail(stream.streamer.username)
                    
                    session = await self._get_session()
                    async with session.get(url) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            
                            # Prüfen, ob das Bild ein Platzhalter ist (graue Kamera)
                            if await self._is_placeholder_image(image_data):
                                logger.warning(f"Received placeholder image for {stream.streamer.username}, retrying in {retry_delay}s (attempt {attempt+1}/{max_retries})")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(retry_delay)
                                    continue
                            
                            # Bild speichern
                            with open(thumbnail_path, 'wb') as f:
                                f.write(image_data)
                            
                            # Metadata aktualisieren
                            metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                            if not metadata:
                                metadata = StreamMetadata(stream_id=stream_id)
                                db.add(metadata)
                            
                            metadata.thumbnail_path = thumbnail_path
                            metadata.thumbnail_url = url
                            db.commit()
                            
                            logger.info(f"Downloaded thumbnail for stream {stream_id} to {thumbnail_path}")
                            return thumbnail_path
                        else:
                            logger.warning(f"Failed to download thumbnail, status: {response.status}, retrying in {retry_delay}s (attempt {attempt+1}/{max_retries})")
                except Exception as e:
                    logger.error(f"Error downloading thumbnail: {e}")
                
                # Warte vor dem nächsten Versuch
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
            
            logger.error(f"Failed to download thumbnail after {max_retries} attempts")
            return None
    
    async def _is_placeholder_image(self, image_data):
        """Prüft, ob das Bild ein Platzhalter (graue Kamera) ist"""
        try:
            # Öffne das Bild mit PIL
            img = Image.open(io.BytesIO(image_data))
            
            # Berechne die durchschnittliche Farbe
            avg_color = self._get_average_color(img)
            
            # Prüfe, ob die Farbe grau ist (alle Kanäle ähnlich)
            r, g, b = avg_color
            is_gray = abs(r - g) < 10 and abs(r - b) < 10 and abs(g - b) < 10
            
            # Prüfe, ob das Bild dunkel ist (typisch für Platzhalter)
            is_dark = (r + g + b) / 3 < 100
            
            # Prüfe die Bildgröße (Platzhalter sind oft klein)
            is_small = img.width < 100 or img.height < 100
            
            return (is_gray and is_dark) or is_small
        except Exception as e:
            logger.error(f"Error checking if image is placeholder: {e}")
            return False
    
    def _get_average_color(self, img):
        """Berechnet die durchschnittliche Farbe eines Bildes"""
        # Verkleinere das Bild für schnellere Berechnung
        img = img.resize((50, 50))
        pixels = list(img.getdata())
        
        # Berechne den Durchschnitt für jeden Kanal
        r_total = 0
        g_total = 0
        b_total = 0
        
        for pixel in pixels:
            if len(pixel) >= 3:  # RGB oder RGBA
                r, g, b = pixel[0:3]
                r_total += r
                g_total += g
                b_total += b
        
        pixel_count = len(pixels)
        return (r_total // pixel_count, g_total // pixel_count, b_total // pixel_count)
    
    async def ensure_thumbnail(self, stream_id: int, output_dir: str):
        """Stellt sicher, dass ein Thumbnail existiert - versucht zuerst Twitch, dann Video-Extraktion"""
        with SessionLocal() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if not stream or not stream.streamer:
                return None
            
            # Verzeichnis erstellen
            os.makedirs(output_dir, exist_ok=True)
            
            # Eindeutigen Dateinamen erstellen mit Stream-ID und Datum
            date_str = stream.started_at.strftime("%Y%m%d") if stream.started_at else datetime.now().strftime("%Y%m%d")
            thumbnail_path = os.path.join(output_dir, f"{stream.streamer.username}_stream_{stream_id}_{date_str}_thumbnail.jpg")
            
            # Zuerst versuchen, das Twitch-Thumbnail zu laden
            twitch_thumbnail = await self.download_thumbnail(stream_id, output_dir)
            
            # Wenn das fehlschlägt, versuche die Extraktion aus dem Video
            if not twitch_thumbnail or not os.path.exists(twitch_thumbnail) or os.path.getsize(twitch_thumbnail) < 1000:
                logger.info(f"Twitch thumbnail failed, trying video extraction for stream {stream_id}")
                
                # Suche nach der MP4-Datei
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                if metadata and metadata.json_path:
                    video_dir = os.path.dirname(metadata.json_path)
                    video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')]
                    
                    if video_files:
                        video_path = os.path.join(video_dir, video_files[0])
                        # FFmpeg-Befehl zum Extrahieren eines besseren Frames
                        # Nehme Frame bei 10% der Videolänge für ein besseres Bild
                        cmd = [
                            "ffmpeg",
                            "-i", video_path,
                            "-ss", "00:00:30",  # 30 Sekunden ins Video
                            "-vframes", "1",
                            "-q:v", "1",        # Höchste Qualität
                            "-y",
                            thumbnail_path
                        ]
                        
                        try:
                            process = await asyncio.create_subprocess_exec(
                                *cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            
                            stdout, stderr = await process.communicate()
                            
                            if os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 1000:
                                # Aktualisiere Metadaten
                                if not metadata:
                                    metadata = StreamMetadata(stream_id=stream_id)
                                    db.add(metadata)
                                
                                metadata.thumbnail_path = thumbnail_path
                                db.commit()
                                
                                logger.info(f"Successfully extracted thumbnail from video for stream {stream_id}")
                                return thumbnail_path
                        except Exception as e:
                            logger.error(f"Error extracting thumbnail from video: {e}", exc_info=True)
            
            # Wenn wir hier sind, haben wir entweder ein Twitch-Thumbnail oder gar keins
            return twitch_thumbnail