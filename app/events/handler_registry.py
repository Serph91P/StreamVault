from typing import Dict, Callable, Awaitable, Any
from app.database import SessionLocal
from app.services.websocket_manager import ConnectionManager

class EventHandlerRegistry:
    def __init__(self, connection_manager: ConnectionManager):
        self.handlers: Dict[str, Callable[[Any], Awaitable[None]]] = {}
        self.manager = connection_manager

    async def handle_stream_online(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(models.Streamer).filter(models.Streamer.id == streamer_id).first()
            if streamer:
                new_stream = models.Stream(streamer_id=streamer_id, event_type='stream.online')
                db.add(new_stream)
                db.commit()
                await self.manager.send_notification(f"{streamer.username} is now **online**!")

    async def handle_stream_offline(self, data: Any) -> None:
        streamer_id = data.event.broadcaster_user_id
        with SessionLocal() as db:
            streamer = db.query(models.Streamer).filter(models.Streamer.id == streamer_id).first()
            if streamer:
                new_stream = models.Stream(streamer_id=streamer_id, event_type='stream.offline')
                db.add(new_stream)
                db.commit()
                await self.manager.send_notification(f"{streamer.username} is now **offline**!")

    def register_handlers(self):
        self.handlers['stream.online'] = self.handle_stream_online
        self.handlers['stream.offline'] = self.handle_stream_offline
