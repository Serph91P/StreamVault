import os
import json
import aiohttp
import asyncio
import logging
import tempfile
import copy  # Add missing import for copy module
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import xml.etree.ElementTree as ET
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Stream, StreamMetadata, StreamEvent, Streamer, RecordingSettings
from app.config.settings import settings
from app.services.system.logging_service import logging_service
from app.services.media.artwork_service import artwork_service
from app.utils.file_utils import sanitize_filename
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

    def _relative_artwork_path(self, nfo_dir: Path, safe_username: str, filename: str) -> Optional[str]:
        """Compute a relative path from an NFO directory to the artwork under recordings/.media/artwork/<user>/filename.

        This walks up from nfo_dir until it finds a ".media" directory sibling (the common recordings root pattern),
        then returns a relative path from nfo_dir to that artwork file. If not found, returns a default 
        relative path that should still work when scanners treat paths as relative to the library root.
        """
        try:
            nfo_dir = Path(nfo_dir)
            current = nfo_dir
            recordings_root = None

            # Walk up looking for a sibling .media directory
            for _ in range(6):  # limit to a reasonable depth
                candidate = current / ".media"
                if candidate.exists() and candidate.is_dir():
                    recordings_root = current
                    break
                # Also check parent sibling
                candidate_parent = current.parent / ".media"
                if candidate_parent.exists() and candidate_parent.is_dir():
                    recordings_root = current.parent
                    break
                current = current.parent
                if current == current.parent:
                    break

            # Build the absolute path to the artwork
            artwork_rel_under_root = Path(".media") / "artwork" / safe_username / filename
            if recordings_root:
                target = recordings_root / artwork_rel_under_root
                # Return a path relative to the NFO directory
                try:
                    rel = os.path.relpath(target, start=nfo_dir)
                    return rel.replace("\\", "/")  # NFO prefers forward slashes
                except Exception:
                    pass

            # Fallback to generic relative path (works if scanners interpret relative to library root)
            return str(artwork_rel_under_root).replace("\\", "/")
        except Exception:
            return f".media/artwork/{safe_username}/{filename}"

    def _find_recordings_root(self, start_dir: Path) -> Optional[Path]:
        """Find the recordings root directory (one that contains a .media folder)."""
        try:
            current = Path(start_dir)
            for _ in range(8):
                if (current / ".media").is_dir():
                    return current
                parent = current.parent
                if parent == current:
                    break
                current = parent
        except Exception:
            pass
        return None

    def _ensure_local_artwork(self, streamer_dir: Path, season_dir: Optional[Path], safe_username: str) -> None:
        """Ensure local copies of key artwork files exist next to NFOs.

        Rationale:
        Some media servers (or certain library / scanner configurations) refuse to follow relative paths
        that traverse outside the immediate show/season folder structure (e.g. paths that effectively
        point to a shared central artwork directory). By placing lightweight copies of the core artwork
        files (poster, fanart, banner) alongside the generated NFO files we maximize compatibility while
        still keeping the canonical originals inside recordings/.media/artwork/<user>/.

        This helper looks for a central artwork directory using _find_recordings_root. If not found it
        cautiously falls back to the parent directory only when that parent actually contains a .media
        folder. Missing artwork is non-fatal; problems are logged at debug level to avoid noise.
        """
        try:
            streamer_dir = Path(streamer_dir)
            root = self._find_recordings_root(streamer_dir)
            if not root:
                parent = streamer_dir.parent
                if parent != streamer_dir and (parent / ".media").is_dir():
                    root = parent

            if not root:
                logger.debug("No recordings root with .media found for %s; skipping local artwork copies", safe_username)
                return

            central_artwork_dir = root / ".media" / "artwork" / safe_username
            if not central_artwork_dir.is_dir():
                logger.debug("Central artwork directory missing for %s: %s", safe_username, central_artwork_dir)
                return

            # Files we want to ensure locally for the show directory
            desired_files = [
                ("poster.jpg", streamer_dir / "poster.jpg"),
                ("fanart.jpg", streamer_dir / "fanart.jpg"),
                ("banner.jpg", streamer_dir / "banner.jpg"),
            ]

            for filename, target_path in desired_files:
                source_path = central_artwork_dir / filename
                if source_path.is_file():
                    if not target_path.exists():
                        try:
                            shutil.copy2(source_path, target_path)
                        except Exception as ce_copy:
                            logger.debug("Failed to copy %s to %s: %s", source_path, target_path, ce_copy)
                else:
                    logger.debug("Expected central artwork file missing: %s", source_path)

            # Season specific: only ensure a poster (others are optional / inherited)
            if season_dir is not None:
                season_dir = Path(season_dir)
                season_poster = season_dir / "poster.jpg"
                if not season_poster.exists():
                    source_poster = central_artwork_dir / "poster.jpg"
                    if source_poster.is_file():
                        try:
                            shutil.copy2(source_poster, season_poster)
                        except Exception as ce_season:
                            logger.debug("Failed to copy poster for season dir %s: %s", season_dir, ce_season)
        except Exception as e_artwork_helper:
            # Swallow all exceptions to keep metadata generation resilient
            logger.debug("_ensure_local_artwork encountered an error for %s: %s", safe_username, e_artwork_helper)

    def _is_within(self, child: Path, parent: Path) -> bool:
        """Return True if 'child' path is the same as or contained within 'parent'.

        Resolves symlinks and normalizes paths. Returns False on error.
        """
        try:
            child_res = Path(child).resolve()
            parent_res = Path(parent).resolve()
            return parent_res == child_res or parent_res in child_res.parents
        except Exception:
            return False

    # Public wrappers (avoid external use of private helpers elsewhere)
    def find_recordings_root(self, start_dir: Path) -> Optional[Path]:  # noqa: D401
        """Public wrapper for locating recordings root (directory containing .media)."""
        return self._find_recordings_root(start_dir)

    def is_within(self, child: Path, parent: Path) -> bool:  # noqa: D401
        """Public wrapper for safe path containment check."""
        return self._is_within(child, parent)
    
    async def generate_metadata_for_stream(
        self, 
        stream_id: int, 
        base_path: str,
        base_filename: str
    ) -> bool:
        """Generate all metadata files for a stream
        
        NOTE: This method works with ended streams (ended_at set) since it's called
        during post-processing after the stream has gone offline. We explicitly query
        by stream_id regardless of the stream's ended_at status.
        """
        try:
            with SessionLocal() as db:
                # Query stream by ID only - no filter on ended_at since we need to
                # generate metadata for completed/ended streams during post-processing
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.error(f"Stream {stream_id} not found in database (may have been deleted)")
                    return False
                
                # Fetch streamer
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer {stream.streamer_id} not found for stream {stream_id}")
                    return False
                
                # Resolve base path and filename, but prefer the actual recording path from DB to avoid mismatches
                base_path_obj = Path(base_path)
                try:
                    if getattr(stream, "recording_path", None):
                        rec_path = Path(stream.recording_path)
                        if rec_path.exists():
                            rec_dir = rec_path.parent
                            rec_stem = rec_path.stem
                            # If provided output dir or filename don't match the recorded file, correct them
                            if rec_dir != base_path_obj or rec_stem != base_filename:
                                logger.warning(
                                    "Metadata path mismatch detected; correcting to recording path. "
                                    f"stream_id={stream_id}, provided_dir={base_path_obj}, provided_name={base_filename}, "
                                    f"recording_dir={rec_dir}, recording_name={rec_stem}"
                                )
                                base_path_obj = rec_dir
                                base_filename = rec_stem
                except Exception as e:
                    # Never fail metadata generation due to path correction logic
                    logger.debug(f"Could not validate/correct metadata base path from recording_path: {e}")

                # Enforce that base_path belongs to the correct streamer folder; if not, rebase using recordings root
                try:
                    recordings_root = self._find_recordings_root(base_path_obj)
                    expected_streamer_dir = None
                    if recordings_root and streamer and getattr(streamer, 'username', None):
                        expected_streamer_dir = recordings_root / sanitize_filename(streamer.username)
                        if expected_streamer_dir.exists():
                            # If current base_path is not under expected streamer dir, try to correct
                            if not self._is_within(base_path_obj, expected_streamer_dir):
                                # CRITICAL FIX: Before rebasing, validate that the output_dir actually contains wrong streamer content
                                # This prevents cross-contamination when the wrong streamer context is passed
                                output_dir_str = str(base_path_obj) if base_path_obj else ""
                                base_path_str = str(base_path_obj)
                                
                                # Check if the current path actually belongs to a different streamer
                                path_contains_different_streamer = False
                                if output_dir_str and streamer.username.lower() not in output_dir_str.lower():
                                    # The output_dir doesn't contain current streamer name, this might be cross-contamination
                                    logger.error(
                                        f"CRITICAL: Stream belongs to {streamer.username} but base_path is {base_path_obj}. "
                                        f"This indicates wrong stream-to-recording mapping. Refusing to rebase to prevent cross-contamination."
                                    )
                                    # Instead of rebasing, keep the original path and log the error for investigation
                                    path_contains_different_streamer = True
                                
                                if not path_contains_different_streamer:
                                    logger.warning(
                                        f"Base path {base_path_obj} not under streamer dir {expected_streamer_dir}; attempting to rebase"
                                    )
                                    # Prefer recording_path if available
                                    if getattr(stream, 'recording_path', None):
                                        rp = Path(stream.recording_path)
                                        if rp.exists() and self._is_within(rp, expected_streamer_dir):
                                            base_path_obj = rp.parent
                                            base_filename = rp.stem
                                    else:
                                        # Fallback to computed Season folder
                                        season_dir = expected_streamer_dir / f"Season {stream.started_at.strftime('%Y-%m')}"
                                        season_dir.mkdir(parents=True, exist_ok=True)
                                        base_path_obj = season_dir
                                        # keep base_filename as-is
                except Exception as e:
                    logger.debug(f"Could not enforce streamer directory for metadata paths: {e}")
                
                # Get or create metadata
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                if not metadata:
                    metadata = StreamMetadata(stream_id=stream_id)
                    db.add(metadata)
                    db.commit()
                
                # Run tasks sequentially to avoid DB/file write races under concurrency
                success = True
                
                # 1) JSON metadata
                try:
                    ok = await self.generate_json_metadata(db, stream, streamer, base_path_obj, base_filename, metadata)
                    if not ok:
                        success = False
                except Exception as e:
                    logger.error(f"JSON metadata generation failed: {e}", exc_info=True)
                    success = False

                # 2) NFO files
                try:
                    ok = await self.generate_nfo_file(db, stream, streamer, base_path_obj, base_filename, metadata)
                    if not ok:
                        success = False
                except Exception as e:
                    logger.error(f"NFO generation failed: {e}", exc_info=True)
                    success = False

                # 3) Chapters
                try:
                    ok = await self.ensure_all_chapter_formats(stream_id, str(base_path_obj / f"{base_filename}.mp4"), db)
                    if not ok:
                        success = False
                except Exception as e:
                    logger.error(f"Chapter generation failed: {e}", exc_info=True)
                    success = False

                # 4) Media server files
                try:
                    ok = await self._create_media_server_specific_files(
                        stream,
                        base_path_obj,
                        base_filename=base_filename,
                        streamer=streamer,
                        db=db,
                    )
                    if not ok:
                        success = False
                except Exception as e:
                    logger.error(f"Media server file creation failed: {e}", exc_info=True)
                    success = False

                # Finalize
                try:
                    db.commit()
                except Exception as commit_error:
                    logger.error(f"Failed to commit metadata changes for stream {stream_id}: {commit_error}")
                    db.rollback()
                    return False

                return success
            
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
        """Creates NFO file for Kodi/Plex/Emby with relative image paths."""
        try:
            # Use hidden .media directory to avoid Emby/Jellyfin creating seasons from image folders
            safe_username = sanitize_filename(streamer.username)
            
            # Artwork paths in hidden .media directory (relative to recordings root)
            poster_path = f".media/artwork/{safe_username}/poster.jpg"
            banner_path = f".media/artwork/{safe_username}/banner.jpg" 
            fanart_path = f".media/artwork/{safe_username}/fanart.jpg"
            
            # Episode thumbnail in same directory as video
            episode_thumb_path = None
            local_thumb = base_path / f"{base_filename}-thumb.jpg"
            if local_thumb.exists():
                episode_thumb_path = f"{base_filename}-thumb.jpg"
            else:
                episode_thumb_path = f".media/artwork/{safe_username}/poster.jpg"  # Fallback
            # Create two NFO files:
            # 1. tvshow.nfo - for show/season data (uses streamer image)
            # 2. episode.nfo - for the specific stream episode (uses stream thumbnail)
            
            # Episode NFO always next to the recording file
            episode_nfo_path = base_path / f"{base_filename}.nfo"

            # Work out if we're inside a season folder using a flexible regex (e.g., "Season 01" or "S202401")
            season_hint = False
            try:
                season_hint = bool(re.search(r"(season\s*\d+|s\d+)", base_path.name, re.IGNORECASE))
            except Exception:
                # Be defensive; if anything goes wrong, assume not in a season dir
                season_hint = False

            # Streamer directory logic:
            # - If we're in a season folder, the streamer directory is the parent of the season folder (base_path.parent)
            # - If we're not in a season folder, base_path itself is the streamer directory
            if season_hint:
                streamer_dir = base_path.parent
                season_dir = base_path
            else:
                streamer_dir = base_path
                season_dir = None

            # Validate streamer_dir points to the actual streamer folder; if not, adjust using recordings root
            try:
                recordings_root = self._find_recordings_root(streamer_dir)
                if recordings_root:
                    expected_streamer_dir = recordings_root / sanitize_filename(streamer.username)
                    if expected_streamer_dir.exists():
                        if not self._is_within(streamer_dir, expected_streamer_dir):
                            logger.warning(
                                f"Streamer dir mismatch for NFOs: {streamer_dir} -> {expected_streamer_dir}"
                            )
                            streamer_dir = expected_streamer_dir
                            if season_dir is not None:
                                # Recompute season_dir under corrected streamer_dir
                                try:
                                    season_dir = expected_streamer_dir / f"Season {stream.started_at.strftime('%Y-%m')}"
                                    season_dir.mkdir(parents=True, exist_ok=True)
                                except Exception:
                                    pass
            except Exception:
                pass

            # Show-level NFO must live inside the individual streamer's folder
            tvshow_nfo_path = streamer_dir / "tvshow.nfo"
            # Season NFO belongs into the season folder (when present)
            season_nfo_path = (season_dir / "season.nfo") if season_dir else None
                    
            # 1. Generate Show/Season NFO
            show_root = ET.Element("tvshow")
            
            # Basic metadata
            ET.SubElement(show_root, "title").text = f"{streamer.username} Streams"
            ET.SubElement(show_root, "sorttitle").text = f"{streamer.username} Streams"
            ET.SubElement(show_root, "showtitle").text = f"{streamer.username} Streams"
            
            # Streamer information
            ET.SubElement(show_root, "studio").text = "Twitch"
            ET.SubElement(show_root, "plot").text = f"Streams by {streamer.username} on Twitch."
            
            # Important for Plex: Store artwork in hidden .media directory
            if streamer.profile_image_url:
                # Save artwork to .media directory (avoids Emby creating seasons from folders)
                await artwork_service.save_streamer_artwork(streamer)
                # Ensure local copies (some servers block ../ traversals or outside-library references)
                try:
                    self._ensure_local_artwork(streamer_dir=streamer_dir, season_dir=season_dir, safe_username=safe_username)
                except Exception as e_copy:
                    logger.debug(f"Local artwork copy step failed (non-fatal): {e_copy}")

                # Prefer simple local filenames for maximum compatibility
                poster_element = ET.SubElement(show_root, "thumb", aspect="poster")
                poster_element.text = "poster.jpg"
                banner_element = ET.SubElement(show_root, "thumb", aspect="banner")
                banner_element.text = "banner.jpg"
                fanart = ET.SubElement(show_root, "fanart")
                ET.SubElement(fanart, "thumb").text = "fanart.jpg"
                
            # Genre/Category
            if streamer.category_name:
                ET.SubElement(show_root, "genre").text = streamer.category_name
            else:
                ET.SubElement(show_root, "genre").text = "Livestream"
            
            # Streamer as "actor"
            actor = ET.SubElement(show_root, "actor")
            ET.SubElement(actor, "name").text = streamer.username
            if streamer.profile_image_url:
                # Actor image from .media directory with proper relative path
                actor_thumb_rel = self._relative_artwork_path(streamer_dir, safe_username, "poster.jpg")
                ET.SubElement(actor, "thumb").text = actor_thumb_rel
                
            ET.SubElement(actor, "role").text = "Streamer"
            
            # Write XML
            show_tree = ET.ElementTree(show_root)
            show_tree.write(str(tvshow_nfo_path), encoding="utf-8", xml_declaration=True)
            
            # Create season NFO if in season directory
            if season_dir is not None and season_nfo_path is not None:
                season_root = ET.Element("season")
                
                if stream.started_at:
                    season_num = stream.started_at.strftime("%Y%m")
                    ET.SubElement(season_root, "seasonnumber").text = season_num
                    
                # Season title
                ET.SubElement(season_root, "title").text = f"Season {stream.started_at.strftime('%Y-%m')}"
                
                # Season poster from .media directory
                if streamer.profile_image_url:
                    # Ensure a local poster exists (already attempted above)
                    local_season_poster = season_dir / "poster.jpg"
                    if not local_season_poster.exists():
                        # fallback: copy global poster
                        try:
                            recordings_root = self._find_recordings_root(season_dir) or season_dir.parent
                            central_art = recordings_root / ".media" / "artwork" / safe_username / "poster.jpg"
                            if central_art.exists():
                                shutil.copy2(central_art, local_season_poster)
                        except Exception as ce_season:
                            logger.exception("Failed to copy central season poster to local season directory: %s", ce_season)
                    ET.SubElement(season_root, "thumb").text = "poster.jpg"
                    
                # Write XML
                season_tree = ET.ElementTree(season_root)
                season_tree.write(str(season_nfo_path), encoding="utf-8", xml_declaration=True)
            
            # 2. Generate Episode NFO
            episode_root = ET.Element("episodedetails")
            
            # Unique identifiers to bind this episode to the precise stream
            try:
                uid = ET.SubElement(episode_root, "uniqueid")
                uid.set("type", "streamvault")
                uid.set("default", "true")
                uid.text = str(stream.id)
                if stream.twitch_stream_id:
                    uid2 = ET.SubElement(episode_root, "uniqueid")
                    uid2.set("type", "twitch_stream_id")
                    uid2.text = str(stream.twitch_stream_id)
            except Exception:
                pass
            
            # Episode title: prefer the human title but, when base_filename contains a formatted prefix, use the full filename-like title for consistency
            try:
                display_title = stream.title or f"{streamer.username} Stream"
                # If base_filename already follows "Streamer - SYYYYMME## - Title", reconstruct that as title for scanners
                if base_filename and re.search(r"S\d{6}E\d{2}", base_filename):
                    display_title = base_filename.split("/")[-1]  # Make sure it's just the name
                    # Replace underscores with spaces for readability
                    display_title = display_title.replace("_", " ")
                ET.SubElement(episode_root, "title").text = display_title
            except Exception:
                ET.SubElement(episode_root, "title").text = stream.title or f"{streamer.username} Stream"
            
            # Calculate season/episode. Prefer stored episode_number for month-based numbering; fallback to day-of-month.
            if stream.started_at:
                ET.SubElement(episode_root, "aired").text = stream.started_at.strftime("%Y-%m-%d")
                ET.SubElement(episode_root, "premiered").text = stream.started_at.strftime("%Y-%m-%d")
                ET.SubElement(episode_root, "dateadded").text = stream.started_at.strftime("%Y-%m-%d %H:%M:%S")
                
                # Use year-month as season number (SYYYYMM)
                season_num = stream.started_at.strftime("%Y%m")
                # Prefer DB episode_number if set, else day-of-month
                try:
                    if getattr(stream, "episode_number", None):
                        episode_num = f"{int(stream.episode_number):02d}"
                    else:
                        episode_num = stream.started_at.strftime("%d")
                except Exception:
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
                # Actor image from .media directory
                ET.SubElement(actor, "thumb").text = f".media/artwork/{safe_username}/poster.jpg"
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
            # Save season NFO path too for proper cleanup (only if created)
            try:
                metadata.season_nfo_path = str(season_nfo_path) if season_nfo_path else None
            except Exception:
                # Column may not exist in older schemas; ignore gracefully
                pass
            
            # Create additional symlinks/copies for specific media servers
            await self._create_media_server_specific_files(
                stream=stream, 
                base_path=base_path, 
                episode_thumb_path=episode_thumb_path if episode_thumb_path else None,
                db=db,
                base_filename=base_filename,
                streamer=streamer,
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
                    shutil.copy2(thumb_path, poster_path)
                
                return str(thumb_path)
            
            # Determine thumbnail source
            if local_thumbnail and os.path.exists(local_thumbnail):
                # Copy existing local thumbnail
                shutil.copy2(local_thumbnail, thumb_path)
                shutil.copy2(local_thumbnail, poster_path)
                logger.debug(f"Copied local thumbnail for stream {stream_id} to {thumb_path}")
                return str(thumb_path)
                
            elif thumbnail_url:
                # Download thumbnail from URL
                success = await self._download_image(thumbnail_url, thumb_path)
                if success:
                    # Also save as poster.jpg
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
                    shutil.copy2(extracted_thumb, thumb_path)
                    shutil.copy2(extracted_thumb, poster_path)
                    logger.debug(f"Extracted thumbnail for stream {stream_id} to {thumb_path}")
                    return str(thumb_path)
                    
            logger.warning(f"Could not create thumbnail for stream {stream_id}")
            return None
        except Exception as e:
            logger.error(f"Error processing episode thumbnail: {e}", exc_info=True)
            return None

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
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy2(local_path, target_path)
                    return True
                else:
                    logger.warning(f"Local image file not found: {url}")
                    return False
            
            # Download from URL using unified_image_service
            from app.services.unified_image_service import unified_image_service
            session = await unified_image_service._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'image' in content_type:
                        # Make sure the directory exists
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        
                        # Save the image
                        with open(target_path, 'wb') as f:
                            f.write(await response.read())
                        return True
                    else:
                        logger.warning(f"Invalid content type for image: {content_type}")
                        return False
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
        db: Optional[Session] = None,
        base_filename: Optional[str] = None,
        streamer: Optional[Streamer] = None,
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
            
            # Resolve exact target directory and base filename from the actual recording path when available
            target_dir = base_path
            resolved_base_filename = base_filename
            try:
                if getattr(stream, "recording_path", None):
                    rec_path = Path(stream.recording_path)
                    if rec_path.exists():
                        target_dir = rec_path.parent
                        if not resolved_base_filename:
                            resolved_base_filename = rec_path.stem
            except Exception:
                pass
            if not resolved_base_filename:
                # Fallback to provided base_filename arg or last-resort: infer from files in dir
                try:
                    # Try to pick the first mp4 file in the directory
                    found = next((p.stem for p in target_dir.glob("*.mp4")), None)
                    resolved_base_filename = found or "unknown"
                except Exception:
                    resolved_base_filename = "unknown"
            
            # Falls kein Thumbnail übergeben wurde, versuche es aus den Metadaten oder dem Artwork-Cache zu holen
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

                # Fallback: copy poster from global artwork cache to local folder
                if (not episode_thumb_path) or (episode_thumb_path and not os.path.exists(episode_thumb_path)):
                    try:
                        eff_streamer = streamer
                        if eff_streamer is None:
                            with SessionLocal() as s:
                                eff_streamer = s.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                        if eff_streamer:
                            safe_username = sanitize_filename(eff_streamer.username)
                            recordings_root = self._find_recordings_root(target_dir)
                            if recordings_root:
                                global_poster = recordings_root / ".media" / "artwork" / safe_username / "poster.jpg"
                                if global_poster.exists():
                                    local_poster = target_dir / "poster.jpg"
                                    if not local_poster.exists():
                                        shutil.copy2(global_poster, local_poster)
                                        episode_thumb_path = str(local_poster)
                                        logger.debug(f"Copied global poster to local folder: {local_poster}")
                                    # If season dir, also create season-poster.jpg
                                    if re.search(r"(season\s*\d+|s\d+)", target_dir.name, re.IGNORECASE):
                                        season_poster = target_dir / "season-poster.jpg"
                                        if not season_poster.exists():
                                            shutil.copy2(global_poster, season_poster)
                                            logger.debug(f"Created season poster from global cache: {season_poster}")
                    except Exception as e:
                        logger.warning(f"Could not copy poster from artwork cache: {e}")
            
            # Create thumbnail and metadata files specific to each media server
            if episode_thumb_path and os.path.exists(episode_thumb_path):
                
                # Plex specific files - always create these for maximum compatibility
                if "plex" in filename_preset or True:  # Always create Plex files
                    # Plex prefers poster.jpg in the same directory
                    plex_poster = target_dir / "poster.jpg"
                    if not plex_poster.exists():
                        shutil.copy2(episode_thumb_path, plex_poster)
                        logger.debug(f"Created Plex poster: {plex_poster}")
                    
                    # Stelle sicher, dass das Standard-Thumbnail existiert
                    plex_thumb = target_dir / f"{resolved_base_filename}-thumb.jpg"
                    if not plex_thumb.exists():
                        shutil.copy2(episode_thumb_path, plex_thumb)
                        logger.debug(f"Created standard thumb: {plex_thumb}")
                    
                    # Create season poster(s) in the season directory if we're inside one
                    if re.search(r"(season\s*\d+|s\d+)", target_dir.name, re.IGNORECASE):
                        season_poster1 = target_dir / "season-poster.jpg"
                        season_poster2 = target_dir / "poster.jpg"
                        for sp in [season_poster1, season_poster2]:
                            if not sp.exists() and os.path.exists(episode_thumb_path):
                                shutil.copy2(episode_thumb_path, sp)
                                logger.debug(f"Created season image: {sp}")
                
                # Kodi specific files
                if "kodi" in filename_preset or True:  # Always create Kodi files
                    # Kodi uses .tbn extension for thumbnails
                    kodi_tbn = target_dir / f"{resolved_base_filename}.tbn"
                    if not kodi_tbn.exists():
                        shutil.copy2(episode_thumb_path, kodi_tbn)
                        logger.debug(f"Created Kodi thumbnail: {kodi_tbn}")
                
                # Emby/Jellyfin specific files
                if any(server in filename_preset for server in ["emby", "jellyfin"]) or True:
                    # Emby/Jellyfin also like poster.jpg
                    poster_jpg = target_dir / "poster.jpg"
                    if not poster_jpg.exists():
                        shutil.copy2(episode_thumb_path, poster_jpg)
                        logger.debug(f"Created Emby poster: {poster_jpg}")
            else:
                logger.warning(f"No episode thumbnail available to create media server specific files for {stream.id}")
            
            # Create specific nfo link based on the preset
            # For example, Plex sometimes requires SXXEXX format in the filename
            if "plex" in filename_preset and stream.started_at:
                season_num = stream.started_at.strftime("%Y%m")
                # Use monthly episode numbering when available (fallback to day-of-month)
                try:
                    if getattr(stream, "episode_number", None):
                        episode_num = f"{int(stream.episode_number):02d}"
                    else:
                        episode_num = stream.started_at.strftime("%d")
                except Exception:
                    episode_num = stream.started_at.strftime("%d")
                
                # Resolve streamer name safely; prefer provided streamer object from caller when available
                streamer_name = ""
                try:
                    if streamer and getattr(streamer, "username", None):
                        streamer_name = streamer.username
                    else:
                        with SessionLocal() as session:
                            s_obj = session.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                            if s_obj:
                                streamer_name = s_obj.username
                except Exception:
                    pass
                
                # Plex pattern: ShowName - SXXEXX - EpisodeTitle
                plex_name = f"{streamer_name} - S{season_num}E{episode_num}"
                if stream.title:
                    plex_name += f" - {stream.title}"
                
                # Clean the filename
                plex_name = plex_name.replace('/', '-').replace('\\', '-').replace(':', '-')
                
                # Determine the streamer folder name from target_dir
                try:
                    target_streamer_dir = target_dir.parent if re.search(r"(season\s*\d+|s\d+)", target_dir.name, re.IGNORECASE) else target_dir
                    target_streamer_name = target_streamer_dir.name
                    if sanitize_filename(streamer_name) != sanitize_filename(target_streamer_name):
                        logger.warning(
                            f"Refusing to create Plex links for streamer '{streamer_name}' inside folder '{target_streamer_name}'"
                        )
                        return True  # Skip creating links to avoid cross-stream pollution
                except Exception:
                    pass

                # Extra safety: ensure target_dir lies within the recordings root for this streamer
                try:
                    recordings_root = self._find_recordings_root(target_dir)
                    if recordings_root and streamer_name:
                        expected_streamer_dir = recordings_root / sanitize_filename(streamer_name)
                        if expected_streamer_dir.exists() and not self._is_within(target_streamer_dir, expected_streamer_dir):
                            logger.warning(
                                f"Target dir {target_streamer_dir} is not within expected streamer dir {expected_streamer_dir}; skipping Plex link creation"
                            )
                            return True
                except Exception:
                    pass

                # Create symlinks for video and nfo files with Plex naming
                video_src = None
                nfo_src = None
                try:
                    # Prefer exact recording path
                    if getattr(stream, "recording_path", None):
                        rp = Path(stream.recording_path)
                        if rp.exists():
                            video_src = rp
                            nfo_candidate = rp.with_suffix(".nfo")
                            if nfo_candidate.exists():
                                nfo_src = nfo_candidate
                    if video_src is None:
                        # Fallback: derive from target_dir + resolved_base_filename
                        candidate = target_dir / f"{resolved_base_filename}.mp4"
                        if candidate.exists():
                            video_src = candidate
                        nfo_candidate = target_dir / f"{resolved_base_filename}.nfo"
                        if nfo_candidate.exists():
                            nfo_src = nfo_candidate
                except Exception:
                    pass

                # Safety: ensure we are writing inside the same streamer directory to avoid cross-stream links
                if video_src and video_src.exists() and self._is_within(video_src, target_dir):
                    try:
                        video_dest = target_dir / f"{plex_name}.mp4"
                        
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
                
                if nfo_src and nfo_src.exists() and self._is_within(nfo_src, target_dir):
                    try:
                        nfo_dest = target_dir / f"{plex_name}.nfo"
                        
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
        Uses FFmpeg for all video formats.
        """
        try:
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                logger.warning(f"Video file not found for thumbnail extraction: {video_path}")
                return None

            # Target thumbnail path (e.g., VideoName_thumbnail.jpg)
            thumb_name = f"{video_path_obj.stem}_thumbnail.jpg"
            thumbnail_path = video_path_obj.with_name(thumb_name)

            # Reuse existing thumbnail if present
            if thumbnail_path.exists() and thumbnail_path.stat().st_size > 1000:
                logger.info(f"Using existing thumbnail at {thumbnail_path}")
                if stream_id and db:
                    metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                    if metadata and not getattr(metadata, 'thumbnail_path', None):
                        metadata.thumbnail_path = str(thumbnail_path)
                        db.commit()
                return str(thumbnail_path)

            # Check if the file has a video stream first (skip audio-only)
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
            check_stdout, _ = await check_process.communicate()
            if check_process.returncode != 0 or not check_stdout or "video" not in check_stdout.decode("utf-8", errors="ignore").lower():
                logger.info(f"Audio-only file detected, skipping thumbnail extraction: {video_path}")
                return None

            # FFmpeg command to grab a frame at 10s for better quality
            cmd = [
                "ffmpeg",
                "-ss", "00:00:10",
                "-i", str(video_path_obj),
                "-vframes", "1",
                "-q:v", "2",
                "-f", "image2",
                "-y",
                str(thumbnail_path)
            ]

            # Create a unique log file for this thumbnail extraction
            streamer_name = video_path_obj.stem.split('-')[0] if '-' in video_path_obj.stem else 'unknown'
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ffmpeg_log_path = logging_service.get_ffmpeg_log_path(f"thumbnail_{timestamp}", streamer_name)
            os.makedirs(os.path.dirname(ffmpeg_log_path), exist_ok=True)

            # Set up environment and quiet logging
            env = os.environ.copy()
            env["FFREPORT"] = f"file={ffmpeg_log_path}:level=40"
            env["AV_LOG_FORCE_NOCOLOR"] = "1"
            env["AV_LOG_FORCE_STDERR"] = "0"
            cmd.extend(["-loglevel", "quiet"])

            import tempfile
            stdout_file = tempfile.NamedTemporaryFile(delete=False, prefix="ffmpeg_thumb_stdout_", suffix=".log")
            stderr_file = tempfile.NamedTemporaryFile(delete=False, prefix="ffmpeg_thumb_stderr_", suffix=".log")
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=stdout_file.fileno(),
                    stderr=stderr_file.fileno(),
                    env=env
                )
                stdout_file.close()
                stderr_file.close()
                await process.wait()

                # Append temp outputs to the ffmpeg log
                try:
                    with open(stdout_file.name, 'r', errors='ignore') as f:
                        stdout_str = f.read()
                    with open(stderr_file.name, 'r', errors='ignore') as f:
                        stderr_str = f.read()
                    with open(ffmpeg_log_path, 'a', errors='ignore') as f:
                        f.write("\n\n--- STDOUT ---\n")
                        f.write(stdout_str)
                        f.write("\n\n--- STDERR ---\n")
                        f.write(stderr_str)
                finally:
                    try:
                        os.unlink(stdout_file.name)
                        os.unlink(stderr_file.name)
                    except Exception as e:
                        logger.warning(f"Failed to clean up temporary thumbnail stdout/stderr files: {e}")
            except Exception as e:
                logger.error(f"Error during thumbnail extraction process: {e}", exc_info=True)

            # Verify thumbnail
            if thumbnail_path.exists() and thumbnail_path.stat().st_size > 0:
                logger.info(f"Successfully extracted thumbnail to {thumbnail_path}")
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
                    logger.warning(f"Stream with ID {stream_id} not found for chapter generation (likely deleted during post-processing)")
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
                    
                    # Try to save XML path - gracefully handle if column doesn't exist
                    try:
                        metadata.chapters_xml_path = str(xml_chapters_path)
                    except Exception as e:
                        logger.warning(f"Could not save chapters_xml_path (migration may be pending): {e}")
                    
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
                
                # Sort events by timestamp and include ALL events (no dedup) to ensure correctness
                filtered_events = sorted(events, key=lambda x: x.timestamp)
                
                # If we have no events, create a default one covering the whole stream
                if not filtered_events and stream.category_name:
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
            from app.services.system.logging_service import logging_service
            
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
            
            # Get stream and streamer information
            with SessionLocal() as db:
                stream = db.query(Stream).filter(Stream.id == stream_id).first()
                if not stream:
                    logger.error(f"Stream not found: {stream_id}")
                    return False
                    
                streamer = db.query(Streamer).filter(Streamer.id == stream.streamer_id).first()
                if not streamer:
                    logger.error(f"Streamer not found: {stream.streamer_id}")
                    return False
                
                metadata = db.query(StreamMetadata).filter(StreamMetadata.stream_id == stream_id).first()
                if not metadata:
                    logger.error(f"Metadata not found for stream: {stream_id}")
                    return False
                
                # Create temporary output file for metadata embedding
                temp_output = f"{mp4_path}.metadata.tmp"
                
                try:
                    # Embed metadata using FFmpeg
                    success = await self.embed_metadata_with_ffmpeg_service(
                        db, stream, streamer, mp4_path, temp_output, metadata
                    )
                    
                    if success and os.path.exists(temp_output):
                        # Replace original file with the metadata-embedded version
                        shutil.move(temp_output, mp4_path)
                        logger.info(f"Successfully embedded metadata using FFmpeg for stream {stream_id}")
                        logging_service.ffmpeg_logger.info(f"[METADATA_EMBED_SUCCESS] FFmpeg metadata embedding successful: {mp4_path}")
                        return True
                    else:
                        logger.error(f"FFmpeg metadata embedding failed for stream {stream_id}")
                        logging_service.ffmpeg_logger.error(f"[METADATA_EMBED_FAILED] FFmpeg metadata embedding failed: {mp4_path}")
                        return False
                
                except Exception as e:
                    logger.error(f"Error during FFmpeg metadata embedding: {e}")
                    # Clean up temp file if it exists
                    if os.path.exists(temp_output):
                        os.remove(temp_output)
                    return False
            
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
        """Formatiert Sekunden in das XML-Format für FFmpeg/Matroska: HH:MM:SS.nnnnnnnnn.
        
        Returns:
            str: Formatierter Zeitstempel
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:09.6f}"
    
    async def embed_metadata_with_ffmpeg_service(
        self,
        db: Session,
        stream: Stream,
        streamer: Streamer,
        input_path: str,
        output_path: str,
        metadata: StreamMetadata
    ) -> bool:
        """
        Embed metadata into MP4 file using FFmpeg.
        
        Args:
            db: Database session
            stream: Stream object
            streamer: Streamer object
            input_path: Path to input MP4 file
            output_path: Path to output MP4 file
            metadata: StreamMetadata object
            
        Returns:
            bool: True on success, False on error
        """
        try:
            logger.info(f"Embedding metadata using FFmpeg for stream {stream.id}")
            
            # Prepare metadata dictionary for FFmpeg
            metadata_dict = {
                "title": stream.title or "Stream Recording",
                "artist": streamer.username,
                "album": f"{streamer.username} Streams",
                "year": str(stream.started_at.year) if stream.started_at else str(datetime.now().year),
                "genre": stream.category_name or "Gaming",
                "comment": f"Recorded stream from {streamer.username}",
                "description": stream.title or "Twitch stream recording",
                "streamer": streamer.username,
                "game": stream.category_name,
                "stream_date": stream.started_at.strftime("%Y-%m-%d") if stream.started_at else datetime.now().strftime("%Y-%m-%d")
            }
            
            # Get chapter information if available
            chapters = await self._get_chapters_for_ffmpeg(db, stream)
            
            # Build FFmpeg command for metadata embedding
            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-c", "copy",
                "-metadata", f"title={metadata_dict['title']}",
                "-metadata", f"artist={metadata_dict['artist']}",
                "-metadata", f"album={metadata_dict['album']}",
                "-metadata", f"year={metadata_dict['year']}",
                "-metadata", f"genre={metadata_dict['genre']}",
                "-metadata", f"comment={metadata_dict['comment']}",
                "-metadata", f"description={metadata_dict['description']}",
                "-metadata", f"streamer={metadata_dict['streamer']}",
                "-metadata", f"game={metadata_dict['game']}",
                "-metadata", f"stream_date={metadata_dict['stream_date']}",
                "-y",  # Overwrite output file if exists
                output_path
            ]
            
            logger.debug(f"FFmpeg command for metadata embedding: {' '.join(cmd)}")
            
            # Execute FFmpeg command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg metadata embedding failed: {stderr.decode('utf-8', errors='ignore')}")
                return False
            
            logger.info(f"Successfully embedded metadata using FFmpeg for stream {stream.id}")
            return True
        
        except Exception as e:
            logger.error(f"Error embedding metadata with FFmpeg: {e}", exc_info=True)
            return False
    
    async def _get_chapters_for_ffmpeg(self, db: Session, stream: Stream) -> Optional[List[Dict[str, Any]]]:
        """
        Get chapter information formatted for FFmpeg.
        
        Args:
            db: Database session
            stream: Stream object
            
        Returns:
            List of chapter dictionaries or None
        """
        try:
            events = db.query(StreamEvent).filter(StreamEvent.stream_id == stream.id).order_by(StreamEvent.timestamp).all()
            
            if not events:
                return None
            
            chapters = []
            for i, event in enumerate(events):
                # Calculate start time relative to stream start
                start_time = 0
                if stream.started_at and event.timestamp:
                    start_time = (event.timestamp - stream.started_at).total_seconds()
                    if start_time < 0:
                        start_time = 0
                
                chapter = {
                    "start_time": start_time,
                    "title": event.category_name or f"Chapter {i+1}"
                }
                chapters.append(chapter)
            
            return chapters
            
        except Exception as e:
            logger.error(f"Error getting chapters for FFmpeg: {e}")
            return None


# Global metadata service instance
metadata_service = MetadataService()
