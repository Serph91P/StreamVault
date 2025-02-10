from sqlalchemy.orm import Session
from twitchAPI.twitch import Twitch
from app.models import Streamer, Stream, StreamEvent
from app.schemas.streamers import StreamerResponse, StreamerList
from app.services.websocket_manager import ConnectionManager
from typing import Dict, Any, Optional, List
import logging
import aiohttp
from app.config.settings import settings

logger = logging.getLogger("streamvault")

class StreamerService:
    def __init__(self, db: Session, twitch: Twitch, websocket_manager: ConnectionManager):
        self.db = db
        self.twitch = twitch
        self.manager = websocket_manager
        self.client_id = settings.TWITCH_APP_ID
        self.client_secret = settings.TWITCH_APP_SECRET
        self.base_url = "https://api.twitch.tv/helix"

    async def notify(self, message: Dict[str, Any]):
        try:
            await self.manager.send_notification(message)
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            raise

    async def get_app_access_token(self):
        async with aiohttp.ClientSession() as session:
            async with session.post("https://id.twitch.tv/oauth2/token", data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials"
            }) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["access_token"]
                else:
                    logger.error(f"Failed to get app access token. Status: {response.status}")
                    return None

    async def get_streamer_info(self, streamer_id):
        token = await self.get_app_access_token()
        if not token:
            return None

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/users?id={streamer_id}", headers={
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {token}"
            }) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["data"][0] if data["data"] else None
                else:
                    logger.error(f"Failed to get streamer info. Status: {response.status}")
                    return None

    async def get_streamers(self) -> List[StreamerResponse]:
        streamers = self.db.query(Streamer).all()
        streamer_statuses = []

        for streamer in streamers:
            latest_stream = self.db.query(Stream)\
                .filter(Stream.streamer_id == streamer.id)\
                .order_by(Stream.id.desc())\
                .first()
            
            last_updated = None
            if latest_stream:
                last_event = self.db.query(StreamEvent)\
                    .filter(StreamEvent.stream_id == latest_stream.id)\
                    .order_by(StreamEvent.timestamp.desc())\
                    .first()
                if last_event:
                    last_updated = last_event.timestamp

            streamer_statuses.append(StreamerResponse(
                id=streamer.id,
                twitch_id=streamer.twitch_id,
                username=streamer.username,
                display_name=streamer.display_name,
                is_live=bool(latest_stream and latest_stream.ended_at is None),
                title=latest_stream.title if latest_stream else None,
                category_name=latest_stream.category_name if latest_stream else None,
                language=latest_stream.language if latest_stream else None,
                last_updated=last_updated
            ))

        return streamer_statuses

    async def get_streamer_by_username(self, username: str) -> Optional[Streamer]:
        return self.db.query(Streamer).filter(Streamer.username.ilike(username)).first()

    async def add_streamer(self, username: str) -> Dict[str, Any]:
        try:
            username = username.strip().lower()
            
            # Quick user lookup
            user_info_list = []
            async for user_info in self.twitch.get_users(logins=[username]):
                user_info_list.append(user_info)
                break  # Only need first result
                
            if not user_info_list:
                return {"success": False, "message": f"No Twitch user found for username: {username}"}

            user_data = user_info_list[0]
            
            # Check for existing
            existing_streamer = self.db.query(Streamer).filter(
                Streamer.twitch_id == user_data.id
            ).first()
            
            if existing_streamer:
                return {"success": False, "message": f"Streamer {user_data.display_name} already exists"}

            # Create new streamer
            new_streamer = Streamer(
                twitch_id=user_data.id,
                username=user_data.login,
                display_name=user_data.display_name
            )
        
            self.db.add(new_streamer)
            self.db.flush()
            
            return {
                "success": True,
                "streamer": new_streamer,
                "twitch_id": user_data.id
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error adding streamer: {str(e)}", exc_info=True)
            return {"success": False, "message": f"Error adding streamer: {str(e)}"}

    async def delete_streamer(self, streamer_id: int) -> Dict[str, Any]:
        try:
            streamer = self.db.query(Streamer).filter(Streamer.id == streamer_id).first()
            if streamer:
                streamer_data = {
                    "twitch_id": streamer.twitch_id,
                    "username": streamer.username
                }
            
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