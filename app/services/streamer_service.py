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
            username = username.strip().lower()
        
            await self.notify({
                "type": "status",
                "message": f"Looking up streamer {username}..."
            })

            users = await self.twitch.get_users(logins=[username])
            if not users.data:
                msg = f"No Twitch user found for username: {username}"
                logger.error(msg)
                await self.notify({
                    "type": "error",
                    "message": msg
                })
                return {"success": False, "message": msg}

            user = users.data[0]
            logger.info(f"Found Twitch user: {user.display_name}")

            existing_streamer = await self.get_streamer_by_username(user.display_name)
            if existing_streamer:
                msg = f"Streamer {user.display_name} already exists"
                await self.notify({
                    "type": "error",
                    "message": msg
                })
                return {"success": False, "message": msg}

            new_streamer = Streamer(
                twitch_id=user.id,
                username=user.login,
                display_name=user.display_name
            )
        
            self.db.add(new_streamer)
            self.db.commit()
        
            logger.info(f"Successfully added streamer: {new_streamer.username}")
            await self.notify({
                "type": "success",
                "message": f"Successfully added {new_streamer.username}"
            })

            return {
                "success": True,
                "streamer": new_streamer
            }

        except Exception as e:
            self.db.rollback()
            error_msg = f"Error adding streamer: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await self.notify({
                "type": "error",
                "message": error_msg
            })
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