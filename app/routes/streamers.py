from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.streamer_service import StreamerService
from app.config.settings import settings
from typing import List

router = APIRouter()

@router.get("/api/streamers")
async def get_streamers(
    db: Session = Depends(get_db),
    streamer_service: StreamerService = Depends()
):
    return await streamer_service.get_streamers()

@router.post("/api/streamers")
async def add_streamer(
    username: str,
    background_tasks: BackgroundTasks,
    streamer_service: StreamerService = Depends()
):
    result = await streamer_service.add_streamer(username)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return {"message": f"Successfully added {username}", "streamer": result["streamer"]}

@router.delete("/api/streamers/{streamer_id}")
async def delete_streamer(
    streamer_id: int,
    streamer_service: StreamerService = Depends()
):
    if await streamer_service.delete_streamer(streamer_id):
        return {"message": "Streamer deleted successfully"}
    raise HTTPException(status_code=404, detail="Streamer not found")
