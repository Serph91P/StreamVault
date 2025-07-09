import os
import json
import aiohttp
import asyncio
import logging
import tempfile
import copy  # Add missing import for copy module
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import xml.etree.ElementTree as ET
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Stream, StreamMetadata, StreamEvent, Streamer, RecordingSettings
from app.config.settings import settings
from app.services.logging_service import logging_service
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
                
                # Aufgaben parallel ausführen - Aber auch bei Fehlern weitermachen
                results = []
                try:
                    result_json = await self.generate_json_metadata(db, stream, streamer, base_path, base_filename, metadata)
                    results.append(result_json)
                except Exception as e:
                    logger.error(f"Error generating JSON metadata: {e}", exc_info=True)
                    results.append(False)
                
                try:
                    result_nfo = await self.generate_nfo_file(db, stream, streamer, base_path, base_filename, metadata)
                    results.append(result_nfo)
                except Exception as e:
                    logger.error(f"Error generating NFO file: {e}", exc_info=True)
                    results.append(False)
                
                try:
                    result_thumbnail = await self.extract_thumbnail(mp4_path, stream_id, db)
                    results.append(result_thumbnail is not None)
                except Exception as e:
                    logger.error(f"Error extracting thumbnail: {e}", exc_info=True)
                    results.append(False)
                
                try:
                    result_chapters = await self.ensure_all_chapter_formats(stream_id, mp4_path, db)
                    results.append(result_chapters is not None)
                except Exception as e:
                    logger.error(f"Error generating chapters: {e}", exc_info=True)
                    results.append(False)
                
                db.commit()
                success_count = sum(1 for r in results if r)
                logger.info(f"Generated metadata for stream {stream_id} - {success_count}/{len(results)} tasks successful")
                return success_count > 0  # Success if at least one task succeeded
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
        """Creates NFO file for Kodi/Plex/Emby with correct image links.
        
        Returns:
            bool: True on success, False on error
        """
        try:
            # Create two NFO files:
            # 1. tvshow.nfo - for show/season data (uses streamer image)
            # 2. episode.nfo - for the specific stream episode (uses stream thumbnail)
            
            # Paths for NFO files - alle im Streamer-Ordner!
            episode_nfo_path = base_path / f"{base_filename}.nfo"
            
            # Determine streamer directory (one or two levels up)
            is_in_season_dir = "season" in base_path.name.lower() or f"s{stream.started_at.strftime('%Y%m')}" in base_path.name.lower()
            if is_in_season_dir:
                streamer_dir = base_path.parent.parent
            else:
                streamer_dir = base_path.parent
            
            # Show-level NFO goes into streamer directory, not parent
            tvshow_nfo_path = streamer_dir / "tvshow.nfo"
            season_nfo_path = streamer_dir / "season.nfo"
                    
            # 1. Generate Show/Season NFO
            show_root = ET.Element("tvshow")
            
            # Basic metadata
            ET.SubElement(show_root, "title").text = f"{streamer.username} Streams"
            ET.SubElement(show_root, "sorttitle").text = f"{streamer.username} Streams"
            ET.SubElement(show_root, "showtitle").text = f"{streamer.username} Streams"
            
            # Streamer information
            ET.SubElement(show_root, "studio").text = "Twitch"
            ET.SubElement(show_root, "plot").text = f"Streams by {streamer.username} on Twitch."
            
            # Important for Plex: Correct paths for images
            # Plex expects specific filenames, not just in NFO files
            if streamer.profile_image_url:
                # Images for the show
                poster_element = ET.SubElement(show_root, "thumb", aspect="poster")
                poster_element.text = "poster.jpg"
                
                banner_element = ET.SubElement(show_root, "thumb", aspect="banner")
                banner_element.text = "banner.jpg"
                
                # Fanart (background image)
                fanart = ET.SubElement(show_root, "fanart")
                ET.SubElement(fanart, "thumb").text = "fanart.jpg"
                
                # Save streamer images in different formats
                await self._save_streamer_images(streamer, streamer_dir)
                
            # Genre/Category
            if streamer.category_name:
                ET.SubElement(show_root, "genre").text = streamer.category_name
            else:
                ET.SubElement(show_root, "genre").text = "Livestream"
            
            # Streamer as "actor"
            actor = ET.SubElement(show_root, "actor")
            ET.SubElement(actor, "name").text = streamer.username
            if streamer.profile_image_url:
                # Korrekte Pfade für verschiedene Strukturen
                if is_in_season_dir:
                    ET.SubElement(actor, "thumb").text = f"../actors/{streamer.username}.jpg"
                else:
                    ET.SubElement(actor, "thumb").text = f"actors/{streamer.username}.jpg"
                
                # Create actors directory and download image
                actors_dir = streamer_dir / "actors"
                actors_dir.mkdir(exist_ok=True)
                await self._download_image(streamer.profile_image_url, actors_dir / f"{streamer.username}.jpg")
                
            ET.SubElement(actor, "role").text = "Streamer"
            
            # Write XML
            show_tree = ET.ElementTree(show_root)
            show_tree.write(str(tvshow_nfo_path), encoding="utf-8", xml_declaration=True)
            
            # Create season NFO if in season directory
            if is_in_season_dir:
                season_root = ET.Element("season")
                
                if stream.started_at:
                    season_num = stream.started_at.strftime("%Y%m")
                    ET.SubElement(season_root, "seasonnumber").text = season_num
                    
                # Season title
                ET.SubElement(season_root, "title").text = f"Season {stream.started_at.strftime('%Y-%m')}"
                
                # Season poster
                if streamer.profile_image_url:
                    ET.SubElement(season_root, "thumb").text = "poster.jpg"
                    # Save season image im Streamer-Ordner
                    await self._download_image(streamer.profile_image_url, streamer_dir / "poster.jpg")
                    await self._download_image(streamer.profile_image_url, streamer_dir / "season.jpg")
                    
                # Write XML
                season_tree = ET.ElementTree(season_root)
                season_tree.write(str(season_nfo_path), encoding="utf-8", xml_declaration=True)
            
            # 2. Generate Episode NFO
            episode_root = ET.Element("episodedetails")
            
            # Episode title and number
            ET.SubElement(episode_root, "title").text = stream.title or f"{streamer.username} Stream"
            
            # Calculate episode number from date (e.g., day of month)
            if stream.started_at:
                ET.SubElement(episode_root, "aired").text = stream.started_at.strftime("%Y-%m-%d")
                ET.SubElement(episode_root, "premiered").text = stream.started_at.strftime("%Y-%m-%d")
                ET.SubElement(episode_root, "dateadded").text = stream.started_at.strftime("%Y-%m-%d %H:%M:%S")
                
                # Use year-month as season number and day as episode number
                season_num = stream.started_at.strftime("%Y%m")
                episode_num = stream.started_at.strftime("%d")
                
                ET.SubElement(episode_root, "season").text = season_num
                ET.SubElement(episode_root, "episode").text = episode_num
                
                # Correct episode ID for Plex
                ET.SubElement(episode_root, "episodeID").text = f"S{season_num}E{episode_num}"
            
            # Language
            ET.SubElement(episode_root, "language").text = stream.language or "en"
            
            # Stream Info
            plot = f"{streamer.username} streamed"
            if stream.category_name:
                plot += f" {stream.category_name}"
            if stream.started_at:
                plot += f" on {stream.started_at.strftime('%Y-%m-%d')}"
                
                # Add duration if available
                if stream.ended_at:
                    duration_mins = int((stream.ended_at - stream.started_at).total_seconds() / 60)
                    plot += f" for {duration_mins} minutes"
            plot += "."
            
            ET.SubElement(episode_root, "plot").text = plot
            ET.SubElement(episode_root, "runtime").text = str(int((stream.ended_at - stream.started_at).total_seconds() / 60)) if stream.ended_at and stream.started_at else ""
            
            # Genre/Category
            if stream.category_name:
                ET.SubElement(episode_root, "genre").text = stream.category_name
            
            # Streamer as "actor"
            actor = ET.SubElement(episode_root, "actor")
            ET.SubElement(actor, "name").text = streamer.username
            if streamer.profile_image_url:
                ET.SubElement(actor, "thumb").text = "../actors/"+streamer.username+".jpg" if is_in_season_dir else "actors/"+streamer.username+".jpg"
            ET.SubElement(actor, "role").text = "Streamer"
            
            # IMPORTANT: Thumbnails for the episode with different standard names
            thumbnail_url = None
            local_thumbnail = None
            
            # Check for Twitch thumbnail in database
            if metadata.thumbnail_url:
                thumbnail_url = metadata.thumbnail_url
                
            # Check for locally stored thumbnail
            if metadata.thumbnail_path and os.path.exists(metadata.thumbnail_path):
                local_thumbnail = metadata.thumbnail_path
                
            # Process thumbnail for episode
            episode_thumb_path = await self._process_episode_thumbnail(
                stream_id=stream.id,
                base_path=base_path,
                base_filename=base_filename,
                thumbnail_url=thumbnail_url,
                local_thumbnail=local_thumbnail,
                db=db
            )
            
            # Different thumb formats for different media servers
            if episode_thumb_path:
                # Standard format
                thumb_element = ET.SubElement(episode_root, "thumb")
                thumb_element.text = os.path.basename(episode_thumb_path)
                
                # Plex format
                thumb_element_plex = ET.SubElement(episode_root, "thumb", aspect="poster")
                thumb_element_plex.text = os.path.basename(episode_thumb_path)
            
            # Write XML
            episode_tree = ET.ElementTree(episode_root)
            episode_tree.write(str(episode_nfo_path), encoding="utf-8", xml_declaration=True)
            
            # Update metadata in database
            metadata.nfo_path = str(episode_nfo_path)
            metadata.tvshow_nfo_path = str(tvshow_nfo_path)
            
            # Create additional symlinks/copies for specific media servers
            await self._create_media_server_specific_files(
                stream=stream, 
                base_path=base_path, 
                episode_thumb_path=episode_thumb_path if episode_thumb_path else None,
                db=db
            )
            
            logger.debug(f"Generated NFO files for stream {stream.id}: {episode_nfo_path} and {tvshow_nfo_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating NFO files: {e}", exc_info=True)
            return False

    async def _process_episode_thumbnail(
        self, 
        stream_id: int,
        base_path: Path,
        base_filename: str,
        thumbnail_url: Optional[str] = None,
        local_thumbnail: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[str]:
        """Processes thumbnail for an episode and saves it in different formats
        
        Returns:
            Optional[str]: Path to main thumbnail or None on error
        """
        try:
            # Standard filenames for different media servers
            thumb_filename = f"{base_filename}-thumb.jpg"
            thumb_path = base_path / thumb_filename
            
            # Alternative filenames for Plex/Kodi/Emby
            poster_filename = "poster.jpg"
            poster_path = base_path / poster_filename
            
            # Prüfen, ob das Thumbnail bereits existiert und nicht überschrieben werden soll
            if thumb_path.exists() and thumb_path.stat().st_size > 1000:
                logger.debug(f"Thumb already exists at {thumb_path}, using existing file")
                
                # Update database metadata if needed
                if db:
                    metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                    if metadata and not metadata.thumbnail_path:
                        metadata.thumbnail_path = str(thumb_path)
                        db.commit()
                
                # Ensure poster.jpg exists as well
                if not poster_path.exists():
                    import shutil
                    shutil.copy2(thumb_path, poster_path)
                
                return str(thumb_path)
            
            # Determine thumbnail source
            if local_thumbnail and os.path.exists(local_thumbnail):
                # Copy existing local thumbnail
                import shutil
                shutil.copy2(local_thumbnail, thumb_path)
                shutil.copy2(local_thumbnail, poster_path)
                logger.debug(f"Copied local thumbnail for stream {stream_id} to {thumb_path}")
                return str(thumb_path)
                
            elif thumbnail_url:
                # Download thumbnail from URL
                success = await self._download_image(thumbnail_url, thumb_path)
                if success:
                    # Also save as poster.jpg
                    import shutil
                    shutil.copy2(thumb_path, poster_path)
                    logger.debug(f"Downloaded thumbnail for stream {stream_id} to {thumb_path}")
                    return str(thumb_path)
                    
            # If no thumbnail available, extract from video
            video_files = [f for f in os.listdir(base_path) if f.endswith('.mp4')]
            if video_files:
                video_path = os.path.join(base_path, video_files[0])
                extracted_thumb = await self.extract_thumbnail(video_path, stream_id, db)
                
                if extracted_thumb and os.path.exists(extracted_thumb):
                    # Copy to standard formats
                    import shutil
                    shutil.copy2(extracted_thumb, thumb_path)
                    shutil.copy2(extracted_thumb, poster_path)
                    logger.debug(f"Extracted thumbnail for stream {stream_id} to {thumb_path}")
                    return str(thumb_path)
                    
            logger.warning(f"Could not create thumbnail for stream {stream_id}")
            return None
        except Exception as e:
            logger.error(f"Error processing episode thumbnail: {e}", exc_info=True)
            return None
        
    async def _save_streamer_images(self, streamer: Streamer, streamer_dir: Path) -> bool:
        """Saves streamer profile image in different formats for media servers
        
        Returns:
            bool: True on success, False on error
        """
        try:
            if not streamer.profile_image_url:
                logger.warning(f"No profile image URL for streamer {streamer.username}")
                return False
                
            # Standard media server image names - alle verwenden das gleiche Bild
            image_files = {
                "poster.jpg": "Main poster for the show",
                "banner.jpg": "Banner image (same as poster for streamers)",
                "fanart.jpg": "Background image (same as poster for streamers)", 
                "logo.jpg": "Logo image (same as poster for streamers)",
                "clearlogo.jpg": "Clear logo image (same as poster for streamers)",
                "season.jpg": "Season poster (same as poster for streamers)",
                "season-poster.jpg": "Season poster alternative name",
                "folder.jpg": "Folder image for Windows",
                "show.jpg": "Show image (same as poster for streamers)"
            }
            
            # Download and save each image format (alle verwenden das gleiche Quellbild)
            success_count = 0
            for filename, description in image_files.items():
                target_path = streamer_dir / filename
                if await self._download_image(streamer.profile_image_url, target_path):
                    success_count += 1
                    logger.debug(f"Saved {description} for {streamer.username} at {target_path}")
            
            # Create specific media server directories if needed
            artwork_dir = streamer_dir / "artwork"
            artwork_dir.mkdir(exist_ok=True)
            
            # Save additional copies in artwork directory
            await self._download_image(streamer.profile_image_url, artwork_dir / "poster.jpg")
            
            return success_count > 0
        except Exception as e:
            logger.error(f"Error saving streamer images: {e}", exc_info=True)
            return False

    async def _download_image(self, url: str, target_path: Path) -> bool:
        """Downloads an image from a URL to a target path
        
        Returns:
            bool: True on success, False on error
        """
        try:
            # Check if URL is actually a local path
            if not url.startswith(('http://', 'https://')):
                local_path = Path(url)
                if local_path.exists():
                    import shutil
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy2(local_path, target_path)
                    return True
                else:
                    logger.warning(f"Local image file not found: {url}")
                    return False
            
            # Download from URL
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    # Make sure the directory exists
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    # Save the image
                    with open(target_path, 'wb') as f:
                        f.write(await response.read())
                    return True
                else:
                    logger.warning(f"Failed to download image, status: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error downloading image: {e}", exc_info=True)
            return False

    async def _create_media_server_specific_files(
        self,
        stream: Stream,
        base_path: Path,
        episode_thumb_path: Optional[str] = None,
        db: Optional[Session] = None
    ) -> bool:
        """Creates additional files and symlinks for specific media servers
        
        Returns:
            bool: True on success, False on error
        """
        try:
            if not stream.started_at:
                logger.warning(f"Stream {stream.id} has no start date, cannot create media server specific files")
                return False
                
            # Get the current filename preset from settings
            recording_settings = None
            if db:
                recording_settings = db.query(RecordingSettings).first()
            
            # Default to generic files if no specific preset found
            filename_preset = "default"
            if recording_settings and hasattr(recording_settings, "filename_preset"):
                filename_preset = recording_settings.filename_preset
                
            logger.debug(f"Using filename preset '{filename_preset}' for media server specific files")
            
            # List of common media servers
            media_servers = ["plex", "emby", "jellyfin", "kodi"]
            
            # Get base filename without extension
            base_filename = base_path.stem if isinstance(base_path, Path) else Path(base_path).stem
            
            # Falls kein Thumbnail übergeben wurde, versuche es aus den Metadaten zu holen
            if not episode_thumb_path or not os.path.exists(episode_thumb_path):
                try:
                    logger.debug(f"No thumb path provided, trying to find from metadata")
                    if db:
                        metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream.id).first()
                        if metadata and metadata.thumbnail_path and os.path.exists(metadata.thumbnail_path):
                            episode_thumb_path = metadata.thumbnail_path
                            logger.debug(f"Found thumbnail from metadata: {episode_thumb_path}")
                except Exception as e:
                    logger.error(f"Error getting thumbnail from metadata: {e}", exc_info=True)
            
            # Create thumbnail and metadata files specific to each media server
            if episode_thumb_path and os.path.exists(episode_thumb_path):
                import shutil
                
                # Plex specific files - always create these for maximum compatibility
                if "plex" in filename_preset or True:  # Always create Plex files
                    # Plex prefers poster.jpg in the same directory
                    plex_poster = base_path / "poster.jpg"
                    if not plex_poster.exists():
                        shutil.copy2(episode_thumb_path, plex_poster)
                        logger.debug(f"Created Plex poster: {plex_poster}")
                    
                    # Stelle sicher, dass das Standard-Thumbnail existiert
                    plex_thumb = base_path / f"{base_filename}-thumb.jpg"
                    if not plex_thumb.exists():
                        shutil.copy2(episode_thumb_path, plex_thumb)
                        logger.debug(f"Created standard thumb: {plex_thumb}")
                    
                    # Create season-poster.jpg in parent if it's a season directory
                    if "season" in str(base_path).lower() or "s20" in str(base_path).lower():
                        season_poster = base_path.parent / "season-poster.jpg"
                        if not season_poster.exists() and os.path.exists(episode_thumb_path):
                            shutil.copy2(episode_thumb_path, season_poster)
                            logger.debug(f"Created season poster: {season_poster}")
                
                # Kodi specific files
                if "kodi" in filename_preset or True:  # Always create Kodi files
                    # Kodi uses .tbn extension for thumbnails
                    kodi_tbn = base_path / f"{base_filename}.tbn"
                    if not kodi_tbn.exists():
                        shutil.copy2(episode_thumb_path, kodi_tbn)
                        logger.debug(f"Created Kodi thumbnail: {kodi_tbn}")
                
                # Emby/Jellyfin specific files
                if any(server in filename_preset for server in ["emby", "jellyfin"]) or True:
                    # Emby/Jellyfin also like poster.jpg
                    poster_jpg = base_path / "poster.jpg"
                    if not poster_jpg.exists():
                        shutil.copy2(episode_thumb_path, poster_jpg)
                        logger.debug(f"Created Emby poster: {poster_jpg}")
            else:
                logger.warning(f"No episode thumbnail available to create media server specific files for {stream.id}")
            
            # Create specific nfo link based on the preset
            # For example, Plex sometimes requires SXXEXX format in the filename
            if "plex" in filename_preset and stream.started_at:
                season_num = stream.started_at.strftime("%Y%m")
                episode_num = stream.started_at.strftime("%d")
                
                streamer_name = ""
                with SessionLocal() as session:
                    streamer = session.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                    if streamer:
                        streamer_name = streamer.username
                
                # Plex pattern: ShowName - SXXEXX - EpisodeTitle
                plex_name = f"{streamer_name} - S{season_num}E{episode_num}"
                if stream.title:
                    plex_name += f" - {stream.title}"
                
                # Clean the filename
                plex_name = plex_name.replace('/', '-').replace('\\', '-').replace(':', '-')
                
                # Create symlinks for video and nfo files with Plex naming
                video_files = list(base_path.parent.glob(f"{base_filename}.mp4"))
                nfo_files = list(base_path.parent.glob(f"{base_filename}.nfo"))
                
                if video_files:
                    try:
                        # Create symlink or copy for video
                        video_src = video_files[0]
                        video_dest = base_path.parent / f"{plex_name}.mp4"
                        
                        if not video_dest.exists():
                            if os.name == 'nt':  # Windows
                                try:
                                    os.link(video_src, video_dest)
                                except:
                                    shutil.copy2(video_src, video_dest)
                            else:  # Linux/Mac
                                try:
                                    os.symlink(video_src, video_dest)
                                except:
                                    shutil.copy2(video_src, video_dest)
                    except Exception as e:
                        logger.warning(f"Error creating Plex video symlink: {e}")
                
                if nfo_files:
                    try:
                        # Create symlink or copy for NFO
                        nfo_src = nfo_files[0]
                        nfo_dest = base_path.parent / f"{plex_name}.nfo"
                        
                        if not nfo_dest.exists():
                            if os.name == 'nt':  # Windows
                                try:
                                    os.link(nfo_src, nfo_dest)
                                except:
                                    shutil.copy2(nfo_src, nfo_dest)
                            else:  # Linux/Mac
                                try:
                                    os.symlink(nfo_src, nfo_dest)
                                except:
                                    shutil.copy2(nfo_src, nfo_dest)
                    except Exception as e:
                        logger.warning(f"Error creating Plex NFO symlink: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Error creating media server specific files: {e}", exc_info=True)
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
            
            # Prüfen, ob das Thumbnail bereits existiert
            if thumbnail_path.exists() and thumbnail_path.stat().st_size > 1000:
                logger.info(f"Using existing thumbnail at {thumbnail_path}")
                
                # Aktualisiere Metadaten, wenn noch nicht gesetzt
                if stream_id and db:
                    metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                    if metadata and not metadata.thumbnail_path:
                        metadata.thumbnail_path = str(thumbnail_path)
                        db.commit()
                        
                return str(thumbnail_path)
            
            # Check if the file has video streams first
            check_cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path_obj)
            ]
            
            check_process = await asyncio.create_subprocess_exec(
                *check_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            check_stdout, check_stderr = await check_process.communicate()
            
            # If no video stream detected, this is audio-only
            if check_process.returncode != 0 or not check_stdout or "video" not in check_stdout.decode("utf-8", errors="ignore").lower():
                logger.info(f"Audio-only file detected, skipping thumbnail extraction: {video_path}")
                return None
            
            # FFmpeg-Befehl zum Extrahieren eines Frames nach 10 Sekunden (bessere Bildqualität)
            cmd = [
                "ffmpeg",
                "-ss", "00:00:10",         # 10 Sekunden ins Video springen
                "-i", str(video_path_obj),
                "-vframes", "1",           # Nur ein Frame
                "-q:v", "2",               # Hohe Qualität
                "-f", "image2",
                "-y",                      # Überschreiben bestehender Dateien
                str(thumbnail_path)
            ]
            
            # Create a unique log file for this thumbnail extraction using the logging service
            streamer_name = video_path_obj.stem.split('-')[0] if '-' in video_path_obj.stem else 'unknown'
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ffmpeg_log_path = logging_service.get_ffmpeg_log_path(f"thumbnail_{timestamp}", streamer_name)
            
            # Ensure the log directory exists
            os.makedirs(os.path.dirname(ffmpeg_log_path), exist_ok=True)
            
            # Set up environment for FFmpeg log and redirect output to file only
            env = os.environ.copy()
            env["FFREPORT"] = f"file={ffmpeg_log_path}:level=40"
            env["AV_LOG_FORCE_NOCOLOR"] = "1"  # Disable ANSI color in logs
            env["AV_LOG_FORCE_STDERR"] = "0"   # Don't force stderr output
            
            # Add quiet logging level to prevent output to console/container logs
            cmd.extend(["-loglevel", "quiet"])
            
            # Create temporary files for stdout and stderr
            import tempfile
            stdout_file = tempfile.NamedTemporaryFile(delete=False, prefix="ffmpeg_thumb_stdout_", suffix=".log")
            stderr_file = tempfile.NamedTemporaryFile(delete=False, prefix="ffmpeg_thumb_stderr_", suffix=".log")
            
            try:
                # Start the process with output redirected to temp files
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=stdout_file.fileno(),
                    stderr=stderr_file.fileno(),
                    env=env
                )
                
                # Close our file handles (subprocess still has them open)
                stdout_file.close()
                stderr_file.close()
                
                # Wait for process to complete
                await process.wait()
                
                # Read output from temporary files
                with open(stdout_file.name, 'r', errors='ignore') as f:
                    stdout_str = f.read()
                with open(stderr_file.name, 'r', errors='ignore') as f:
                    stderr_str = f.read()
                
                # Append the output to the FFmpeg log file
                with open(ffmpeg_log_path, 'a', errors='ignore') as f:
                    f.write("\n\n--- STDOUT ---\n")
                    f.write(stdout_str)
                    f.write("\n\n--- STDERR ---\n")
                    f.write(stderr_str)
                
                # Clean up temporary files
                try:
                    os.unlink(stdout_file.name)
                    os.unlink(stderr_file.name)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary thumbnail stdout/stderr files: {e}")
            except Exception as e:
                logger.error(f"Error during thumbnail extraction process: {e}", exc_info=True)
                
                # Clean up temp files if they exist
                for temp_file in [stdout_file, stderr_file]:
                    try:
                        if temp_file and os.path.exists(temp_file.name):
                            os.unlink(temp_file.name)
                    except Exception:
                        pass
            
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
                    logger.info(f"No events found for stream {stream_id}, creating minimal chapter file")
                    
                    # Erstelle ein Standard-Event für den ganzen Stream
                    if stream.started_at:
                        # Erstelle ein echtes StreamEvent-Objekt
                        dummy_event = StreamEvent(
                            stream_id=stream_id,
                            timestamp=stream.started_at,
                            title=stream.title or "Stream",
                            category_name=stream.category_name or "Stream",
                            event_type='category_change'
                        )
                        events = [dummy_event]
                    else:
                        logger.warning(f"Cannot create minimal chapters for stream {stream_id} - missing started_at")
                        # Return None to indicate no chapters could be created
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
        
        # Sort events by timestamp to ensure proper processing
        sorted_events = sorted(events, key=lambda x: x.timestamp)
        
        # Process pre-stream events if they exist
        if stream.started_at:
            # Check for pre-stream events
            pre_stream_events = [event for event in sorted_events if event.timestamp < stream.started_at]
            
            if pre_stream_events:
                # If we have pre-stream events, use the latest one as the first chapter starting at time 0
                latest_pre_stream = max(pre_stream_events, key=lambda x: x.timestamp)
                
                # Create a copy of this event but set timestamp to stream start
                adjusted_event = copy.deepcopy(latest_pre_stream)
                adjusted_event.timestamp = stream.started_at
                
                # Filter out all pre-stream events from the original list
                post_stream_events = [event for event in sorted_events if event.timestamp >= stream.started_at]
                
                # Combine the adjusted event with post-stream events
                processed_events = [adjusted_event] + post_stream_events
                
                logger.info(f"Using pre-stream event '{latest_pre_stream.title or 'Unknown'}' as first chapter")
                return duration, processed_events
        
        # If there are no events at all, create a single event for the entire stream
        if not sorted_events and stream.started_at:
            logger.info("No events found, creating a single chapter for entire stream")
            default_event = StreamEvent(
                stream_id=stream.id,
                event_type="stream.online",
                title=stream.title or "Stream",
                category_name=stream.category_name,
                timestamp=stream.started_at
            )
            return duration, [default_event]
        
        return duration, sorted_events
    
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
                
                # Log how many chapters we're creating
                logger.info(f"Generating {len(filtered_events)} chapters for stream {stream.id}")
                
                # When we have only one chapter, we need special handling for VLC compatibility
                if len(filtered_events) == 1:
                    # Add a special marker that this is a single chapter file
                    f.write("\n# Single-chapter file, VLC may need special handling\n")
                    
                    # For single chapter, explicitly set TIMEBASE to 1/1 instead of 1/1000 for better compatibility
                    f.write("\n[CHAPTER]\n")
                    f.write("TIMEBASE=1/1\n")
                    
                    # Always use 0 as start time for single chapter
                    f.write(f"START=0\n")
                    
                    # Use the actual duration in seconds, not milliseconds
                    duration = 0
                    if stream.started_at and stream.ended_at:
                        duration = int((stream.ended_at - stream.started_at).total_seconds())
                    else:
                        duration = 3600  # Default 1 hour if no duration available
                        
                    f.write(f"END={duration}\n")
                    
                    # Chapter title
                    event = filtered_events[0]
                    if event.category_name:
                        title = f"{event.category_name}"
                    elif hasattr(event, 'title') and event.title:
                        title = f"{event.title}"
                    else:
                        title = "Stream"
                    
                    # Escape special characters for FFmpeg
                    title = self._escape_ffmpeg_metadata(title)
                    f.write(f"title={title}\n")
                    logger.info(f"Created single chapter with title: {title}")
                else:
                    # Multiple chapters - standard handling
                    for i, event in enumerate(filtered_events):
                        # Berechne Start- und Endzeit
                        start_offset_ms, end_offset_ms = self._calculate_ffmpeg_timestamps(i, event, filtered_events, stream)
                        
                        # Kapitel-Titel erstellen
                        if event.category_name:
                            title = f"{event.category_name}"
                        elif hasattr(event, 'title') and event.title:
                            title = f"{event.title}"
                        else:
                            title = "Stream"
                        
                        # Escape special characters for FFmpeg
                        title = self._escape_ffmpeg_metadata(title)
                        
                        # Kapitel-Eintrag schreiben
                        f.write("\n[CHAPTER]\n")
                        f.write("TIMEBASE=1/1000\n")
                        f.write(f"START={start_offset_ms}\n")
                        f.write(f"END={end_offset_ms}\n")
                        f.write(f"title={title}\n")
                        
                        logger.debug(f"Created chapter {i+1}/{len(filtered_events)}: {title}, {start_offset_ms}ms to {end_offset_ms}ms")
                
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
                        timestamp_ms = total_seconds * 1000;
                        
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
        """Embed both chapters and all other metadata in one pass."""
        try:
            logger.info(f"Starting metadata embedding for stream {stream_id}, mp4: {mp4_path}")
            mp4_path_obj = Path(mp4_path)
            
            # Import logging service
            from app.services.logging_service import logging_service
            
            # Validate source file exists and has reasonable size
            if not mp4_path_obj.exists():
                logger.error(f"MP4 file does not exist: {mp4_path}")
                logging_service.ffmpeg_logger.error(f"[METADATA_EMBED_FAILED] MP4 file does not exist: {mp4_path}")
                return False
                
            # Check file size to ensure it's not empty or corrupted
            mp4_size = mp4_path_obj.stat().st_size
            if mp4_size < 10000:
                logger.error(f"MP4 file is too small ({mp4_size} bytes), likely corrupted: {mp4_path}")
                logging_service.ffmpeg_logger.error(f"[METADATA_EMBED_FAILED] MP4 file too small: {mp4_path}, {mp4_size} bytes")
                return False
                
            logger.info(f"Source MP4 validation passed: {mp4_path}, size: {mp4_size} bytes")
            
            # Initialize chapters_path_obj
            chapters_path_obj = Path(chapters_path) if chapters_path else None
            logger.debug(f"Using chapters file: {chapters_path}")
            
            # Create unique log file for validation with streamer name
            timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # Extract streamer name from file path if possible
            streamer_name = "unknown"
            if mp4_path_obj.name:
                name_parts = mp4_path_obj.stem.split('-')
                if name_parts:
                    streamer_name = name_parts[0]
            validation_log_path = logging_service.get_ffmpeg_log_path(f"metadata_validate_{timestamp_str}", streamer_name)
            
            # Validate the MP4 file using ffprobe to ensure it's not corrupted
            logger.info(f"Validating MP4 file with ffprobe: {mp4_path}")
            validate_cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,duration,width,height",
                "-of", "json",
                str(mp4_path_obj)
            ]
            
            # Log the validation command
            logging_service.ffmpeg_logger.info(f"[METADATA_VALIDATION_START] Validating MP4: {mp4_path}")
            logging_service.ffmpeg_logger.info(f"[FFPROBE_CMD] {' '.join(validate_cmd)}")
            
            # Set up environment for ffprobe log - ensure logs go only to file
            env = os.environ.copy()
            env["FFREPORT"] = f"file={validation_log_path}:level=32"
            env["AV_LOG_FORCE_NOCOLOR"] = "1"  # Disable ANSI color in logs
            env["AV_LOG_FORCE_STDERR"] = "0"   # Don't force stderr output
            
            # Add quiet logging level to command to prevent output to console
            validate_cmd = [validate_cmd[0]] + ["-loglevel", "quiet"] + validate_cmd[1:]
            
            # Create temporary files for stdout/stderr to prevent console logging
            with tempfile.NamedTemporaryFile(delete=False, prefix="ffprobe_stdout_", suffix=".log") as stdout_file, \
                 tempfile.NamedTemporaryFile(delete=False, prefix="ffprobe_stderr_", suffix=".log") as stderr_file:
                
                # Start process with redirected output
                validate_process = await asyncio.create_subprocess_exec(
                    *validate_cmd,
                    stdout=stdout_file.fileno(),
                    stderr=stderr_file.fileno(),
                    env=env
                )
                
                # Wait for process to complete
                await validate_process.wait()
                
                # Read output from temporary files
                with open(stdout_file.name, 'r', errors='ignore') as f:
                    stdout = f.read().encode('utf-8')
                with open(stderr_file.name, 'r', errors='ignore') as f:
                    stderr = f.read().encode('utf-8')
                
                # Clean up temporary files
                os.unlink(stdout_file.name)
                os.unlink(stderr_file.name)
            
            validate_stdout, validate_stderr = await validate_process.communicate()
            
            if validate_process.returncode != 0:
                error_message = validate_stderr.decode('utf-8', errors='ignore')
                logger.error(f"MP4 file validation failed: {error_message}")
                logging_service.ffmpeg_logger.error(f"[METADATA_VALIDATION_FAILED] MP4 validation failed: {error_message}")
                return False
                
            # Parse the validation output to confirm video stream is present
            try:
                import json
                validation_data = json.loads(validate_stdout.decode('utf-8', errors='ignore'))
                if "streams" not in validation_data or len(validation_data["streams"]) == 0:
                    logger.error(f"No video streams found in MP4: {mp4_path}")
                    logging_service.ffmpeg_logger.error(f"[METADATA_VALIDATION_FAILED] No video streams found: {mp4_path}")
                    return False
                
                # Log video details
                stream = validation_data["streams"][0]
                codec = stream.get("codec_name", "unknown")
                width = stream.get("width", "unknown")
                height = stream.get("height", "unknown")
                duration = stream.get("duration", "unknown")
                
                logger.info(f"MP4 file validation successful: {codec}, {width}x{height}, duration: {duration}s")
                logging_service.ffmpeg_logger.info(
                    f"[METADATA_VALIDATION_SUCCESS] MP4 validated: {mp4_path}, codec: {codec}, "
                    f"resolution: {width}x{height}, duration: {duration}s"
                )
            except Exception as e:
                logger.error(f"Error parsing validation result: {e}")
                # Continue even if parsing fails as the ffprobe command succeeded
            
            # Get stream and streamer information
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.error(f"Stream not found with ID {stream_id}")
                    return False
                
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
            
            # Check if the chapters file exists and is valid
            has_chapters = False
            if chapters_path_obj and chapters_path_obj.exists():
                with open(str(chapters_path_obj), 'r', encoding='utf-8') as f:
                    chapter_lines = f.readlines()
                has_chapters = len(chapter_lines) > 0
                logger.info(f"Found chapters file with {len(chapter_lines)} lines")
            else:
                logger.info(f"No chapters file found at: {chapters_path}")
            
            # Create temporary metadata file with all metadata
            meta_path = mp4_path_obj.with_name(f"{mp4_path_obj.stem}-combined-metadata-{timestamp_str}.txt")
            logger.info(f"Creating combined metadata file: {meta_path}")
            
            with open(str(meta_path), 'w', encoding='utf-8') as f:
                f.write(";FFMETADATA1\n")
                
                # Add basic metadata
                if stream:
                    if stream.title:
                        title = self._escape_ffmpeg_metadata(stream.title)
                        f.write(f"title={title}\n")
                    
                    if metadata and metadata.stream_id:
                        f.write(f"comment=Stream ID: {metadata.stream_id}\n")
                    
                    if stream.started_at:
                        date_str = stream.started_at.strftime("%Y-%m-%d")
                        f.write(f"date={date_str}\n")
                    
                    if stream.category_name:
                        genre = self._escape_ffmpeg_metadata(stream.category_name)
                        f.write(f"genre={genre}\n")
                
                if streamer and streamer.username:
                    artist = self._escape_ffmpeg_metadata(streamer.username)
                    f.write(f"artist={artist}\n")
                
                # Add encoding metadata
                f.write("encoded_by=StreamVault\n")
                f.write("encoding_tool=StreamVault\n")
                f.write(f"metadata_date={datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                
                # Add chapters if available
                if has_chapters:
                    f.write("\n")
                    in_header = True
                    chapter_count = 0
                    for line in chapter_lines:
                        if line.strip() == "[CHAPTER]":  # New chapter begins
                            in_header = False
                            chapter_count += 1
                        
                        if not in_header or line.strip() == "":  # Empty lines or chapter content
                            f.write(line)
                    
                    logger.info(f"Added {chapter_count} chapters to metadata file")
                else:
                    logger.warning(f"No valid chapters file available: {chapters_path}")
            
            # Import remux function from utilities
            from app.utils.file_utils import remux_file
            
            temp_output = f"{str(mp4_path_obj)}.temp_{timestamp_str}.mp4"
            streamer_name = streamer.username if streamer else "unknown"
            
            # Call the remux_file utility with logging service
            logger.info(f"Embedding metadata with remux_file method...")
            logger.debug(f"Starting remux process: input={mp4_path}, output={temp_output}, metadata={meta_path}")
            
            # Log metadata operation through the logging service
            logging_service.ffmpeg_logger.info(f"[METADATA_EMBED_START] {streamer_name}, stream ID: {stream_id}, file: {mp4_path}")
            
            # Log command details to ffmpeg log
            ffmpeg_cmd = [
                "ffmpeg", 
                "-i", str(mp4_path_obj), 
                "-i", str(meta_path), 
                "-map_metadata", "1", 
                "-c", "copy", 
                "-movflags", "+faststart",
                "-y", 
                temp_output
            ]
            logging_service.log_ffmpeg_start("metadata_embed", ffmpeg_cmd, f"{streamer_name}_stream{stream_id}")
            
            # Call remux with detailed logging
            result = await remux_file(
                input_path=str(mp4_path_obj), 
                output_path=temp_output,
                overwrite=True, 
                metadata_file=str(meta_path),
                streamer_name=f"{streamer_name}_stream{stream_id}",
                logging_service=logging_service
            )
            
            success = False
            if result["success"]:
                # Verify the temp file exists and has reasonable size
                if os.path.exists(temp_output):
                    temp_file_size = os.path.getsize(temp_output)
                    logger.info(f"Remux completed, temp file size: {temp_file_size} bytes")
                    
                    # Validate the output MP4 file with ffprobe
                    validate_output_cmd = [
                        "ffprobe",
                        "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "json",
                        temp_output
                    ]
                    
                    validate_output_process = await asyncio.create_subprocess_exec(
                        *validate_output_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    validate_output_stdout, validate_output_stderr = await validate_output_process.communicate()
                    
                    if validate_output_process.returncode != 0:
                        error_msg = f"Output file validation failed: {validate_output_stderr.decode('utf-8', errors='ignore')}"
                        logger.error(error_msg)
                        logging_service.ffmpeg_logger.error(f"[METADATA_EMBED_FAILED] {error_msg}")
                        if os.path.exists(temp_output):
                            os.remove(temp_output)
                        return False
                    
                    # Check if output file is not too small (which would indicate corruption)
                    if temp_file_size > (mp4_size * 0.9):  # Should be at least 90% of original
                        # Replace original with temp file
                        logger.info(f"Temp file passed validation, replacing original file")
                        os.replace(temp_output, str(mp4_path_obj))
                        logger.info(f"Successfully embedded metadata into {mp4_path}")
                        logging_service.ffmpeg_logger.info(f"[METADATA_EMBED_SUCCESS] {streamer_name}: {mp4_path}")
                        success = True
                    else:
                        error_msg = f"Output file appears corrupted: size {temp_file_size} bytes is significantly smaller than original {mp4_size} bytes"
                        logger.error(error_msg)
                        logging_service.ffmpeg_logger.error(f"[METADATA_EMBED_FAILED] {streamer_name}: {error_msg}")
                        # Keep the original file, don't replace it
                        if os.path.exists(temp_output):
                            os.remove(temp_output)
                else:
                    error_msg = "Temp output file was not created"
                    logger.error(error_msg)
                    logging_service.ffmpeg_logger.error(f"[METADATA_EMBED_FAILED] {streamer_name}: {error_msg}")
            else:
                error_msg = f"Failed to embed metadata: {result.get('stderr', 'Unknown error')}"
                logger.error(error_msg)
                logging_service.ffmpeg_logger.error(f"[METADATA_EMBED_FAILED] {streamer_name}: {error_msg}")
                # Clean up temp file if it exists despite failure
                if os.path.exists(temp_output):
                    os.remove(temp_output)
            
            # Delete temporary metadata file
            if os.path.exists(str(meta_path)):
                os.remove(str(meta_path))
                logger.debug(f"Deleted temporary metadata file: {meta_path}")
            
            # Update database
            if success:
                logger.info(f"Updating database to mark metadata as embedded for stream {stream_id}")
                with SessionLocal() as db:
                    stream_metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                    if stream_metadata:
                        stream_metadata.metadata_embedded = True
                        stream_metadata.metadata_embedded_at = datetime.now(timezone.utc)
                        db.commit()
                        logger.info(f"Updated database for stream {stream_id}, metadata marked as embedded")
                        logging_service.ffmpeg_logger.info(f"[DATABASE_UPDATE] {streamer_name}, metadata marked as embedded for stream {stream_id}")
                    else:
                        logger.warning(f"No metadata record found for stream {stream_id}")
                        logging_service.ffmpeg_logger.warning(f"[DATABASE_WARNING] No metadata record found for stream {stream_id} ({streamer_name})")
            
            # Create additional chapter files for various media servers
            if success:
                logger.info(f"Creating additional chapter files for media servers")
                await self._create_media_server_chapters(stream_id, mp4_path, use_category_as_chapter_title=False)
                logging_service.ffmpeg_logger.info(f"[CHAPTERS_CREATED] Additional chapter files for stream {stream_id} ({streamer_name})")
            
            status_str = 'Success' if success else 'Failed'
            logger.info(f"Metadata embedding process completed with status: {status_str}")
            logging_service.ffmpeg_logger.info(f"[METADATA_EMBED_COMPLETE] {streamer_name} - Status: {status_str}")
            return success
        except Exception as e:
            logger.error(f"Error embedding all metadata: {e}", exc_info=True)
            from app.services.logging_service import logging_service
            logging_service.ffmpeg_logger.error(f"[METADATA_EMBED_EXCEPTION] Unhandled error: {str(e)}")
            return False
    
    async def _create_media_server_chapters(self, stream_id: int, mp4_path: str, use_category_as_chapter_title: bool = False) -> None:
        """Create additional chapter files for better media server compatibility
        
        Args:
            stream_id: ID of the stream
            mp4_path: Path to the MP4 file
            use_category_as_chapter_title: Whether to use category as chapter title
        """
        try:
            mp4_path_obj = Path(mp4_path)
            base_path = mp4_path_obj.with_suffix('')
            
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.warning(f"Stream {stream_id} not found for media server chapter creation")
                    return
                
                events = db.query(StreamEvent).filter(StreamEvent.stream_id == stream_id).order_by(StreamEvent.timestamp).all()
                if not events:
                    logger.warning(f"No events found for stream {stream_id}, cannot create media server chapters")
                    return
                
                # 1. Create Plex-compatible chapters.txt file
                plex_chapters_path = f"{base_path}.chapters.txt"
                await self._create_plex_chapters_file(stream, events, plex_chapters_path, use_category_as_chapter_title)
                
                # 2. Create standard WebVTT file with exact filename for maximum compatibility
                vtt_path = f"{base_path}.vtt"
                if os.path.exists(f"{base_path}.vtt") and not os.path.samefile(f"{base_path}.vtt", vtt_path):
                    import shutil
                    shutil.copy2(f"{base_path}.vtt", vtt_path)
                    
                logger.info(f"Created additional chapter files for media server compatibility")
                
        except Exception as e:
            logger.error(f"Error creating media server chapters: {e}")
    
    async def _create_plex_chapters_file(
        self, 
        stream: Stream, 
        events: List[StreamEvent], 
        output_path: str,
        use_category_as_chapter_title: bool = False
    ) -> bool:
        """Create a chapter file in Plex-compatible format
        
        Args:
            stream: Stream object
            events: List of stream events
            output_path: Output path for the chapters file
            use_category_as_chapter_title: Whether to use category as chapter title
            
        Returns:
            bool: True on success, False on failure
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Format: CHAPTER01=00:00:00.000
                #         CHAPTER01NAME=Chapter Title
                
                # Sort events and filter duplicates
                sorted_events = sorted(events, key=lambda x: x.timestamp)
                last_category = None
                chapter_events = []
                
                for event in sorted_events:
                    # Skip consecutive events with same category if we're using category as title
                    if use_category_as_chapter_title:
                        if event.category_name != last_category:
                            chapter_events.append(event)
                            last_category = event.category_name
                    else:
                        # When using stream title, include all events
                        chapter_events.append(event)
                
                # Always ensure at least one chapter
                if not chapter_events and stream.started_at:
                    # Add a single chapter for the whole stream
                    dummy_event = StreamEvent(
                        stream_id=stream.id,
                        event_type="stream.online",
                        title=stream.title,
                        category_name=stream.category_name,
                        timestamp=stream.started_at
                    )
                    chapter_events = [dummy_event]
                
                # Write chapters
                for i, event in enumerate(chapter_events):
                    # Calculate offset in seconds
                    if stream.started_at:
                        offset_seconds = max(0, (event.timestamp - stream.started_at).total_seconds())
                    else:
                        offset_seconds = 0
                    
                    # Format time as HH:MM:SS.mmm
                    hours = int(offset_seconds // 3600)
                    minutes = int((offset_seconds % 3600) // 60)
                    seconds = offset_seconds % 60
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
                    
                    # Format chapter number (CHAPTER01, CHAPTER02, etc.)
                    chapter_num = f"CHAPTER{i+1:02d}"
                    
                    # Get chapter title based on settings
                    if use_category_as_chapter_title and event.category_name:
                        title = event.category_name
                    elif event.title:
                        title = event.title
                    else:
                        title = f"Chapter {i+1}"
                    
                    # Write entry
                    f.write(f"{chapter_num}={time_str}\n")
                    f.write(f"{chapter_num}NAME={title}\n")
                
                logger.info(f"Created Plex-compatible chapters file with {len(chapter_events)} chapters")
                return True
        except Exception as e:
            logger.error(f"Error creating Plex chapters file: {e}")
            return False
            
    def _escape_ffmpeg_metadata(self, text: str) -> str:
        """Escape special characters for FFmpeg metadata format
        
        Args:
            text: Text to escape
            
        Returns:
            str: Escaped text
        """
        if not text:
            return "Untitled"
        # Escape =, ;, # and \ characters as they have special meaning in FFmpeg metadata
        return text.replace('=', '\\=').replace(';', '\\;').replace('#', '\\#').replace('\\', '\\\\')
    
    def _format_xml_time(self, seconds: float) -> str:
        """Formatiert Sekunden in das XML-Format für MP4Box/Matroska: HH:MM:SS.nnnnnnnnn.
        
        Returns:
            str: Formatierter Zeitstempel
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:09.6f}"
