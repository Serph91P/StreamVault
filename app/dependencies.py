from app.database import SessionLocal
from app.services.streamer_service import StreamerService
from app.events.handler_registry import EventHandlerRegistry

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_event_registry():
    return EventHandlerRegistry()

def get_streamer_service():
    return StreamerService()
