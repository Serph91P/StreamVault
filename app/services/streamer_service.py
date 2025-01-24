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
            latest_stream = self.db.query(Stream)\
                .filter(Stream.streamer_id == streamer.id)\
                .order_by(Stream.started_at.desc())\
                .first()
            
            streamer_statuses.append({
                "id": streamer.id,
                "username": streamer.username,
                "is_live": latest_stream and latest_stream.ended_at is None,
                "last_updated": latest_stream.started_at if latest_stream else None
            })
    
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
            raise