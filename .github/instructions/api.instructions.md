---
applyTo: "app/routes/**/*.py,app/api/**/*.py"
---

# API Development Guidelines

## 🔐 Security Requirements (MANDATORY)

**CRITICAL**: All API endpoints MUST implement security controls. See `security.instructions.md` for complete guidelines.

### Input Validation - Required for ALL Endpoints
```python
from app.utils.security import validate_path_security, validate_filename

# ✅ CORRECT: Validate all inputs before processing
@router.post("/admin/cleanup")
async def cleanup_files(recordings_root: str = Query(...)):
    # SECURITY: Always validate file paths
    safe_path = validate_path_security(recordings_root, "read")
    return await cleanup_service.cleanup_files(safe_path)

@router.post("/upload")
async def upload_file(file: UploadFile):
    # SECURITY: Validate file uploads
    if file.size > 10 * 1024 * 1024 * 1024:  # 10GB
        raise HTTPException(400, "File too large")
    
    safe_filename = validate_filename(file.filename)
    # ... rest of upload logic
```

### Authentication & Authorization
```python
from app.middleware.auth import verify_admin_access
from app.dependencies import get_current_user

# ✅ CORRECT: Admin endpoint protection
@router.post("/admin/settings")
@verify_admin_access
async def update_settings(
    settings_data: dict,
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    # ... implementation

# ✅ CORRECT: User-specific data access
@router.get("/user/streams")
async def get_user_streams(current_user: User = Depends(get_current_user)):
    return db.query(Stream).filter(Stream.user_id == current_user.id).all()
```

### Error Handling - Prevent Information Disclosure
```python
# ✅ CORRECT: Safe error messages
@router.get("/streams/{stream_id}")
async def get_stream(stream_id: int):
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(404, "Stream not found")  # Safe message
    return stream

# ❌ WRONG: Information disclosure
@router.delete("/files/{file_path:path}")
async def delete_file(file_path: str):
    try:
        os.remove(file_path)  # Path traversal + info disclosure
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))  # Reveals filesystem structure
```

## Endpoint Design

- Use RESTful conventions for resource endpoints
- Return proper HTTP status codes (200, 201, 404, 422, 500)
- Use Pydantic models for request/response validation
- Add OpenAPI documentation with descriptions and examples
- **SECURITY**: Validate ALL inputs before processing
- **SECURITY**: Implement proper authentication/authorization

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
