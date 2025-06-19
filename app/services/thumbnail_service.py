import aiohttp
import os
from pathlib import Path
import asyncio
import logging
import time
from PIL import Image
import io
from datetime import datetime
from typing import Optional

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
            
            # Konvertiere zu RGB falls notwendig
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Berechne die durchschnittliche Farbe
            avg_color = self._get_average_color(img)
            
            # Twitch Placeholder ist typischerweise grau (RGB um 100-120)
            # Prüfe auch auf sehr einheitliche Farben (geringer Kontrast)
            r, g, b = avg_color
            
            # Graue Placeholder-Erkennung (erweitert)
            is_gray_placeholder = (
                80 <= r <= 140 and 
                80 <= g <= 140 and 
                80 <= b <= 140 and
                abs(r - g) < 20 and 
                abs(g - b) < 20 and 
                abs(r - b) < 20
            )
            
            # Prüfe auch auf sehr kleine Dateien (unter 5KB sind meist Placeholder)
            is_too_small = len(image_data) < 5120  # 5KB
            
            # Zusätzlich: Prüfe auf sehr einheitliche Farben (Histogramm-Analyse)
            histogram = img.histogram()
            # Bei Placeholder-Bildern sind wenige Farben dominant
            if len(histogram) >= 768:  # RGB = 3 * 256
                max_values = []
                for i in range(0, 768, 256):  # R, G, B Kanäle
                    channel_hist = histogram[i:i+256]
                    max_values.append(max(channel_hist))
                
                total_pixels = img.width * img.height
                # Wenn über 70% der Pixel in den dominanten Farben sind, ist es wahrscheinlich ein Placeholder
                dominant_ratio = sum(max_values) / (total_pixels * 3)
                is_low_contrast = dominant_ratio > 0.7
            else:
                is_low_contrast = False
            
            result = is_gray_placeholder or is_too_small or is_low_contrast
            
            if result:
                logger.info(f"Detected placeholder image: gray={is_gray_placeholder}, small={is_too_small}, low_contrast={is_low_contrast}, avg_color={avg_color}, size={len(image_data)} bytes")
            
            return result
            
        except Exception as e:
            logger.warning(f"Error checking for placeholder image: {e}")
            # Bei Fehlern nehmen wir an, dass es kein Placeholder ist
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
        
    async def extract_thumbnail_from_video(self, video_path: str, output_path: str, timestamp: str = "00:05:00") -> bool:
        """Extrahiert ein Thumbnail aus der Video-Datei an einer bestimmten Zeitstelle"""
        try:
            # Verwende FFmpeg, um ein Frame aus der Mitte des Videos zu extrahieren
            cmd = [
                "ffmpeg",
                "-ss", timestamp,  # Springe zu dieser Zeitstelle (5 Minuten in den Stream)
                "-i", video_path,
                "-vframes", "1",   # Nur ein Frame
                "-q:v", "2",       # Hohe Qualität
                "-y",              # Überschreibe existierende Datei
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                logger.info(f"Successfully extracted thumbnail from video at {timestamp}: {output_path}")
                return True
            else:
                logger.warning(f"Failed to extract thumbnail from video. Return code: {process.returncode}")
                if stderr:
                    logger.warning(f"FFmpeg stderr: {stderr.decode('utf-8', errors='ignore')}")
                return False
                
        except Exception as e:
            logger.error(f"Error extracting thumbnail from video: {e}", exc_info=True)
            return False

    async def ensure_thumbnail_with_fallback(self, stream_id: int, output_dir: str, video_path: str = None) -> str:
        """Stellt sicher, dass ein hochwertiges Thumbnail existiert - mit Video-Fallback bei Placeholder"""
        with SessionLocal() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if not stream:
                logger.warning(f"Stream with ID {stream_id} not found in ensure_thumbnail_with_fallback")
                return None
            
            # Streamer über streamer_id laden (fix für den Fehler)
            streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
            if not streamer:
                logger.warning(f"Streamer with ID {stream.streamer_id} not found in ensure_thumbnail_with_fallback")
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
                        # Versuche, ein Thumbnail aus dem Video zu extrahieren
                        success = await self.extract_thumbnail_from_video(video_path, thumbnail_path)
                        
                        if success:
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
    
    async def delayed_thumbnail_download(self, streamer_username: str, stream_id: int, output_dir: str, video_path: Optional[str] = None, delay_minutes: int = 3) -> Optional[str]:
        """Downloads thumbnail with delay to ensure stream is running and fallback to video extraction
        
        Args:
            streamer_username: Twitch username
            stream_id: Stream ID
            output_dir: Output directory
            video_path: Path to video file for fallback extraction
            delay_minutes: Minutes to wait before downloading (default: 3)
            
        Returns:
            Path to thumbnail or None on failure
        """
        try:
            # Wait for the stream to be properly running
            await asyncio.sleep(delay_minutes * 60)
            
            logger.info(f"Attempting delayed thumbnail download for {streamer_username} after {delay_minutes} minutes")
            
            # First attempt: Download from Twitch
            twitch_thumbnail = await self.download_thumbnail(stream_id, output_dir)
            
            if twitch_thumbnail and os.path.exists(twitch_thumbnail):
                # Check if it's a placeholder
                with open(twitch_thumbnail, 'rb') as f:
                    image_data = f.read()
                
                is_placeholder = await self._is_placeholder_image(image_data)
                
                if not is_placeholder:
                    logger.info(f"Successfully downloaded quality Twitch thumbnail for {streamer_username}")
                    return twitch_thumbnail
                else:
                    logger.info(f"Twitch thumbnail is placeholder, will extract from video instead")
                    # Remove placeholder file
                    os.remove(twitch_thumbnail)
            
            # Fallback: Extract from video file if available
            if video_path and os.path.exists(video_path):
                output_path = os.path.join(output_dir, f"{streamer_username}_thumbnail.jpg")
                
                # Try different timestamps to find a good frame
                timestamps = ["00:05:00", "00:03:00", "00:10:00", "00:01:30"]
                
                for timestamp in timestamps:
                    success = await self.extract_thumbnail_from_video(video_path, output_path, timestamp)
                    if success:
                        logger.info(f"Successfully extracted thumbnail from video at {timestamp} for {streamer_username}")
                        
                        # Update database
                        with SessionLocal() as db:
                            metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                            if not metadata:
                                metadata = StreamMetadata(stream_id=stream_id)
                                db.add(metadata)
                            
                            metadata.thumbnail_path = output_path
                            db.commit()
                        
                        return output_path
                
                logger.warning(f"Failed to extract thumbnail from video for {streamer_username}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error in delayed thumbnail download: {e}", exc_info=True)
            return None