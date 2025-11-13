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

### N+1 Query Prevention (CRITICAL)

**ALWAYS use eager loading when accessing relationships** to prevent N+1 query problems.

#### The N+1 Problem

```python
# ❌ WRONG: Lazy loading causes N+1 queries
streams = db.query(Stream).all()  # Query 1: Fetch streams
for stream in streams:
    print(stream.streamer.username)  # Query 2-31: Fetch each streamer
# Total: 1 + 30 = 31 queries (should be 1!)
```

#### Solution: Eager Loading with joinedload()

```python
# ✅ CORRECT: Single query with JOIN
from sqlalchemy.orm import joinedload

streams = db.query(Stream).options(
    joinedload(Stream.streamer)  # Load relationship in same query
).all()

for stream in streams:
    print(stream.streamer.username)  # Already loaded, no query!
# Total: 1 query
```

#### Nested Relationships

```python
# ✅ CORRECT: Chain joinedload for multi-level relationships
recordings = db.query(Recording).options(
    joinedload(Recording.stream).joinedload(Stream.streamer)
).filter(Recording.status == "recording").all()

for rec in recordings:
    print(rec.stream.streamer.username)  # All loaded in 1 query
```

#### Multiple Relationships

```python
# ✅ CORRECT: Load multiple relationships at once
streams = db.query(Stream).options(
    joinedload(Stream.streamer),
    joinedload(Stream.recordings),
    joinedload(Stream.stream_events)
).all()
```

#### Bulk Query Pattern

```python
# ✅ CORRECT: Query once, use in-memory operations
active_recording_stream_ids = set(
    recording.stream_id for recording in 
    db.query(Recording.stream_id).filter(
        Recording.status == "recording"
    ).all()
)

# Check membership without additional queries
for streamer in streamers:
    is_recording = streamer.id in active_recording_stream_ids  # No query
```

#### When to Use Eager Loading

✅ **ALWAYS use when:**
- Accessing relationships in loops
- Displaying related data in API responses
- Counting or aggregating related records
- Loading data for serialization

❌ **DON'T use when:**
- Not accessing the relationship at all
- Relationship would be too expensive to load
- Only need a filtered subset (use WHERE instead)

**See:** `docs/N_PLUS_ONE_OPTIMIZATION.md` for complete guide

### Other Performance Guidelines

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

### Constants Management (MANDATORY)

**ALWAYS** use `app/config/constants.py` for magic numbers, timeouts, and thresholds.

#### Available Constant Groups:

```python
from app.config.constants import (
    ASYNC_DELAYS,        # Delays for async operations (seconds)
    RETRY_CONFIG,        # Retry attempts and strategies
    TIMEOUTS,            # Timeout values for various operations
    CACHE_CONFIG,        # Cache sizes and TTL values
    FILE_SIZE_THRESHOLDS,# File size thresholds in bytes
    METADATA_CONFIG      # Metadata extraction configuration
)

# Examples:
await asyncio.sleep(ASYNC_DELAYS.BRIEF_PAUSE)  # 1.0 seconds
max_retries = RETRY_CONFIG.DEFAULT_MAX_RETRIES  # 3 attempts
timeout = TIMEOUTS.GRACEFUL_SHUTDOWN  # 30 seconds
ttl = CACHE_CONFIG.NOTIFICATION_DEBOUNCE_TTL  # 300 seconds
```

#### When to Use Constants:

❌ **Bad - Magic Numbers:**
```python
await asyncio.sleep(5)  # What does 5 mean?
max_retries = 3  # Why 3?
if file_size > 2097152:  # What is 2097152?
cache = TTLCache(maxsize=1000, ttl=300)  # Arbitrary values
```

✅ **Good - Named Constants:**
```python
await asyncio.sleep(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)
max_retries = RETRY_CONFIG.DEFAULT_MAX_RETRIES
if file_size > FILE_SIZE_THRESHOLDS.TEST_FILE_SIZE:
cache = TTLCache(
    maxsize=CACHE_CONFIG.DEFAULT_CACHE_SIZE,
    ttl=CACHE_CONFIG.NOTIFICATION_DEBOUNCE_TTL
)
```

#### Adding New Constants:

When you find a magic number in code:
1. **Check** if a similar constant exists in `constants.py`
2. **Add** to appropriate dataclass if new
3. **Document** purpose with clear comment
4. **Update** this guide if adding new category

**Categories:**
- `ASYNC_DELAYS` - Sleep times, polling intervals
- `RETRY_CONFIG` - Retry counts and delays
- `TIMEOUTS` - Subprocess, API, process timeouts
- `CACHE_CONFIG` - Cache sizes and TTL values
- `FILE_SIZE_THRESHOLDS` - File size limits
- `METADATA_CONFIG` - Parsing depth limits

### Environment Variables

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

### Datetime Handling - PostgreSQL Timezone Awareness
**CRITICAL**: PostgreSQL stores `TIMESTAMP WITH TIME ZONE` - always use timezone-aware datetimes in Python.

```python
# ✅ CORRECT: Timezone-aware datetime
from datetime import datetime, timezone

# For new timestamps
now = datetime.now(timezone.utc)
stream.end_time = now

# For calculations
if recording.start_time:
    end_time = recording.end_time or datetime.now(timezone.utc)
    duration = int((end_time - recording.start_time).total_seconds())

# For edge cases where DB might have naive datetimes
if recording.start_time.tzinfo is None:
    # Assume UTC if timezone info is missing
    start_time_aware = recording.start_time.replace(tzinfo=timezone.utc)
else:
    start_time_aware = recording.start_time

# ❌ WRONG: Timezone-naive datetime
now = datetime.now()  # No timezone info
duration = (datetime.now() - recording.start_time).total_seconds()
# ↑ ERROR: "can't subtract offset-naive and offset-aware datetimes"

# ❌ WRONG: Mixing aware and naive
end_time = recording.end_time or datetime.now()  # end_time has tz, datetime.now() doesn't
```

**Database Schema:**
- All timestamp columns use `TIMESTAMP WITH TIME ZONE`
- PostgreSQL stores timestamps in UTC, converts on query
- Python SQLAlchemy returns timezone-aware datetime objects
- **ALWAYS** use `datetime.now(timezone.utc)` for consistency

**Common Gotchas:**
- `datetime.now()` returns **naive** datetime (no timezone)
- `datetime.now(timezone.utc)` returns **aware** datetime
- Cannot subtract naive from aware or vice versa
- Database queries return aware datetimes from PostgreSQL

### Database Cascade Deletes - Foreign Key Ordering
**CRITICAL**: When deleting records with foreign keys, delete children BEFORE parents.

```python
# ✅ CORRECT: Delete recordings before stream
from app.models import Recording

# Get all associated recordings
associated_recordings = db.query(Recording).filter(
    Recording.stream_id == stream.id
).all()

# Delete recordings first
for recording in associated_recordings:
    db.delete(recording)

# Then delete metadata
if metadata:
    db.delete(metadata)

# Finally delete the stream
db.delete(stream)
db.commit()

# ❌ WRONG: Delete stream first
db.delete(stream)  # IntegrityError: recordings still reference this stream_id
# ERROR: null value in column "stream_id" violates not-null constraint

# ❌ WRONG: Rely on CASCADE DELETE without explicit deletion
# Even though schema has ondelete="CASCADE", SQLAlchemy needs explicit deletion
db.delete(stream)  # May cause IntegrityError depending on session state
```

**Why Manual Deletion?**
- SQLAlchemy's ORM session state vs database CASCADE behavior
- `ondelete="CASCADE"` in schema works at database level
- But SQLAlchemy session may try to UPDATE children to NULL first
- Explicit deletion ensures predictable, session-aware cleanup

**Schema Reference:**
```python
# models.py
class Recording(Base):
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False)
```

**Best Practice:**
- Always delete in order: Recordings → Metadata → Stream
- Commit after all deletions to maintain transactional integrity
- Log each deletion for debugging

### Process Lifecycle Management - Critical for Long-Running Operations
**ALWAYS use fail-forward strategy for external process cleanup**

#### Pattern: Zombie Process Handling (uvloop)
When using uvloop (StreamVault's event loop), **always poll() before checking returncode**:

```python
# ✅ CORRECT: Poll first to update status
try:
    process.poll()  # Updates returncode, may throw ProcessLookupError
    if process.returncode is None:
        # Process is still alive
        process.terminate()
    else:
        # Process already terminated
        logger.info(f"Process already terminated (returncode: {process.returncode})")
except ProcessLookupError:
    # Expected for zombie processes (terminated but not reaped)
    logger.info("Process already terminated externally")

# ❌ WRONG: Direct returncode check
if process.returncode is None:  # May be stale!
    process.terminate()  # ProcessLookupError if zombie
```

#### Pattern: Fail-Forward with Finally Block
**Always continue with next step even if cleanup fails**:

```python
# ✅ CORRECT: Cleanup won't block next step
async def rotate_segment(stream: Stream, segment_info: Dict):
    try:
        process_id = f"stream_{stream.id}"
        
        # Try to stop old process
        if process_id in self.active_processes:
            current_process = self.active_processes[process_id]
            
            try:
                # Attempt graceful cleanup
                current_process.poll()
                if current_process.returncode is None:
                    current_process.terminate()
                    await asyncio.sleep(5)
                    current_process.poll()
                    if current_process.returncode is None:
                        current_process.kill()
                        
            except ProcessLookupError:
                # EXPECTED - process died externally (OOM, crash)
                logger.info("🔄 ROTATION: Process already terminated, continuing")
                
            except Exception as e:
                # Log but DON'T stop rotation
                logger.warning(f"🔄 ROTATION: Cleanup error: {e}, continuing anyway")
            
            finally:
                # CRITICAL: Always remove from tracking
                self.active_processes.pop(process_id, None)
        
        # ✅ This ALWAYS executes, even if cleanup failed
        segment_info['segment_count'] += 1
        new_process = await self._start_segment(stream, next_path, quality)
        
        if new_process:
            logger.info(f"✅ Successfully rotated to segment {segment_info['segment_count']}")
        else:
            logger.error(f"❌ Failed to start new segment")
    
    except Exception as e:
        logger.error(f"Critical error in rotation: {e}", exc_info=True)

# ❌ WRONG: Cleanup failure blocks next step
async def rotate_segment_wrong(stream: Stream):
    try:
        current_process.terminate()  # May throw ProcessLookupError
        await asyncio.sleep(5)
        current_process.kill()
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return  # ❌ New segment never started!
    
    # This code never reached if cleanup fails
    new_process = await self._start_segment(...)
```

#### Pattern: Expected vs Unexpected Exceptions
Use appropriate log levels for process lifecycle events:

```python
# ✅ CORRECT: INFO for expected conditions
try:
    process.poll()
except ProcessLookupError:
    logger.info("Process already terminated externally")  # Expected (OOM, crash)
except OSError as e:
    logger.error(f"Unexpected OS error: {e}")  # Unexpected system issue

# ✅ CORRECT: Semantic logging for operations
logger.info("🔄 ROTATION: Starting segment rotation")
logger.info("✅ Successfully rotated to segment 002")
logger.error("❌ Failed to start new segment")

# ❌ WRONG: ERROR for expected events
try:
    process.poll()
except ProcessLookupError:
    logger.error("Process lookup failed")  # This is normal!
```

#### Why External Processes Die
Long-running processes (24h+ streams) can terminate externally due to:
- **OOM Killer**: System runs out of memory → kills largest process
- **Container Restarts**: Docker/Kubernetes maintenance
- **Network Failures**: Proxy timeouts → streamlink crash
- **Application Bugs**: Streamlink internal crashes

**Always assume external processes can die at any time** and handle gracefully.

#### Critical Cleanup Requirements
When managing process dictionaries/tracking:

1. **Use `finally` blocks** to ensure cleanup happens
2. **Use `.pop(key, None)`** instead of `del` to avoid KeyError
3. **Remove from tracking BEFORE starting new process** to prevent race conditions
4. **Log all cleanup actions** with context for debugging

```python
# ✅ CORRECT: Safe dictionary cleanup
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
finally:
    # CRITICAL: Always executes, even with exception
    self.tracking_dict.pop(process_id, None)  # No KeyError if missing
    self.cleanup_resources()

# ❌ WRONG: Cleanup skipped on exception
try:
    risky_operation()
    self.tracking_dict.pop(process_id)  # Never reached if exception!
except Exception as e:
    logger.error(f"Failed: {e}")
```

**See Also**: `docs/segment_rotation_fixes.md` for complete production bug analysis

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
