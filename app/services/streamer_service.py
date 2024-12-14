from sqlalchemy.orm import Session
from twitchAPI.twitch import Twitch
from fastapi import BackgroundTasks
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
            
            # Log Twitch API call
            logger.debug("Calling Twitch API to get user info")
            user_info_list = []
            async for user_info in self.twitch.get_users(logins=[username]):
                logger.debug(f"Received Twitch API response: {user_info}")
                user_info_list.append(user_info)

            if not user_info_list:
                logger.debug(f"No user found for username: {username}")
                return {"success": False, "message": f"Streamer {username} does not exist."}

            user_data = user_info_list[0]
            logger.debug(f"Processing user data: {user_data}")

            # Create new streamer
            new_streamer = Streamer(
                id=user_data.id,
                username=user_data.display_name
            )
            self.db.add(new_streamer)
            self.db.commit()
            
            logger.info(f"Successfully added streamer: {new_streamer.username}")
            return {
                "success": True,
                "streamer": new_streamer
            }

        except Exception as e:
            logger.error(f"Error in add_streamer: {str(e)}", exc_info=True)
            raise

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
