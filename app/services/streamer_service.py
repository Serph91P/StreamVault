from sqlalchemy.orm import Session
from app.models import Streamer, Stream, StreamEvent, NotificationSettings  # Add NotificationSettings
from app.database import SessionLocal  # Add SessionLocal
from app.schemas.streamers import StreamerResponse, StreamerList
from app.services.websocket_manager import ConnectionManager
from app.events.handler_registry import EventHandlerRegistry
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timezone  # Add datetime and timezone
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
        return [
            {
                "id": streamer.id,
                "twitch_id": streamer.twitch_id,
                "username": streamer.username,  # Changed from display_name
                "is_live": streamer.is_live,
                "title": streamer.title,
                "category_name": streamer.category_name,
                "language": streamer.language,
                "last_updated": streamer.last_updated,
                "profile_image_url": streamer.profile_image_url
            }
            for streamer in streamers
        ]

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

    async def add_streamer(self, username: str) -> Optional[Streamer]:
        """Add a new streamer to the database."""
        try:
            logger.debug(f"Adding streamer: {username}")
            user_data = await self.get_user_data(username)
            
            if not user_data:
                logger.error(f"Could not fetch user data for {username}")
                return None
                
            logger.debug(f"User data retrieved: {user_data}")
            
            # Use the existing db connection from the class
            existing = self.db.query(Streamer).filter(
                Streamer.twitch_id == user_data['id']
            ).first()
            
            if existing:
                logger.debug(f"Streamer already exists: {username}")
                return existing
            
            # Create new streamer
            new_streamer = Streamer(
                twitch_id=user_data['id'],
                username=user_data['login'],
                profile_image_url=user_data['profile_image_url'],
                is_live=False,
                title=None,
                category_name=None,
                language=None,
                last_updated=datetime.now(timezone.utc)
            )
            
            self.db.add(new_streamer)
            self.db.flush()  # Get the ID before creating notification settings
            
            # Create default notification settings
            notification_settings = NotificationSettings(
                streamer_id=new_streamer.id,
                notify_online=True,
                notify_offline=True,
                notify_update=True
            )
            self.db.add(notification_settings)
            
            self.db.commit()
            self.db.refresh(new_streamer)
            
            # Initialize EventSub subscriptions
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

    async def download_profile_image(self, url: str, streamer_id: str) -> str:
        """Download and cache profile image"""
        cache_path = self.image_cache_dir / f"{streamer_id}.jpg"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(cache_path, 'wb') as f:
                            f.write(content)
                        logger.debug(f"Cached profile image for streamer {streamer_id}")
                        return str(cache_path)
        except Exception as e:
            logger.error(f"Failed to cache profile image: {e}")
            return url

        return str(cache_path) if cache_path.exists() else url
