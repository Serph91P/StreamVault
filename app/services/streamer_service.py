from sqlalchemy.orm import Session
from twitchAPI.twitch import Twitch
from fastapi import BackgroundTasks
from app.models import Streamer, Stream
from app.services.websocket_manager import ConnectionManager
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger("streamvault")

class StreamerService:
    def __init__(self, db: Session, twitch: Twitch):
        self.db = db
        self.twitch = twitch
        self.manager = ConnectionManager()

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
            await self.notify({
                "type": "status",
                "message": f"Looking up streamer {username}..."
            })

            async for user_info in self.twitch.get_users(logins=[username]):
                logger.debug(f"Fetched user_info: {user_info}")

                if not user_info or not user_info.data:
                    await self.notify({
                        "type": "error",
                        "message": f"Streamer {username} does not exist."
                    })
                    return {"success": False, "message": f"Streamer {username} does not exist."}

                user_data = user_info.data[0]
                logger.debug(f"Processing user_data: {user_data}")

                user_id = user_data.id
                display_name = user_data.display_name

                await self.notify({
                    "type": "status",
                    "message": f"Setting up subscriptions for {display_name}..."
                })

                new_streamer = Streamer(id=user_id, username=display_name)
                self.db.add(new_streamer)
                self.db.commit()
                logger.info(f"Added new streamer: {display_name}")

                await self.notify({
                    "type": "success",
                    "message": f"Successfully added {display_name}"
                })

                return {
                    "success": True,
                    "streamer": new_streamer
                }

        except Exception as e:
            logger.error(f"Failed to add streamer {username}: {str(e)}", exc_info=True)
            await self.notify({
                "type": "error",
                "message": f"Failed to add {username}: {str(e)}"
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
