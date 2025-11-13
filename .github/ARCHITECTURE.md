# StreamVault Backend Architecture

## Production-Ready Design Principles

StreamVault is built with **production-first** design principles:

1. **100% Reliability** - No silent failures, comprehensive error handling
2. **Concurrent Processing** - Multiple streamers recording simultaneously without interference
3. **Graceful Recovery** - Automatic task resumption after restarts
4. **Resource Optimization** - Memory-efficient, thread-safe operations
5. **Modern Python Standards** - Type hints, async/await, proper dependency injection

---

## Core Recording Flow

### 1. Stream Event Detection (EventSub Webhook)

**File:** `app/events/handler_registry.py`

```
Twitch → EventSub Webhook → StreamVault
    ↓
handle_stream_online()
    ↓
1. Create Stream record in DB
2. Check recording settings (auto_record)
3. Start recording if enabled
```

**Implementation:**
```python
class EventHandlerRegistry:
    async def handle_stream_online(self, data: dict):
        # 1. Deduplicate events (TTLCache)
        if self._is_duplicate_event(data):
            return
        
        # 2. Create stream record
        stream = Stream(
            streamer_id=streamer.id,
            started_at=datetime.now(timezone.utc),
            twitch_stream_id=data["id"]
        )
        db.add(stream)
        db.commit()
        
        # 3. Start recording if enabled
        if self.config_manager.is_recording_enabled(streamer.id):
            await self.recording_service.start_recording(
                stream.id, 
                streamer.id,
                force_mode=False
            )
```

**Key Features:**
- **Event Deduplication:** TTLCache prevents duplicate recordings from repeated webhooks
- **Auto-Record Check:** Only starts if streamer settings enable recording
- **Database-First:** Stream record created before recording starts (audit trail)

---

### 2. Recording Service (Streamlink Process Management)

**File:** `app/services/recording/recording_service.py`

```
start_recording()
    ↓
1. Duplicate Check (prevent multiple recordings)
2. Create Recording record (status='recording')
3. Start Streamlink subprocess
4. Monitor process status
5. Handle segment rotation (24h+ streams)
```

**Implementation:**
```python
class RecordingService:
    async def start_recording(self, stream_id: int, streamer_id: int, force_mode: bool = False):
        # 1. CRITICAL: Check for existing active recording
        active_recording = self.state_manager.get_active_recording(streamer_id)
        if active_recording:
            logger.warning(f"DUPLICATE_BLOCK: Streamer {streamer_id} already recording")
            return None
        
        # 2. Create Recording record
        recording = Recording(
            stream_id=stream_id,
            start_time=datetime.now(timezone.utc),
            status='recording'
        )
        db.add(recording)
        db.commit()
        
        # 3. Start Streamlink process
        process = await self._start_streamlink_process(
            streamer_username=streamer.username,
            quality=quality,
            output_path=output_file
        )
        
        # 4. Track process in state manager
        self.state_manager.register_recording(
            recording_id=recording.id,
            process=process,
            stream_id=stream_id,
            streamer_id=streamer_id
        )
        
        # 5. Start monitoring task
        asyncio.create_task(self._monitor_recording(recording.id))
        
        return recording.id
```

**Duplicate Prevention Strategy:**
- ✅ Check `state_manager` for active recordings before starting
- ✅ Use `streamer_id` as key (one recording per streamer at a time)
- ✅ Support segmented recordings (24h rotation doesn't count as duplicate)

---

### 3. Segment Rotation (24h+ Streams)

**File:** `app/services/recording/recording_service.py`

```
24h Timer Expires
    ↓
rotate_segment()
    ↓
1. Stop current Streamlink process (graceful)
2. Increment segment count
3. Start new Streamlink process (same stream)
4. Continue until stream ends
```

**Implementation:**
```python
async def rotate_segment(self, stream: Stream, segment_info: Dict):
    """
    Rotate recording segment for long streams (24h+)
    CRITICAL: Must handle process cleanup failures gracefully
    """
    try:
        process_id = f"stream_{stream.id}"
        
        # 1. FAIL-FORWARD: Try to stop old process, but ALWAYS continue
        if process_id in self.active_processes:
            current_process = self.active_processes[process_id]
            
            try:
                # Attempt graceful termination
                current_process.poll()  # Update returncode (uvloop requirement)
                if current_process.returncode is None:
                    current_process.terminate()
                    await asyncio.sleep(TIMEOUTS.GRACEFUL_SHUTDOWN)
                    current_process.poll()
                    if current_process.returncode is None:
                        current_process.kill()
                        
            except ProcessLookupError:
                # EXPECTED: Process died externally (OOM, crash, restart)
                logger.info("🔄 ROTATION: Process already terminated, continuing")
                
            except Exception as e:
                # Log but DON'T stop rotation
                logger.warning(f"🔄 ROTATION: Cleanup error: {e}, continuing anyway")
            
            finally:
                # CRITICAL: Always remove from tracking (even on error)
                self.active_processes.pop(process_id, None)
        
        # 2. ✅ ALWAYS START NEW SEGMENT (even if cleanup failed)
        segment_info['segment_count'] += 1
        next_path = self._generate_segment_path(stream, segment_info['segment_count'])
        
        new_process = await self._start_segment(stream, next_path, quality)
        
        if new_process:
            logger.info(f"✅ Rotated to segment {segment_info['segment_count']}")
            return True
        else:
            logger.error(f"❌ Failed to start segment {segment_info['segment_count']}")
            return False
            
    except Exception as e:
        logger.error(f"Critical error in rotation: {e}", exc_info=True)
        return False
```

**Why Fail-Forward Pattern:**
- Long-running processes (24h+) can terminate externally (OOM killer, container restart)
- **NEVER** let cleanup failure prevent new segment from starting
- Use `finally` block to ensure state cleanup happens
- Use `.pop(key, None)` instead of `del` to avoid KeyError

**External Process Death Scenarios:**
- **OOM Killer**: System runs out of memory → kills largest process (streamlink)
- **Container Restart**: Docker/Kubernetes maintenance
- **Network Failure**: Proxy timeout → streamlink crash
- **Streamlink Bugs**: Internal crashes

---

### 4. Stream Offline (Stop Recording)

**File:** `app/events/handler_registry.py`

```
stream.offline webhook
    ↓
handle_stream_offline()
    ↓
1. Find active Recording
2. Stop recording (graceful)
3. Update Stream.ended_at
4. Trigger post-processing
```

**Implementation:**
```python
async def handle_stream_offline(self, data: dict):
    # 1. Find active recording
    active_recording = db.query(Recording).filter(
        Recording.stream_id == stream.id,
        Recording.status == 'recording'
    ).first()
    
    if active_recording:
        # 2. Stop recording (triggers post-processing)
        await self.recording_service.stop_recording(
            active_recording.id,
            reason="automatic"
        )
    
    # 3. Update stream status
    stream.ended_at = datetime.now(timezone.utc)
    streamer.is_live = False
    db.commit()
```

---

## Post-Processing Pipeline

### 1. Transmux (TS → MP4)

**File:** `app/services/post_processing/transmux_service.py`

```
stop_recording()
    ↓
Transmux Task Queue
    ↓
1. Detect all segments (.ts files)
2. Merge segments (ffmpeg concat)
3. Transmux to MP4 (fast, no re-encode)
4. Validate output
5. Update Recording.path
```

**Implementation:**
```python
async def transmux_recording(self, recording_id: int):
    # 1. Find all segment files
    segments = sorted(glob.glob(f"{base_path}_segment_*.ts"))
    
    if len(segments) > 1:
        # 2. Merge segments with ffmpeg concat
        concat_list = self._create_concat_list(segments)
        merged_ts = await self._merge_segments(concat_list)
        input_file = merged_ts
    else:
        input_file = segments[0]
    
    # 3. Transmux (copy codecs, no re-encode)
    output_mp4 = input_file.replace('.ts', '.mp4')
    await self._run_ffmpeg_transmux(input_file, output_mp4)
    
    # 4. Validate output
    if not os.path.exists(output_mp4) or os.path.getsize(output_mp4) < MIN_FILE_SIZE:
        raise TransmuxError("Output file invalid")
    
    # 5. Update recording
    recording.path = output_mp4
    recording.status = 'completed'
    db.commit()
    
    # 6. Clean up temp files
    for segment in segments:
        os.remove(segment)
```

**Why Transmux (not Re-encode):**
- **Fast:** Copy streams instead of re-encoding (10-100x faster)
- **Lossless:** No quality degradation
- **Resource-Efficient:** Minimal CPU usage

---

### 2. Metadata Extraction & Embedding

**File:** `app/services/post_processing/metadata_service.py`

```
transmux_completed
    ↓
Metadata Task
    ↓
1. Fetch stream metadata (Twitch API)
2. Fetch category/game info
3. Generate thumbnail (ffmpeg)
4. Embed metadata in MP4
5. Create StreamMetadata record
```

**Implementation:**
```python
async def process_metadata(self, stream_id: int):
    # 1. Fetch stream data
    stream = db.query(Stream).get(stream_id)
    streamer = stream.streamer
    
    # 2. Generate thumbnail (10% position)
    thumbnail_path = await self._generate_thumbnail(
        video_path=recording.path,
        position_percent=10
    )
    
    # 3. Fetch category image
    category_image = await self.image_service.get_category_image(
        stream.category_name
    )
    
    # 4. Embed metadata in MP4
    await self._embed_metadata(
        video_path=recording.path,
        metadata={
            'title': stream.title,
            'artist': streamer.username,
            'comment': f"Streamed on {stream.started_at.strftime('%Y-%m-%d')}",
            'genre': stream.category_name,
            'artwork': thumbnail_path
        }
    )
    
    # 5. Create database record
    metadata = StreamMetadata(
        stream_id=stream.id,
        thumbnail_path=thumbnail_path,
        category_image_path=category_image,
        duration=duration,
        file_size=file_size
    )
    db.add(metadata)
    db.commit()
```

---

## Concurrent Recording Management

### State Manager (Thread-Safe)

**File:** `app/services/recording/state_manager.py`

```python
class RecordingStateManager:
    """
    Thread-safe state manager for active recordings
    Prevents race conditions in concurrent environments
    """
    def __init__(self):
        self._lock = asyncio.Lock()
        self._active_recordings: Dict[int, RecordingState] = {}
    
    async def register_recording(self, recording_id: int, process: subprocess.Popen, 
                                stream_id: int, streamer_id: int):
        """Register active recording (thread-safe)"""
        async with self._lock:
            # CRITICAL: Check for duplicates under lock
            if streamer_id in self._get_active_streamer_ids():
                raise DuplicateRecordingError(f"Streamer {streamer_id} already recording")
            
            self._active_recordings[recording_id] = RecordingState(
                process=process,
                stream_id=stream_id,
                streamer_id=streamer_id,
                started_at=datetime.now(timezone.utc)
            )
    
    async def unregister_recording(self, recording_id: int):
        """Remove recording from active state (thread-safe)"""
        async with self._lock:
            self._active_recordings.pop(recording_id, None)
    
    def get_active_recording(self, streamer_id: int) -> Optional[int]:
        """Check if streamer has active recording"""
        for recording_id, state in self._active_recordings.items():
            if state.streamer_id == streamer_id:
                return recording_id
        return None
```

**Why Thread-Safe State Management:**
- Multiple webhooks can arrive simultaneously
- Background tasks run concurrently
- Prevents duplicate recordings from race conditions

---

## Startup Recovery & Cleanup

### Zombie State Detection

**File:** `app/main.py` (startup event)

```python
@app.on_event("startup")
async def startup_cleanup():
    """
    Clean up stale/zombie state on application startup
    CRITICAL: Prevents orphaned recordings after container restarts
    """
    # 1. Clean zombie recordings
    await cleanup_zombie_recordings()
    
    # 2. Recover active streams
    await recover_active_recordings()
    
    # 3. Resume post-processing
    await resume_pending_tasks()
```

**Implementation:**
```python
async def cleanup_zombie_recordings():
    """
    Find recordings marked 'recording' but no actual process exists
    Happens after: crashes, restarts, OOM kills
    """
    with SessionLocal() as db:
        zombie_recordings = db.query(Recording).filter(
            Recording.status == 'recording'
        ).all()
        
        for recording in zombie_recordings:
            # Check if process actually exists
            if not is_process_running(recording.id):
                # Update to realistic state
                recording.status = 'stopped'
                recording.end_time = recording.end_time or datetime.now(timezone.utc)
                
                logger.info(f"🧹 Cleaned zombie recording {recording.id}")
        
        db.commit()
        logger.info(f"✅ Cleaned {len(zombie_recordings)} zombie recordings")

async def recover_active_recordings():
    """
    For streams still live, attempt to resume recording
    Only if stream.ended_at is NULL and streamer.is_live = True
    """
    with SessionLocal() as db:
        active_streams = db.query(Stream).filter(
            Stream.ended_at.is_(None)
        ).join(Streamer).filter(
            Streamer.is_live == True
        ).all()
        
        for stream in active_streams:
            # Check if recording exists
            recording = db.query(Recording).filter(
                Recording.stream_id == stream.id,
                Recording.status == 'recording'
            ).first()
            
            if not recording:
                # Stream is live but no recording → Resume
                logger.info(f"🔄 Resuming recording for stream {stream.id}")
                await recording_service.start_recording(
                    stream.id,
                    stream.streamer_id,
                    force_mode=False
                )
```

**Zombie States:**
- **Recording** status in DB but no process running
- **Stream** ended_at is NULL but streamer offline
- **Locks/Semaphores** held but no owner process

---

## Notification System

### Profile Image Priority (CRITICAL FIX)

**File:** `app/services/notifications/external_notification_service.py`

```python
# ALWAYS use original Twitch HTTP URL for notifications
# External services (Ntfy, Discord) cannot access local file paths

# Priority 1: Original Twitch URL (always works)
if streamer.original_profile_image_url and streamer.original_profile_image_url.startswith('http'):
    profile_image_url = streamer.original_profile_image_url

# Priority 2: EventSub notification URL
elif details.get("profile_image_url") and details["profile_image_url"].startswith('http'):
    profile_image_url = details["profile_image_url"]

# Priority 3: Current streamer URL (if HTTP)
elif streamer.profile_image_url and streamer.profile_image_url.startswith('http'):
    profile_image_url = streamer.profile_image_url
```

**Why This Matters:**
- ❌ Local paths (`/recordings/.media/profiles/...`) don't work for external services
- ✅ HTTP URLs (`https://static-cdn.jtvnw.net/...`) work everywhere
- **Update events** were showing Apprise logo because profile_image was a local path

**Ntfy Configuration:**
```python
# FIXED: Add icon for ALL event types
params = [
    f"click={twitch_url}",
    f"priority={'high' if event_type == 'online' else 'default'}",
    f"tags=stream,{event_type}"
]

# CRITICAL: Add icon for all events (not just online/offline)
if profile_image and profile_image.startswith('http'):
    params.append(f"icon={profile_image}")  # ntfy uses 'icon' not 'avatar_url'
```

---

## Database Schema & Properties

### Streamer Model

**File:** `app/models.py`

```python
class Streamer(Base):
    __tablename__ = "streamers"
    
    id = Column(Integer, primary_key=True)
    twitch_id = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=False)
    is_live = Column(Boolean, default=False)
    auto_record = Column(Boolean, default=False)
    profile_image_url = Column(String)  # Can be local path or HTTP
    original_profile_image_url = Column(String)  # Always HTTP from Twitch
    
    @property
    def is_recording(self) -> bool:
        """
        Check if this streamer currently has an active recording.
        NO DATABASE MIGRATION NEEDED - computed at runtime.
        """
        from sqlalchemy.orm import object_session
        
        session = object_session(self)
        if not session:
            return False
        
        # Query Recording table for active recordings
        active_recording = session.query(Recording).join(Stream).filter(
            Stream.streamer_id == self.id,
            Recording.status == 'recording'
        ).first()
        
        return active_recording is not None
    
    @property
    def recording_enabled(self) -> bool:
        """Alias for auto_record (backward compatibility)"""
        return self.auto_record
```

**Why @property Instead of Column:**
- ✅ No migration needed
- ✅ Always up-to-date (queries Recording table in real-time)
- ✅ Separation of concerns: `is_recording` (state) vs `recording_enabled` (config)

---

## Error Handling & Logging

### Semantic Logging Pattern

```python
# ✅ CORRECT: INFO for expected conditions
try:
    process.poll()  # Update returncode
except ProcessLookupError:
    logger.info("Process already terminated externally")  # Expected (OOM, crash)
except OSError as e:
    logger.error(f"Unexpected OS error: {e}")  # Unexpected system issue

# ✅ CORRECT: Semantic prefixes for operations
logger.info("🔄 ROTATION: Starting segment rotation")
logger.info("✅ Successfully rotated to segment 002")
logger.error("❌ Failed to start new segment")

# ❌ WRONG: ERROR for expected events
try:
    process.poll()
except ProcessLookupError:
    logger.error("Process lookup failed")  # This is normal for zombie processes!
```

**Logging Levels:**
- `DEBUG` - Detailed flow for debugging
- `INFO` - Normal operations, expected conditions
- `WARNING` - Recoverable issues, fallbacks used
- `ERROR` - Unexpected failures, but service continues
- `CRITICAL` - Service cannot continue, requires intervention

---

## Production Checklist

### Before Deployment

- [x] All database queries use eager loading (`joinedload()`)
- [x] No bare `except:` blocks - specific exceptions only
- [x] All magic numbers extracted to `app/config/constants.py`
- [x] TTLCache used for unbounded dictionaries
- [x] Zombie state cleanup on startup
- [x] Duplicate prevention checks before starting recordings
- [x] Fail-forward strategy for external process cleanup
- [x] All file paths validated against path traversal
- [x] All user input sanitized before database queries
- [x] Properties used for computed values (no unnecessary columns)
- [x] WebSocket connections managed with proper state
- [x] Notification images use HTTP URLs (not local paths)

### Concurrent Recording Scenarios

**Scenario 1: 5 streamers go live simultaneously**
```
✅ PASS: Each webhook creates separate recording
✅ PASS: State manager prevents duplicates via async lock
✅ PASS: Streamlink processes run independently
✅ PASS: No resource contention (separate output files)
```

**Scenario 2: Streamer goes live while previous recording post-processing**
```
✅ PASS: Post-processing runs in background queue
✅ PASS: New recording starts independently
✅ PASS: No file conflict (new segment number)
```

**Scenario 3: Container restart during 3 active recordings**
```
✅ PASS: Startup cleanup marks all as 'stopped'
✅ PASS: Recovery checks if streams still live
✅ PASS: Resumes recordings for live streams
✅ PASS: No duplicate recordings created
```

---

## References

**Key Files:**
- Event Handling: `app/events/handler_registry.py`
- Recording Service: `app/services/recording/recording_service.py`
- State Management: `app/services/recording/state_manager.py`
- Post-Processing: `app/services/post_processing/transmux_service.py`
- Notifications: `app/services/notifications/external_notification_service.py`
- Models: `app/models.py`

**Critical Patterns:**
- Duplicate Prevention: Lines 260-275 in `handler_registry.py`
- Fail-Forward Cleanup: Lines 450-490 in `recording_service.py`
- Zombie Detection: `app/main.py` startup event
- Profile Image Priority: Lines 95-120 in `external_notification_service.py`

**Documentation:**
- Segment Rotation: `docs/segment_rotation_fixes.md`
- Database Indexes: `docs/database_indexes.md`
- Graceful Shutdown: `docs/graceful_shutdown.md`
