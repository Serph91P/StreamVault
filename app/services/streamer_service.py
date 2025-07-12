from sqlalchemy.orm import Session
from app.models import Streamer, Stream, StreamEvent, NotificationSettings
from app.database import SessionLocal
from app.schemas.streamers import StreamerResponse, StreamerList
from app.services.websocket_manager import ConnectionManager
from app.events.handler_registry import EventHandlerRegistry
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timezone
import logging
import aiohttp
from app.config.settings import settings

logger = logging.getLogger("streamvault")

class StreamerService:
    def __init__(self, db: Session, websocket_manager: ConnectionManager, event_registry: EventHandlerRegistry):
        self.db = db
        self.manager = websocket_manager
        self.event_registry = event_registry
        self.client_id = settings.TWITCH_APP_ID
        self.client_secret = settings.TWITCH_APP_SECRET
        self.base_url = "https://api.twitch.tv/helix"
        self._access_token = None
        self.data_dir = Path("/app/data")
        self.image_cache_dir = self.data_dir / "profile_images"
        self.image_cache_dir.mkdir(parents=True, exist_ok=True)

    async def notify(self, message: Dict[str, Any]):
        try:
            await self.manager.send_notification(message)
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            raise

    async def get_access_token(self) -> str:
        """Get or refresh Twitch access token"""
        if not self._access_token:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://id.twitch.tv/oauth2/token",
                    params={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._access_token = data["access_token"]
                    else:
                        raise ValueError(f"Failed to get access token: {response.status}")
        return self._access_token

    async def get_users_by_login(self, usernames: List[str]) -> List[Dict[str, Any]]:
        token = await self.get_access_token()
        users = []
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/users",
                params={"login": usernames},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", [])
                else:
                    logger.error(f"Failed to get users. Status: {response.status}")
                    return []

    async def get_streamer_info(self, streamer_id: str) -> Optional[Dict[str, Any]]:
        token = await self.get_access_token()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/users",
                params={"id": streamer_id},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["data"][0] if data["data"] else None
                else:
                    logger.error(f"Failed to get streamer info. Status: {response.status}")
                    return None

    async def get_streamers(self) -> List[Dict[str, Any]]:
        streamers = self.db.query(Streamer).all()
        
        # Try to get recording status - fail gracefully if not available
        recording_streamer_ids = set()
        try:
            from app.services.recording.recording_service import RecordingService
            recording_service = RecordingService()
            active_recordings = await recording_service.get_active_recordings()
            recording_streamer_ids = {info['streamer_id'] for info in active_recordings}
        except Exception as e:
            logger.warning(f"Could not get recording status: {e}")
        
        result = []
        for streamer in streamers:
            # Check if recording is enabled for this streamer
            recording_enabled = False
            try:
                from app.services.recording.recording_service import RecordingService
                recording_service = RecordingService()
                recording_enabled = recording_service.config_manager.is_recording_enabled(streamer.id)
            except Exception as e:
                logger.warning(f"Could not check recording status for streamer {streamer.id}: {e}")
            
            result.append({
                "id": streamer.id,
                "twitch_id": streamer.twitch_id,
                "username": streamer.username,
                "is_live": streamer.is_live,
                "is_recording": streamer.id in recording_streamer_ids,
                "recording_enabled": recording_enabled,
                "title": streamer.title,
                "category_name": streamer.category_name,
                "language": streamer.language,
                "last_updated": streamer.last_updated,
                "profile_image_url": streamer.profile_image_url
            })
            
        return result

    async def get_streamer_by_username(self, username: str) -> Optional[Streamer]:
        return self.db.query(Streamer).filter(Streamer.username.ilike(username)).first()

    async def get_user_data(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user data from Twitch API."""
        try:
            users = await self.get_users_by_login([username])
            if users and len(users) > 0:
                return users[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching user data: {e}")
            return None

    async def download_profile_image(self, url: str, streamer_id: str) -> str:
        """Download and cache profile image"""
        file_name = f"{streamer_id}.jpg"
        cache_path = self.image_cache_dir / file_name
        web_path = f"/data/profile_images/{file_name}"
    
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(cache_path, 'wb') as f:
                            f.write(content)
                        logger.debug(f"Cached profile image for streamer {streamer_id}")
                        return web_path
        except Exception as e:
            logger.error(f"Failed to cache profile image: {e}")
            return url

        return web_path if cache_path.exists() else url

    async def add_streamer(self, username: str, display_name: str = None) -> Optional[Streamer]:
        try:
            logger.debug(f"Adding streamer: {username}")
            user_data = await self.get_user_data(username)
        
            if not user_data:
                logger.error(f"Could not fetch user data for {username}")
                return None
            
            logger.debug(f"User data retrieved: {user_data}")
        
            existing = self.db.query(Streamer).filter(
                Streamer.twitch_id == user_data['id']
            ).first()
        
            if existing:
                logger.debug(f"Streamer already exists: {username}")
                return existing
        
            # Cache profile image
            cached_image_path = await self.download_profile_image(
                user_data['profile_image_url'],
                user_data['id']
            )
        
            # Use display_name for better user experience, but store original for API calls
            streamer_name = display_name or user_data.get('display_name') or user_data['login']
        
            # Create new streamer with cached image path and display_name if provided
            new_streamer = Streamer(
                twitch_id=user_data['id'],
                username=streamer_name,  # Use display_name instead of login
                profile_image_url=cached_image_path,
                original_profile_image_url=user_data['profile_image_url'],
                is_live=False,
                title=None,
                category_name=None,
                language=None,
                last_updated=datetime.now(timezone.utc)
            )
        
            self.db.add(new_streamer)
            self.db.flush()
        
            notification_settings = NotificationSettings(
                streamer_id=new_streamer.id,
                notify_online=True,
                notify_offline=True,
                notify_update=True
            )
            self.db.add(notification_settings)
        
            self.db.commit()
            self.db.refresh(new_streamer)
        
            await self.event_registry.subscribe_to_events(user_data['id'])
        
            return new_streamer
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding streamer: {e}")
            raise

    async def delete_streamer(self, streamer_id: int) -> Optional[Dict[str, Any]]:
        try:
            streamer = self.db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                streamer_data = {
                    "twitch_id": streamer.twitch_id,
                    "username": streamer.username
                }
            
                # Delete notification settings first
                self.db.query(NotificationSettings).filter(
                    NotificationSettings.streamer_id == streamer_id
                ).delete()
            
                # Delete the streamer
                self.db.delete(streamer)
                self.db.commit()
        
                await self.notify({
                    "type": "success",
                    "message": f"Removed streamer {streamer_data['username']}"
                })
        
                logger.info(f"Deleted streamer: {streamer_data['username']}")
                return streamer_data
        
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting streamer: {e}")
            raise
    async def subscribe_to_events(self, twitch_id: str):
        await self.event_registry.subscribe_to_events(twitch_id)

    async def get_game_data(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Fetch game data from Twitch API including box art URL."""
        try:
            token = await self.get_access_token()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/games",
                    params={"id": game_id},
                    headers={
                        "Client-ID": self.client_id,
                        "Authorization": f"Bearer {token}"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("data") and len(data["data"]) > 0:
                            game_data = data["data"][0]
                            
                            # Die Box Art URL im Twitch-Format ersetzen wir durch die gewünschte Größe
                            # Format ist normalerweise: https://static-cdn.jtvnw.net/ttv-boxart/123456-{width}x{height}.jpg
                            box_art_url = game_data.get("box_art_url", "")
                            if box_art_url:
                                # Standard-Größe für Box Art
                                box_art_url = box_art_url.replace("{width}", "285").replace("{height}", "380")
                                game_data["box_art_url"] = box_art_url
                                
                            return game_data
                    
                    logger.warning(f"Failed to get game data for ID {game_id}. Status: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching game data: {e}")
            return None

    async def get_stream_info(self, twitch_id: str) -> Optional[Dict[str, Any]]:
        """Get current stream information for a Twitch user to check if they're live"""
        token = await self.get_access_token()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/streams",
                params={"user_id": twitch_id},
                headers={
                    "Client-ID": self.client_id,
                    "Authorization": f"Bearer {token}"
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["data"][0] if data["data"] else None
                else:
                    logger.error(f"Failed to get stream info. Status: {response.status}")
                    return None
