from sqlalchemy.orm import Session
from twitchAPI.twitch import Twitch
from app.models import Streamer, Stream
from app.services.websocket_manager import ConnectionManager
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger("streamvault")

class StreamerService:
    def __init__(self, db: Session, twitch: Twitch, websocket_manager: ConnectionManager):
        self.db = db
        self.twitch = twitch
        self.manager = websocket_manager

    async def notify(self, message: Dict[str, Any]):
        try:
            await self.manager.send_notification(message)
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            raise

    async def get_streamers(self) -> List[Dict[str, Any]]:
        streamers = self.db.query(Streamer).all()
        streamer_statuses = []
        
        for streamer in streamers:
            latest_event = self.db.query(Stream)\
                .filter(Stream.streamer_id == streamer.id)\
                .order_by(Stream.timestamp.desc())\
                .first()
                
            streamer_statuses.append({
                "id": streamer.id,
                "username": streamer.username,
                "is_live": latest_event.event_type == 'stream.online' if latest_event else False,
                "last_updated": latest_event.timestamp if latest_event else None
            })
        
        return streamer_statuses

    async def get_streamer_by_username(self, username: str) -> Optional[Streamer]:
        return self.db.query(Streamer).filter(Streamer.username.ilike(username)).first()

    async def add_streamer(self, username: str) -> Dict[str, Any]:
        try:
            logger.debug(f"Starting add_streamer process for username: {username}")
            
            # Check if streamer already exists
            existing_streamer = await self.get_streamer_by_username(username)
            if existing_streamer:
                logger.debug(f"Streamer {username} already exists")
                return {"success": False, "message": f"Streamer {username} already exists"}

            # Get user info from Twitch
            users = []
            async for user in self.twitch.get_users(logins=[username]):
                users.append(user)
                logger.debug(f"Found Twitch user: {user.display_name}")

            if not users:
                logger.debug(f"No Twitch user found for username: {username}")
                return {"success": False, "message": f"Streamer {username} not found on Twitch"}

            user = users[0]
            new_streamer = Streamer(
                id=user.id,
                username=user.display_name,
                display_name=user.display_name
            )
            
            self.db.add(new_streamer)
            self.db.commit()
            logger.info(f"Successfully added streamer: {user.display_name}")

            return {
                "success": True,
                "streamer": new_streamer
            }

        except Exception as e:
            logger.error(f"Error adding streamer: {e}", exc_info=True)
            return {"success": False, "message": str(e)}

    async def delete_streamer(self, streamer_id: int) -> bool:
        streamer = self.db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if streamer:
            self.db.delete(streamer)
            self.db.commit()
            await self.notify({
                "type": "success",
                "message": f"Removed streamer {streamer.username}"
            })
            logger.info(f"Deleted streamer: {streamer.username}")
            return True
        return False