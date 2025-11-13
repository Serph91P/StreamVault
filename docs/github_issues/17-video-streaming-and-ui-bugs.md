# Video Streaming & UI Critical Bugs

## 🔴 Priority: CRITICAL
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 2-3 hours  
**Sprint:** Sprint 1: Critical Bugs & Features  
**Impact:** CRITICAL - Videos completely broken, can't stream, UI corrupted

---

## 📝 Problem Description

### Current State: Multiple Critical Failures on Videos Page

**Critical Issues Identified:**

#### 1. **Video Thumbnails Missing (All Videos)**
- ❌ No preview images shown on video cards
- ❌ Only video title appears (duplicated?)
- ❌ Card layout broken/collapsed

**Screenshot 1 Evidence:**
- Video cards show only text, no thumbnails
- Empty space where thumbnail should be
- Affects ALL videos in list

---

#### 2. **Streamer Detail Page - Missing Data**
- ❌ Total VODs: Shows "0" with no icon
- ❌ Avg Duration: Shows "0m" with no icon
- ❌ Total Size: Shows "0 MB" with **no icon** (always missing)
- ❌ Stream History: Empty, shows "No Recordings Yet" message
- ❌ Back button: **No icon** (missing globally?)

**Screenshot 2 Evidence:**
- Stats cards incomplete
- Stream History section empty despite existing videos
- Icons missing from UI elements

---

#### 3. **API Errors - 400 Bad Request**
**Console Errors:**
```
API request failed: Error: HTTP error! status: 400
    request https://streamvault-develop.meberthosting.de/assets/api-BSUUbNq2.js:1
```

**Root Cause:**
- API requests returning 400 errors
- Invalid request parameters?
- Missing query parameters?
- CORS issues?

---

#### 4. **Video Streaming Broken - 500 Server Errors**
**Cannot Play Any Videos:**
```
HTTP-Laden ist mit dem Status 500 fehlgeschlagen. 
Laden der Medienressource https://streamvault-develop.meberthosting.de/api/videos/42/stream fehlgeschlagen.

HTTP 500 errors:
- /api/videos/42/stream
- /api/videos/40/stream  
- /api/videos/39/stream
```

**Symptoms:**
- Video player shows error
- Stream endpoint returns 500 Internal Server Error
- Affects ALL videos (not just specific ones)

---

#### 5. **Connection Aborted Errors**
```
GET https://streamvault-develop.meberthosting.de/api/videos/42/stream
Status: (failed) net::ERR_CONNECTION_ABORTED
```

**Possible Causes:**
- Backend crash during stream request
- File not found on server
- Permission errors reading video files
- Database query failure

---

#### 6. **Video Selection UI Broken**
**Screenshot 4 Evidence:**
- ❌ Checkbox hit area wrong (must click beside checkbox)
- ❌ Checkbox design completely broken
- ❌ Selection state unclear
- ❌ Selected video border/highlight wrong

**User Impact:**
- Can't select videos properly
- Accidental selections
- Must click in weird spots to select
- Visual design corrupted

---

## 🔥 Critical Impact Assessment

**Severity: CRITICAL**
- ✋ **Videos page completely unusable**
- ✋ **Cannot stream ANY videos**
- ✋ **Streamer stats not loading**
- ✋ **Selection UI broken**

**User Flow Blocked:**
1. User opens Videos page → Thumbnails missing ❌
2. User clicks video → 500 error, can't play ❌
3. User clicks streamer → Stats empty, history empty ❌
4. User tries to select videos → Checkbox broken ❌

**Production Status:**
- 🚨 **PRODUCTION DOWN** - Core functionality broken
- 🚨 Videos unusable
- 🚨 Streamer pages empty
- 🚨 UI elements missing

---

## 🎯 Requirements

### 1. Video Thumbnails - Fix Missing Images

**Root Cause Analysis Needed:**
- [ ] Check API response - Does it return thumbnail URLs?
- [ ] Check image paths - Are they correct?
- [ ] Check file existence - Do thumbnail files exist on server?
- [ ] Check permissions - Can server read thumbnail files?

**Expected Behavior:**
- Video cards show thumbnail image
- Fallback to placeholder if thumbnail missing
- Lazy loading with skeleton state

**API Response Check:**
```json
{
  "videos": [
    {
      "id": 42,
      "title": "Stream Title",
      "thumbnail_url": "/api/videos/42/thumbnail",  // ← Check this
      "thumbnail_path": "/recordings/thumbs/42.jpg" // ← Or this
    }
  ]
}
```

---

### 2. Streamer Stats - Fix Missing Icons & Data

**Icons Missing:**
- Total VODs: Should show video icon (📹)
- Avg Duration: Should show clock icon (🕐)
- **Total Size: Icon ALWAYS missing** (📦 or 💾)
- Back button: Should show arrow icon (←)

**Data Issues:**
- Total VODs: Shows 0, but videos exist
- Stream History: Empty, but videos recorded
- Stats not calculated on page load

**Root Cause:**
- Icons not imported?
- CSS class wrong?
- API not returning data?
- Frontend not requesting correct endpoint?

---

### 3. API 400 Errors - Fix Bad Requests

**Investigation Needed:**
- [ ] Which endpoints return 400?
- [ ] What parameters are being sent?
- [ ] What does backend expect?
- [ ] Are query params URL-encoded correctly?

**Common 400 Causes:**
- Missing required parameters
- Invalid parameter format
- Wrong data type (string vs int)
- Missing authentication headers

**Backend Logs Check:**
```python
# Check backend logs for:
# - "Bad Request: Missing parameter 'X'"
# - "ValidationError: Invalid format for 'Y'"
# - "TypeError: Expected int, got str"
```

---

### 4. Video Streaming 500 Errors - Fix Server Crashes

**Critical: Stream Endpoint Broken**

**Investigation Priority:**
1. **Check backend logs** - Stack trace of 500 error
2. **Check file paths** - Do video files exist?
3. **Check permissions** - Can backend read video files?
4. **Check database** - Is recording_path column correct?

**Common 500 Causes:**
```python
# Possible errors in backend:
# 1. File not found
recording_path = stream.recording_path
if not os.path.exists(recording_path):
    # 500 error!

# 2. Permission denied
with open(recording_path, 'rb') as f:
    # PermissionError → 500

# 3. Database query failure
stream = session.query(Stream).filter_by(id=video_id).first()
# If stream.recording_path is NULL → 500

# 4. Missing recording_path column
# AttributeError: 'Stream' object has no attribute 'recording_path'
```

**Expected Behavior:**
- `/api/videos/{id}/stream` returns video file
- Correct MIME type (`video/mp4` or `video/x-matroska`)
- Range requests supported (for seeking)
- No 500 errors

---

### 5. Video Selection Checkbox - Fix Hit Area & Design

**Current Problems:**
- Checkbox clickable area wrong
- Must click outside checkbox to select
- Design broken (size, border, color?)
- Selected state unclear

**Expected Behavior:**
- Checkbox 24x24px minimum (desktop)
- Checkbox 32x32px on mobile
- Entire card clickable for selection
- Clear visual feedback on select
- Checkbox styled with global `.checkbox` class

**CSS Fix:**
```scss
.video-card {
  cursor: pointer;
  
  &.selected {
    border: 2px solid var(--primary-color);
    background: rgba(var(--primary-rgb), 0.05);
  }
  
  .checkbox {
    // Use global checkbox style from _utilities.scss
    width: 24px;
    height: 24px;
    cursor: pointer;
    
    @include m.respond-below('md') {
      width: 32px;
      height: 32px;
    }
  }
  
  // Make entire card clickable
  input[type="checkbox"] {
    position: absolute;
    opacity: 0;
    width: 100%;
    height: 100%;
    cursor: pointer;
  }
}
```

---

## 🔍 Debugging Steps

### Step 1: Check API Responses (Browser DevTools)

**Network Tab:**
1. Open `/videos` page
2. Filter by XHR/Fetch
3. Find `/api/videos` request
4. Check response:
   - Status code: 200? 400? 500?
   - Response body: Contains `thumbnail_url`?
   - Response body: Contains correct data?

**Example:**
```json
// Check if this exists in response:
{
  "videos": [
    {
      "id": 42,
      "title": "Stream Title",
      "thumbnail_url": "/api/videos/42/thumbnail",  // ← Present?
      "streamer_name": "CohhCarnage",
      "duration": 12345,
      "file_size": 2300000000  // bytes
    }
  ]
}
```

---

### Step 2: Check Backend Logs

**Docker Logs:**
```bash
# Check backend container logs
docker logs streamvault-backend -f

# Look for:
# - 500 errors with stack traces
# - "FileNotFoundError"
# - "PermissionError"
# - "AttributeError: 'Stream' object has no attribute 'recording_path'"
```

**Log File:**
```bash
# Or check log file
tail -f logs/streamvault.log

# Look for ERROR level messages:
# ERROR:app.routes.videos:Failed to stream video 42: FileNotFoundError
```

---

### Step 3: Database Verification

**Check `streams` table:**
```sql
-- Do streams have recording_path?
SELECT id, title, recording_path, file_size 
FROM streams 
WHERE id IN (39, 40, 42);

-- Check if recording_path is NULL
SELECT COUNT(*) FROM streams WHERE recording_path IS NULL;

-- Check if files exist on filesystem
SELECT id, title, recording_path 
FROM streams 
WHERE recording_path IS NOT NULL 
LIMIT 10;
```

**Expected:**
- `recording_path` column exists
- `recording_path` values not NULL
- Paths point to existing files

---

### Step 4: File System Check

**SSH into server:**
```bash
# Check if recordings directory exists
ls -la /recordings/

# Check specific video files
ls -la /recordings/CohhCarnage/

# Check file permissions
stat /recordings/CohhCarnage/video1.mp4

# Expected:
# -rw-r--r-- (readable by all)
# Owner: streamvault or www-data
```

---

### Step 5: Frontend Component Check

**Check `VideosView.vue`:**
```typescript
// Does component request thumbnails?
const fetchVideos = async () => {
  const response = await fetch('/api/videos')
  const data = await response.json()
  
  console.log('Videos data:', data)  // ← Check console
  videos.value = data.videos
}

// Does template render thumbnails?
<template>
  <img 
    :src="video.thumbnail_url"  // ← Check this exists
    alt="Thumbnail"
  />
</template>
```

---

## 📋 Implementation Tasks

### Task 1: Fix Video Streaming 500 Errors (HIGH PRIORITY - 1 hour)

**Backend Fix:**
```python
# app/routes/videos.py

@router.get("/videos/{video_id}/stream")
async def stream_video(video_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Stream video file with proper error handling
    """
    # Get stream from database
    stream = db.query(Stream).filter(Stream.id == video_id).first()
    
    if not stream:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check if recording_path exists
    if not stream.recording_path:
        logger.error(f"Stream {video_id} has no recording_path")
        raise HTTPException(status_code=404, detail="Video file path not set")
    
    # Verify file exists
    if not os.path.exists(stream.recording_path):
        logger.error(f"Video file not found: {stream.recording_path}")
        raise HTTPException(status_code=404, detail="Video file not found on server")
    
    # Check file permissions
    if not os.access(stream.recording_path, os.R_OK):
        logger.error(f"Cannot read video file: {stream.recording_path}")
        raise HTTPException(status_code=403, detail="Cannot read video file")
    
    # Stream the file
    try:
        return FileResponse(
            stream.recording_path,
            media_type="video/mp4",  # or detect from file extension
            headers={
                "Accept-Ranges": "bytes",  # Enable seeking
                "Content-Disposition": f'inline; filename="{stream.title}.mp4"'
            }
        )
    except Exception as e:
        logger.error(f"Failed to stream video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stream video: {str(e)}")
```

**Test:**
```bash
# Test streaming endpoint
curl -I https://streamvault-develop.meberthosting.de/api/videos/42/stream

# Expected:
# HTTP/1.1 200 OK
# Content-Type: video/mp4
# Accept-Ranges: bytes
```

---

### Task 2: Fix Missing Thumbnails (MEDIUM PRIORITY - 45 minutes)

**Backend: Ensure API Returns Thumbnails**
```python
# app/routes/videos.py

@router.get("/videos")
async def get_videos(db: Session = Depends(get_db)):
    """
    Get all videos with thumbnail URLs
    """
    streams = db.query(Stream).filter(Stream.ended_at.isnot(None)).all()
    
    videos = []
    for stream in streams:
        videos.append({
            "id": stream.id,
            "title": stream.title,
            "thumbnail_url": f"/api/videos/{stream.id}/thumbnail",  # ← Add this
            "streamer_name": stream.streamer.username if stream.streamer else "Unknown",
            "duration": stream.duration,
            "file_size": stream.file_size or 0,
            "created_at": stream.started_at.isoformat() if stream.started_at else None
        })
    
    return {"videos": videos}
```

**Frontend: Handle Missing Thumbnails**
```vue
<template>
  <div class="video-card">
    <div class="video-thumbnail">
      <img 
        v-if="video.thumbnail_url"
        :src="video.thumbnail_url" 
        :alt="video.title"
        @error="handleThumbnailError"
      />
      <div v-else class="thumbnail-placeholder">
        <i class="icon-video"></i>
      </div>
    </div>
    
    <div class="video-info">
      <h3>{{ video.title }}</h3>
      <p>{{ video.streamer_name }} · {{ formatDuration(video.duration) }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
const handleThumbnailError = (event: Event) => {
  // Fallback to placeholder if thumbnail fails to load
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
  // Show placeholder instead
}
</script>

<style scoped lang="scss">
.thumbnail-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background: var(--bg-tertiary);
  
  i {
    font-size: 48px;
    color: var(--text-secondary);
  }
}
</style>
```

---

### Task 3: Fix Missing Icons (MEDIUM PRIORITY - 30 minutes)

**Check Icon Import:**
```vue
<script setup lang="ts">
// Are icons imported?
import { 
  IconVideo,       // Total VODs
  IconClock,       // Avg Duration
  IconHardDrive,   // Total Size ← MISSING?
  IconArrowLeft    // Back button ← MISSING?
} from '@/components/icons'  // Or wherever icons are from
</script>

<template>
  <div class="stats-card">
    <IconHardDrive class="stats-icon" />  <!-- ← Add this -->
    <div class="stats-value">{{ formatFileSize(totalSize) }}</div>
    <div class="stats-label">Total Size</div>
  </div>
  
  <button class="btn-back" @click="goBack">
    <IconArrowLeft />  <!-- ← Add this -->
    Back
  </button>
</template>
```

**If Icons Missing - Use CSS Icons:**
```scss
.stats-icon {
  &.icon-hard-drive::before {
    content: '💾';  // Fallback emoji
  }
}

.btn-back::before {
  content: '←';
  margin-right: 8px;
}
```

---

### Task 4: Fix Streamer Stats - Load Data (MEDIUM PRIORITY - 45 minutes)

**Backend: Add Streamer Stats Endpoint**
```python
# app/routes/streamers.py

@router.get("/streamers/{streamer_id}/stats")
async def get_streamer_stats(streamer_id: int, db: Session = Depends(get_db)):
    """
    Get streamer statistics
    """
    streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
    
    if not streamer:
        raise HTTPException(status_code=404, detail="Streamer not found")
    
    # Count VODs
    total_vods = db.query(Stream).filter(
        Stream.streamer_id == streamer_id,
        Stream.ended_at.isnot(None)
    ).count()
    
    # Calculate avg duration
    avg_duration = db.query(func.avg(Stream.duration)).filter(
        Stream.streamer_id == streamer_id,
        Stream.duration.isnot(None)
    ).scalar() or 0
    
    # Calculate total size
    total_size = db.query(func.sum(Stream.file_size)).filter(
        Stream.streamer_id == streamer_id,
        Stream.file_size.isnot(None)
    ).scalar() or 0
    
    return {
        "total_vods": total_vods,
        "avg_duration": int(avg_duration),
        "total_size": int(total_size)
    }
```

**Frontend: Fetch Stats**
```typescript
// StreamerDetailView.vue

const stats = ref({
  total_vods: 0,
  avg_duration: 0,
  total_size: 0
})

const fetchStreamerStats = async () => {
  const response = await fetch(`/api/streamers/${streamerId}/stats`, {
    credentials: 'include'
  })
  
  if (response.ok) {
    stats.value = await response.json()
  }
}

onMounted(() => {
  fetchStreamerStats()
})
```

---

### Task 5: Fix Video Selection Checkbox (LOW PRIORITY - 30 minutes)

**Make Entire Card Clickable:**
```vue
<template>
  <div 
    class="video-card"
    :class="{ selected: isSelected }"
    @click="toggleSelect"
  >
    <div class="checkbox-container">
      <input 
        type="checkbox" 
        :checked="isSelected"
        @click.stop  // Prevent double-toggle
      />
      <span class="checkbox-custom"></span>
    </div>
    
    <!-- Rest of card content -->
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  video: Video
  selected: boolean
}>()

const emit = defineEmits<{
  select: [videoId: number]
}>()

const isSelected = computed(() => props.selected)

const toggleSelect = () => {
  emit('select', props.video.id)
}
</script>

<style scoped lang="scss">
.video-card {
  position: relative;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &.selected {
    border: 2px solid var(--primary-color);
    background: rgba(var(--primary-rgb), 0.05);
  }
  
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
}

.checkbox-container {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
  
  input[type="checkbox"] {
    position: absolute;
    opacity: 0;
    width: 32px;
    height: 32px;
    cursor: pointer;
  }
  
  .checkbox-custom {
    display: block;
    width: 32px;
    height: 32px;
    border: 2px solid var(--border-color);
    border-radius: 6px;
    background: var(--bg-primary);
    transition: all 0.2s ease;
    
    // Checkmark icon
    &::after {
      content: '✓';
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%) scale(0);
      color: white;
      font-size: 20px;
      font-weight: bold;
      transition: transform 0.2s ease;
    }
  }
  
  input:checked + .checkbox-custom {
    background: var(--primary-color);
    border-color: var(--primary-color);
    
    &::after {
      transform: translate(-50%, -50%) scale(1);
    }
  }
}
</style>
```

---

## ✅ Acceptance Criteria

### Video Streaming
- [ ] `/api/videos/{id}/stream` returns 200 OK (not 500)
- [ ] Video player loads and plays videos
- [ ] No connection aborted errors
- [ ] Seeking works (range requests)
- [ ] All videos playable (test 5+ videos)

### Thumbnails
- [ ] Video cards show thumbnail images
- [ ] Placeholder shown if thumbnail missing
- [ ] No broken image icons
- [ ] Lazy loading works

### Streamer Stats
- [ ] Total VODs shows correct count
- [ ] Avg Duration shows correct value
- [ ] Total Size shows correct value with icon 💾
- [ ] Stream History loads and displays videos
- [ ] Back button has icon ←

### Icons
- [ ] Total Size icon visible
- [ ] Back button icon visible
- [ ] All stats cards have icons
- [ ] Icons match design system

### Video Selection
- [ ] Entire card clickable for selection
- [ ] Checkbox hit area correct (32x32px minimum)
- [ ] Selected state clear (border + background)
- [ ] Checkbox design matches global style
- [ ] No accidental selections

### API Errors
- [ ] No 400 errors in console
- [ ] No 500 errors in console
- [ ] No connection aborted errors
- [ ] All API requests succeed

---

## 📖 References

**Related Issues:**
- Issue #1: Fix 6 UI Bugs (might be related to some UI issues)

**Backend Files:**
- `app/routes/videos.py` - Video streaming endpoint
- `app/routes/streamers.py` - Streamer stats endpoint
- `app/models.py` - Stream model (check recording_path column)

**Frontend Files:**
- `app/frontend/src/views/VideosView.vue` - Videos page
- `app/frontend/src/views/StreamerDetailView.vue` - Streamer detail page
- `app/frontend/src/components/VideoCard.vue` - Video card component

**Logs:**
- `logs/streamvault.log` - Backend error logs
- Browser DevTools Console - Frontend errors
- Browser DevTools Network - API request/response

---

## 🤖 Agent Recommendation

**Primary Agent:** `bug-fixer`  
**Backup Agent:** `feature-builder`

**Why bug-fixer:**
- Production down situation
- Multiple critical failures
- Requires systematic debugging
- Backend + Frontend fixes needed

**Copilot Command:**
```bash
@copilot with agent bug-fixer: Fix critical video streaming bugs (500 errors, missing thumbnails, broken UI)
```

---

## 🚨 Priority Order

1. **CRITICAL**: Fix 500 streaming errors (videos can't play)
2. **HIGH**: Fix missing thumbnails (videos not visible)
3. **HIGH**: Fix streamer stats loading (empty data)
4. **MEDIUM**: Fix missing icons (UI incomplete)
5. **LOW**: Fix checkbox selection UX (annoying but works)

Start with streaming fix - that's the blocker! 🔥
