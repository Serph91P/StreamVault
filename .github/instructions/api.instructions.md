---
applyTo: "app/routes/**/*.py,app/api/**/*.py"
---

# API Development Guidelines

## Endpoint Design

- Use RESTful conventions for resource endpoints
- Return proper HTTP status codes (200, 201, 404, 422, 500)
- Use Pydantic models for request/response validation
- Add OpenAPI documentation with descriptions and examples

## Error Handling

```python
from fastapi import HTTPException

# ✅ CORRECT: Proper error responses
@router.get("/streams/{stream_id}")
async def get_stream(stream_id: int, db: Session = Depends(get_db)):
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    return stream

# ❌ WRONG: Generic errors
@router.get("/streams/{stream_id}")
async def get_stream(stream_id: int, db: Session = Depends(get_db)):
    return db.query(Stream).filter(Stream.id == stream_id).first()
```

## Database Sessions

Use dependency injection for database sessions:
```python
from app.dependencies import get_db

@router.post("/streamers")
async def create_streamer(
    data: StreamerCreate,
    db: Session = Depends(get_db)
):
    # db session automatically closed after request
    streamer = Streamer(**data.dict())
    db.add(streamer)
    db.commit()
    db.refresh(streamer)
    return streamer
```

## Query Optimization

Always use eager loading for relationships:
```python
# ✅ CORRECT
streamers = db.query(Streamer).options(
    joinedload(Streamer.latest_stream),
    joinedload(Streamer.recording_settings)
).all()

# ❌ WRONG: Causes N+1
streamers = db.query(Streamer).all()
```

## Response Models

Define explicit response models:
```python
from app.schemas import StreamResponse

@router.get("/streams/{stream_id}", response_model=StreamResponse)
async def get_stream(stream_id: int, db: Session = Depends(get_db)):
    # Response automatically validated and serialized
    return stream
```

## WebSocket Endpoints

Use WebSocket for real-time updates:
```python
@router.websocket("/ws/status")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Handle message
            await websocket.send_json(response)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
```
