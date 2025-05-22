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
from app.models import Stream, StreamMetadata, Streamer

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
    async def download_thumbnail(self, stream_id: int, output_dir: str):
        """Lädt das Stream-Thumbnail herunter"""
        with SessionLocal() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if not stream:
                logger.warning(f"Stream with ID {stream_id} not found in thumbnail_service")
                return None
            
            # Streamer über streamer_id laden (der Fehler war, dass wir stream.streamer verwendet haben)
            streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
            if not streamer:
                logger.warning(f"Streamer with ID {stream.streamer_id} not found in thumbnail_service")
                return None
            
            # Verzeichnis erstellen
            os.makedirs(output_dir, exist_ok=True)
            thumbnail_path = os.path.join(output_dir, f"{streamer.username}_thumbnail.jpg")
            
            # Prüfen, ob bereits ein Thumbnail existiert
            metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
            if metadata and metadata.thumbnail_path and os.path.exists(metadata.thumbnail_path):
                logger.info(f"Using existing thumbnail for stream {stream_id} from {metadata.thumbnail_path}")
                
                # Kopiere auch in das Standard-Format für Plex, falls verfügbar
                try:
                    if metadata.json_path:
                        video_dir = os.path.dirname(metadata.json_path)
                        base_filename = os.path.splitext(os.path.basename(metadata.json_path))[0]
                        base_filename = base_filename.replace(".info", "")  # Entferne ".info" wenn vorhanden
                        
                        plex_thumbnail_path = os.path.join(video_dir, f"{base_filename}-thumb.jpg")
                        poster_path = os.path.join(video_dir, "poster.jpg")
                        
                        import shutil
                        if not os.path.exists(plex_thumbnail_path) or os.path.getsize(plex_thumbnail_path) < 1000:
                            shutil.copy2(metadata.thumbnail_path, plex_thumbnail_path)
                        
                        if not os.path.exists(poster_path):
                            shutil.copy2(metadata.thumbnail_path, poster_path)
                except Exception as e:
                    logger.error(f"Error copying to Plex format: {e}", exc_info=True)
                
                return metadata.thumbnail_path
            
            # Prüfen, ob das Ziel-Thumbnail bereits existiert
            if os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 1000:
                logger.info(f"Using existing thumbnail file at {thumbnail_path}")
                
                # Metadata aktualisieren
                if metadata:
                    metadata.thumbnail_path = thumbnail_path
                    db.commit()
                
                return thumbnail_path
                
            # URL generieren
            url = await self.get_stream_thumbnail(streamer.username)
            
            try:
                session = await self._get_session()
                async with session.get(url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        # Prüfen, ob es ein Platzhalter-Bild ist
                        if await self._is_placeholder_image(image_data):
                            logger.warning(f"Thumbnail for stream {stream_id} is a placeholder image, skipping")
                            return None
                            
                        with open(thumbnail_path, 'wb') as f:
                            f.write(image_data)
                        
                        # Metadata aktualisieren
                        if not metadata:
                            metadata = StreamMetadata(stream_id=stream_id)
                            db.add(metadata)
                        
                        metadata.thumbnail_path = thumbnail_path
                        metadata.thumbnail_url = url
                        db.commit()
                        
                        # Auch in das Verzeichnis mit dem Video kopieren, falls es schon existiert
                        try:
                            if metadata.json_path:
                                video_dir = os.path.dirname(metadata.json_path)
                                base_filename = os.path.splitext(os.path.basename(metadata.json_path))[0]
                                base_filename = base_filename.replace(".info", "")  # Entferne ".info" wenn vorhanden
                                
                                # Kopiere in verschiedene Standard-Formate für Plex und andere Media Server
                                import shutil
                                plex_thumbnail_path = os.path.join(video_dir, f"{base_filename}-thumb.jpg")
                                poster_path = os.path.join(video_dir, "poster.jpg")
                                
                                shutil.copy2(thumbnail_path, plex_thumbnail_path)
                                shutil.copy2(thumbnail_path, poster_path)
                                logger.info(f"Copied thumbnail to Plex format: {plex_thumbnail_path}")
                        except Exception as e:
                            logger.error(f"Error copying thumbnail to video directory: {e}", exc_info=True)
                        
                        logger.info(f"Downloaded thumbnail for stream {stream_id} to {thumbnail_path}")
                        return thumbnail_path
                    else:
                        logger.warning(f"Failed to download thumbnail, status: {response.status}")
            except Exception as e:
                logger.error(f"Error downloading thumbnail: {e}")
            
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
            if not stream:
                logger.warning(f"Stream with ID {stream_id} not found in ensure_thumbnail")
                return None
            
            # Streamer über streamer_id laden (fix für den Fehler)
            streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
            if not streamer:
                logger.warning(f"Streamer with ID {stream.streamer_id} not found in ensure_thumbnail")
                return None
            
            # Verzeichnis erstellen
            os.makedirs(output_dir, exist_ok=True)
            thumbnail_path = os.path.join(output_dir, f"{streamer.username}_thumbnail.jpg")
            
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
                                
                                # Kopiere das Thumbnail auch in das Verzeichnis mit dem passenden Namen für Plex
                                if metadata.json_path:
                                    try:
                                        video_dir = os.path.dirname(metadata.json_path)
                                        base_filename = os.path.splitext(os.path.basename(metadata.json_path))[0]
                                        base_filename = base_filename.replace(".info", "")  # Entferne ".info" wenn vorhanden
                                        
                                        # Kopiere in verschiedene Standard-Formate für Plex und andere Media Server
                                        import shutil
                                        plex_thumbnail_path = os.path.join(video_dir, f"{base_filename}-thumb.jpg")
                                        poster_path = os.path.join(video_dir, "poster.jpg")
                                        
                                        shutil.copy2(thumbnail_path, plex_thumbnail_path)
                                        shutil.copy2(thumbnail_path, poster_path)
                                        logger.info(f"Copied extracted thumbnail to Plex format: {plex_thumbnail_path}")
                                    except Exception as e:
                                        logger.error(f"Error copying extracted thumbnail to video directory: {e}", exc_info=True)
                                
                                logger.info(f"Successfully extracted thumbnail from video for stream {stream_id}")
                                return thumbnail_path
                        except Exception as e:
                            logger.error(f"Error extracting thumbnail from video: {e}", exc_info=True)
            
            # Wenn wir hier sind, haben wir entweder ein Twitch-Thumbnail oder gar keins
            # Prüfe nochmal, ob wir ein Thumbnail in den Metadaten haben, falls alles andere fehlgeschlagen ist
            if metadata and metadata.thumbnail_path and os.path.exists(metadata.thumbnail_path):
                logger.info(f"Using existing thumbnail from metadata for stream {stream_id}")
                
                # Stelle sicher, dass das Thumbnail auch mit dem richtigen Namen im Verzeichnis liegt,
                # damit die Plex-Integration es korrekt findet
                if metadata.json_path:
                    try:
                        video_dir = os.path.dirname(metadata.json_path)
                        base_filename = os.path.splitext(os.path.basename(metadata.json_path))[0]
                        base_filename = base_filename.replace(".info", "")  # Entferne ".info" wenn vorhanden
                        
                        # Kopiere das Thumbnail in das Verzeichnis mit standardisierten Namen für Plex
                        plex_thumbnail_path = os.path.join(video_dir, f"{base_filename}-thumb.jpg")
                        poster_path = os.path.join(video_dir, "poster.jpg")
                        
                        import shutil
                        if not os.path.exists(plex_thumbnail_path) or os.path.getsize(plex_thumbnail_path) < 1000:
                            shutil.copy2(metadata.thumbnail_path, plex_thumbnail_path)
                            logger.info(f"Copied thumbnail to Plex-friendly format: {plex_thumbnail_path}")
                        
                        if not os.path.exists(poster_path):
                            shutil.copy2(metadata.thumbnail_path, poster_path)
                            logger.info(f"Copied thumbnail to Plex poster: {poster_path}")
                    except Exception as e:
                        logger.error(f"Error copying thumbnail to standardized location: {e}", exc_info=True)
                
                return metadata.thumbnail_path
                
            return twitch_thumbnail