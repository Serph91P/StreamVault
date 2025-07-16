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
from app.services.unified_image_service import unified_image_service

logger = logging.getLogger("streamvault")

class ThumbnailService:
    def __init__(self):
        pass
    
    async def close(self):
        """Close resources (now handled by unified_image_service)"""
        pass
    
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
                # Use unified_image_service for download
                session = await unified_image_service._get_session()
                async with session.get(url) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'image' in content_type:
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
                        else:
                            logger.warning(f"Invalid content type for thumbnail: {content_type}")
                            return None
                        
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
                            # Use the logging service to create per-streamer logs
                            from app.services.system.logging_service import logging_service
                            if logging_service:
                                streamer_log_path = logging_service.log_ffmpeg_start("thumbnail_extract", cmd, streamer.name)
                                logger.info(f"FFmpeg logs will be written to: {streamer_log_path}")
                            
                            process = await asyncio.create_subprocess_exec(
                                *cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            
                            stdout, stderr = await process.communicate()
                            
                            # Log the FFmpeg output using the logging service
                            if logging_service:
                                logging_service.log_ffmpeg_output("thumbnail_extract", stdout, stderr, process.returncode, streamer.name)
                            
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
    
    async def generate_thumbnail_from_mp4(self, stream_id: int, mp4_path: str) -> Optional[str]:
        """Generate thumbnail from MP4 file with all Plex/Emby compatibility features
        
        Args:
            stream_id: Stream ID for database updates
            mp4_path: Path to the MP4 file
            
        Returns:
            Path to the generated thumbnail or None on failure
        """
        try:
            # Get stream info from database
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream {stream_id} not found for thumbnail generation")
                    return None
                
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    logger.warning(f"Streamer for stream {stream_id} not found for thumbnail generation")
                    return None
            
            # Create output directory for thumbnail
            output_dir = os.path.dirname(mp4_path)
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate thumbnail path
            thumbnail_path = os.path.join(output_dir, f"{streamer.username}_thumbnail.jpg")
            
            # Try different timestamps to find a good frame
            timestamps = ["00:02:00", "00:05:00", "00:01:00", "00:10:00", "00:00:30"]
            
            for timestamp in timestamps:
                logger.info(f"Attempting to extract thumbnail from MP4 at {timestamp} for {streamer.username}")
                
                success = await self.extract_thumbnail_from_video(
                    video_path=mp4_path,
                    output_path=thumbnail_path,
                    timestamp=timestamp
                )
                
                if success and os.path.exists(thumbnail_path) and os.path.getsize(thumbnail_path) > 1000:
                    logger.info(f"Successfully extracted thumbnail from MP4 at {timestamp}: {thumbnail_path}")
                    
                    # Update database with thumbnail path
                    with SessionLocal() as db:
                        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                        if not metadata:
                            metadata = StreamMetadata(stream_id=stream_id)
                            db.add(metadata)
                        
                        metadata.thumbnail_path = thumbnail_path
                        db.commit()
                    
                    # Create Plex-compatible thumbnail files
                    await self._create_plex_compatible_thumbnails(mp4_path, thumbnail_path)
                    
                    logger.info(f"THUMBNAIL_SUCCESS: Generated from MP4 at {timestamp} for {streamer.username}")
                    return thumbnail_path
            
            # If all timestamps failed, try Twitch thumbnail as fallback
            logger.warning(f"Failed to extract thumbnail from MP4, trying Twitch fallback for {streamer.username}")
            
            twitch_thumbnail = await self.download_thumbnail(stream_id, output_dir)
            if twitch_thumbnail and os.path.exists(twitch_thumbnail):
                logger.info(f"Successfully downloaded Twitch fallback thumbnail: {twitch_thumbnail}")
                await self._create_plex_compatible_thumbnails(mp4_path, twitch_thumbnail)
                return twitch_thumbnail
            else:
                logger.error(f"Both MP4 extraction and Twitch download failed for {streamer.username}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating thumbnail from MP4: {e}", exc_info=True)
            return None
    
    async def _create_plex_compatible_thumbnails(self, mp4_path: str, source_thumbnail_path: str):
        """Create Plex/Emby-compatible thumbnail files in multiple formats"""
        try:
            if not os.path.exists(source_thumbnail_path):
                logger.warning(f"Source thumbnail does not exist: {source_thumbnail_path}")
                return
                
            video_dir = os.path.dirname(mp4_path)
            base_filename = os.path.splitext(os.path.basename(mp4_path))[0]
            
            # Create various thumbnail formats for different media servers
            thumbnail_formats = [
                f"{base_filename}-thumb.jpg",  # Plex thumbnail
                f"{base_filename}.jpg",        # Alternative format
                "poster.jpg",                  # Plex poster
                "folder.jpg",                  # Generic folder image
            ]
            
            import shutil
            for format_name in thumbnail_formats:
                target_path = os.path.join(video_dir, format_name)
                try:
                    if not os.path.exists(target_path) or os.path.getsize(target_path) < 1000:
                        shutil.copy2(source_thumbnail_path, target_path)
                        logger.debug(f"Created thumbnail format: {target_path}")
                except Exception as e:
                    logger.warning(f"Failed to create thumbnail format {format_name}: {e}")
                    
            logger.info(f"Created Plex-compatible thumbnails in {video_dir}")
            
        except Exception as e:
            logger.error(f"Error creating Plex-compatible thumbnails: {e}")


# Global thumbnail service instance
thumbnail_service = ThumbnailService()
