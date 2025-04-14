import aiohttp
import os
from pathlib import Path
import asyncio
import logging

from app.database import SessionLocal
from app.models import Stream, StreamMetadata

logger = logging.getLogger("streamvault")

class ThumbnailService:
    def __init__(self):
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        await self.session.close()
    
    async def get_stream_thumbnail(self, username: str, width: int = 1280, height: int = 720):
        """Generiert Twitch-Vorschaubild-URL für einen laufenden Stream"""
        return f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{username}-{width}x{height}.jpg"
    
    async def download_thumbnail(self, stream_id: int, output_dir: str):
        """Lädt das Stream-Thumbnail herunter"""
        with SessionLocal() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if not stream or not stream.streamer:
                return None
            
            # Verzeichnis erstellen
            os.makedirs(output_dir, exist_ok=True)
            thumbnail_path = os.path.join(output_dir, f"{stream.streamer.username}_thumbnail.jpg")
            
            # URL generieren
            url = await self.get_stream_thumbnail(stream.streamer.username)
            
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        with open(thumbnail_path, 'wb') as f:
                            f.write(await response.read())
                        
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
                        logger.warning(f"Failed to download thumbnail, status: {response.status}")
            except Exception as e:
                logger.error(f"Error downloading thumbnail: {e}")
            
            return None
    
    async def ensure_thumbnail(self, stream_id: int, output_dir: str):
        """Stellt sicher, dass ein Thumbnail existiert - versucht zuerst Twitch, dann Video-Extraktion"""
        with SessionLocal() as db:
            stream = db.query(Stream).filter(Stream.id == stream_id).first()
            if not stream or not stream.streamer:
                return None
            
            # Verzeichnis erstellen
            os.makedirs(output_dir, exist_ok=True)
            thumbnail_path = os.path.join(output_dir, f"{stream.streamer.username}_thumbnail.jpg")
            
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
                        # FFmpeg-Befehl zum Extrahieren des ersten Frames mit höherer Qualität
                        cmd = [
                            "ffmpeg",
                            "-i", video_path,
                            "-vf", "select=eq(n\\,100)",  # Nehme Frame 100 statt 0 (oft besser)
                            "-q:v", "1",                 # Höchste Qualität
                            "-vframes", "1",
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
