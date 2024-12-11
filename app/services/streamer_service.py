from sqlalchemy.orm import Session
from twitchAPI.twitch import Twitch
from app.models import Streamer, Stream
from app.config.settings import settings
from typing import List, Dict, Any

class StreamerService:
    def __init__(self, db: Session, twitch: Twitch):
        self.db = db
        self.twitch = twitch

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

    async def add_streamer(self, username: str) -> Dict[str, Any]:
        user_info = await self.twitch.get_users(logins=[username])
        if not user_info['data']:
            return {"success": False, "message": f"Streamer {username} does not exist."}

        user_data = user_info['data'][0]
        new_streamer = Streamer(id=user_data['id'], username=user_data['display_name'])
        self.db.add(new_streamer)
        self.db.commit()
        
        return {"success": True, "streamer": new_streamer}

    async def delete_streamer(self, streamer_id: int) -> bool:
        streamer = self.db.query(Streamer).filter(Streamer.id == streamer_id).first()
        if streamer:
            self.db.delete(streamer)
            self.db.commit()
            return True
        return False
