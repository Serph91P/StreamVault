---
applyTo: "app/**/*.py,migrations/**/*.py"
---

# Backend Development Guidelines

## 🔐 Security Requirements (MANDATORY)

**CRITICAL**: Read and follow `security.instructions.md` for comprehensive security guidelines.

### Path Security - Apply to ALL File Operations
```python
# ✅ ALWAYS: Validate user-provided paths
from app.utils.security import validate_path_security

def process_file(user_path: str):
    safe_path = validate_path_security(user_path, "read")
    with open(safe_path, 'r') as f:
        return f.read()

# ❌ NEVER: Direct file operations with user input
def process_file_unsafe(user_path: str):
    with open(user_path, 'r') as f:  # Path traversal vulnerability
        return f.read()
```

### Database Security - Prevent SQL Injection
```python
# ✅ ALWAYS: Use SQLAlchemy ORM
streams = db.query(Stream).filter(Stream.name == user_input).all()

# ✅ ALWAYS: Parameterized queries for raw SQL
result = db.execute(text("SELECT * FROM streams WHERE name = :name"), {"name": user_input})

# ❌ NEVER: String formatting with user input
query = f"SELECT * FROM streams WHERE name = '{user_input}'"  # SQL injection risk
```

### Input Validation - Required for ALL User Input
```python
# ✅ ALWAYS: Validate before processing
def create_stream(streamer_name: str, title: str):
    if not streamer_name or len(streamer_name.strip()) == 0:
        raise ValueError("Streamer name required")
    
    clean_name = validate_streamer_name(streamer_name)
    safe_title = html.escape(title.strip()[:200])
    
    # Now safe to use
    return Stream(streamer_name=clean_name, title=safe_title)
```

## Code Style

- Use type hints for all function parameters and return types
- Follow PEP 8 style guide
- Add docstrings for public APIs using Google style
- Never use bare `except:` - use specific exception types
- **NO MAGIC NUMBERS**: Extract all constants to module-level or configuration
- **DOCUMENT LOGIC CHANGES**: Add comments explaining why query filters changed
- **DOCUMENT BREAKING CHANGES**: Add `BREAKING CHANGE:` comments for behavior changes
- **SECURITY**: Validate ALL user input before processing
- **SECURITY**: Use parameterized queries, never string formatting

## Database & Performance

- Use `joinedload()` for relationships to avoid N+1 queries
- All database queries should use eager loading
- Use dependency injection for database sessions
- Add indexes for frequently queried columns

## Services Architecture

- Services in `app/services/` should be stateless where possible
- Use structured logging with context
- Implement proper error handling with specific exceptions
- Use TTLCache for caches that could grow unboundedly
- **Check external service connectivity BEFORE starting long-running operations**
- **Fail fast with clear errors when external services are unavailable**

## Configuration

- Put magic numbers in `app/config/constants.py`
- Use environment variables for secrets
- Validate configuration at startup

## Background Tasks

- Background tasks use queue system in `app/services/queues/`
- Implement graceful shutdown for long-running tasks
- Use WebSocket for real-time UI updates

## Production Best Practices

### Missing Import Prevention
**ALWAYS verify imports are complete when using external libraries**

```python
# ✅ CORRECT: Import ALL required classes
from fastapi import WebSocket
from starlette.websockets import WebSocketState  # Required for state checking!

if websocket.client_state == WebSocketState.CONNECTED:
    await websocket.send_json(data)

# ❌ WRONG: Missing import causes runtime error
# from fastapi import WebSocket  # Missing WebSocketState import!
# if websocket.client_state == WebSocketState.CONNECTED:  # NameError!
```

**Check:** If you reference a class/constant, ensure it's imported at the top of the file.

### Duplicate Prevention Checks
**ALWAYS check for existing operations before starting duplicates**

```python
# ✅ CORRECT: Check for existing active recording
active_recordings = state_manager.get_active_recordings()
existing_recording = next(
    (rec_id for rec_id, rec_data in active_recordings.items() 
     if rec_data.get('streamer_id') == streamer_id),
    None
)
if existing_recording:
    logger.warning(f"DUPLICATE_BLOCK: Streamer {streamer_id} already has active recording {existing_recording}")
    return None

# Start new recording only if no duplicate exists
recording_id = await start_recording(streamer_id)

# ❌ WRONG: Start without checking for duplicates
recording_id = await start_recording(streamer_id)  # May create multiple recordings!
```

**Apply to:**
- Recording processes (one per streamer at a time)
- Background tasks (prevent duplicate jobs)
- WebSocket connections (prevent duplicate event handlers)
- File operations (prevent concurrent writes to same file)

**Note:** Consider if your duplicate check is compatible with segmented/chunked operations (e.g., 24h recording segments).

### Startup Cleanup - Zombie State Detection
**ALWAYS clean up stale state on application startup**

```python
# ✅ CORRECT: Startup cleanup function
async def cleanup_zombie_recordings():
    """Clean up stale recordings from database on startup
    
    Recordings are zombies if:
    - Status is 'recording' in database
    - But no actual process is running (after restart)
    """
    with SessionLocal() as db:
        zombie_recordings = db.query(Recording).filter(
            Recording.status == 'recording'
        ).all()
        
        for recording in zombie_recordings:
            # Update to realistic state
            recording.status = 'stopped'
            recording.end_time = recording.end_time or datetime.now()
            
            logger.info(f"🧹 Cleaned zombie recording {recording.id}")
        
        db.commit()
        logger.info(f"✅ Cleaned up {len(zombie_recordings)} zombie recordings")

# Call during startup BEFORE attempting recovery
async def startup_initialization():
    await cleanup_zombie_recordings()  # Clean first
    await recover_active_recordings()   # Then recover
```

**Apply to:**
- Recording status in database (status='recording' but no process)
- WebSocket connections (connections in DB but not in memory)
- Background tasks (tasks marked 'running' but not executing)
- Temporary files (orphaned temp files from previous session)
- Locks/semaphores (stale locks that prevent operations)

**Pattern:**
1. Query for entities in "active" state (recording, running, locked, etc.)
2. Verify actual state (check if process exists, file is locked, etc.)
3. Update to realistic state (stopped, failed, unlocked)
4. Log cleanup actions for debugging

### Static File Serving - PWA & Service Workers
**ALWAYS provide root-level endpoints for PWA critical files**

```python
# ✅ CORRECT: Serve PWA files at root level
@app.get("/registerSW.js")
async def register_service_worker():
    """Service worker registration must be at root level"""
    for path in ["app/frontend/dist/registerSW.js", "/app/app/frontend/dist/registerSW.js"]:
        try:
            return FileResponse(
                path,
                media_type="application/javascript",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",  # Never cache SW
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        except (FileNotFoundError, PermissionError):
            continue
    return Response(status_code=404)

@app.get("/sw.js")
async def service_worker():
    """Service worker must also be at root"""
    # Same pattern as above

# ❌ WRONG: Only mounting under /pwa/
app.mount("/pwa", StaticFiles(directory="dist"))
# Browser requests /registerSW.js → 404!
# Service worker scope rules require root-level files
```

**PWA File Requirements:**
- `/sw.js` - Service worker itself (MUST be at root)
- `/registerSW.js` - Registration script (MUST be at root)
- `/manifest.json` - Web app manifest (MUST be at root)
- Headers: Service workers MUST have `no-cache` headers
- Scope: Service worker scope is limited to its location and below

**Why Root Level?**
- Service workers can only control their own directory and subdirectories
- `/pwa/sw.js` can only control `/pwa/**`, not the whole app
- `/sw.js` can control the entire application

## Testing

- Write unit tests for business logic
- Integration tests for API endpoints
- Use fixtures for database setup
- Mock external APIs (Twitch, Streamlink)

## Common Patterns

### Database Queries
```python
# ✅ CORRECT: Eager loading
streams = db.query(Stream).options(
    joinedload(Stream.streamer),
    joinedload(Stream.category)
).filter(Stream.ended_at.isnot(None)).all()

# ❌ WRONG: Lazy loading causes N+1
streams = db.query(Stream).all()
for stream in streams:
    print(stream.streamer.name)  # N+1 query
```

### Exception Handling
```python
# ✅ CORRECT: Specific exceptions
try:
    process.terminate()
except ProcessLookupError:
    logger.debug("Process already terminated")

# ✅ CORRECT: Check external service connectivity first
from app.utils.streamlink_utils import check_proxy_connectivity

proxy_settings = get_proxy_settings_from_db()
if proxy_settings:
    is_reachable, error = check_proxy_connectivity(proxy_settings)
    if not is_reachable:
        logger.error(f"🔴 Proxy connection failed: {error}")
        raise ProxyConnectionError(f"Cannot start recording: {error}")

# ❌ WRONG: Start process without checking connectivity
process = subprocess.Popen([...])  # May fail silently if proxy is down!
except Exception as e:
    logger.error(f"Failed to terminate: {e}")

# ❌ WRONG: Bare except
try:
    process.terminate()
except:
    pass
```

### Logging
```python
# ✅ CORRECT: Structured logging
logger.info("Recording started", extra={
    "stream_id": stream.id,
    "streamer": stream.streamer.username
})

# ❌ WRONG: Unstructured
logger.info(f"Recording {stream.id} started")
```
