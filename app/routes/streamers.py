from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.services.streamer_service import StreamerService
from app.dependencies import get_streamer_service, get_event_registry
from app.events.handler_registry import EventHandlerRegistry

router = APIRouter(prefix="/api/streamers", tags=["streamers"])

@router.get("")
async def get_streamers(
    streamer_service: StreamerService = Depends(get_streamer_service)
):
    return await streamer_service.get_streamers()

@router.post("/{username}")
async def add_streamer(
    username: str,
    background_tasks: BackgroundTasks,
    streamer_service: StreamerService = Depends(get_streamer_service),
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    result = await streamer_service.add_streamer(username)
    if result["success"]:
        await event_registry.subscribe_to_events(result["streamer"].id)
    return result

@router.delete("/{streamer_id}")
async def delete_streamer(
    streamer_id: int,
    streamer_service: StreamerService = Depends(get_streamer_service)
):
    if await streamer_service.delete_streamer(streamer_id):
        return {"message": "Streamer deleted successfully"}
    raise HTTPException(status_code=404, detail="Streamer not found")