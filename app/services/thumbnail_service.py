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
