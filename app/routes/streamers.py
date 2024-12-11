from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from app.services.streamer_service import StreamerService
from app.events.handler_registry import EventHandlerRegistry
from app.dependencies import get_streamer_service, get_event_registry

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
    try:
        existing = await streamer_service.get_streamer_by_username(username)
        if existing:
            return JSONResponse(
                status_code=400,
                content={"message": f"Streamer {username} is already subscribed."}
            )
        
        result = await streamer_service.add_streamer(username)
        if result["success"]:
            await event_registry.subscribe_to_events(result["streamer"].id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{streamer_id}")
async def delete_streamer(
    streamer_id: int,
    streamer_service: StreamerService = Depends(get_streamer_service)
):
    if await streamer_service.delete_streamer(streamer_id):
        return {"message": "Streamer deleted successfully"}
    raise HTTPException(status_code=404, detail="Streamer not found")