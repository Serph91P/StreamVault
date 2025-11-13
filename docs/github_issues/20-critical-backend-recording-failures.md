# Issue #20: CRITICAL - Backend Recording System Completely Broken

**Priority:** 🔴 CRITICAL - BLOCKS PRODUCTION  
**Estimated Time:** 4-6 hours  
**Sprint:** Sprint 1 - EMERGENCY HOTFIX  
**Status:** 🔴 PRODUCTION DOWN  
**Agent:** backend-expert + bug-fixer

---

## ⚠️ EXECUTIVE SUMMARY

**PRODUCTION IS DOWN**: The entire recording system is non-functional. Multiple critical backend failures prevent ANY recordings from working.

**Business Impact:**
- 🚨 **0% recordings working** - Cannot record ANY streams
- 🚨 **All videos failing to stream** - Thumbnails return 500 errors
- 🚨 **Data loss ongoing** - Missing streams since November 12, 2025
- 🚨 **Application unusable** - Core functionality completely broken

**Root Cause:** Recent changes (TypeScript fix, SCSS warnings fix) **broke critical backend endpoints**.

**Priority:** **FIX BACKEND FIRST** - Frontend appearance is irrelevant if core functionality doesn't work.

---

## 🔴 Critical Bug #1: Video Thumbnail Endpoint Crashes (500 Errors)

### Problem Description

**ALL video thumbnails return 500 Internal Server Error:**

```
GET /api/videos/42/thumbnail [HTTP/2 500  70ms]
GET /api/videos/40/thumbnail [HTTP/2 500  69ms]
GET /api/videos/39/thumbnail [HTTP/2 500  68ms]
GET /api/videos/38/thumbnail [HTTP/2 500  44ms]
GET /api/videos/37/thumbnail [HTTP/2 500  43ms]
GET /api/videos/36/thumbnail [HTTP/2 500  ...]
```

**Impact:**
- ✅ Videos page loads
- ❌ **No thumbnails visible** (all broken image icons)
- ❌ **VideoCard component broken** (missing preview)
- ❌ **User cannot identify videos** (no visual preview)

### Root Cause Analysis

**Recent Changes Broke Endpoint:**

**What Changed (November 13, 2025):**
1. ✅ Fixed TypeScript error in `VideoPlayer.vue` (Line 193: `as HTMLElement` cast)
2. ✅ Fixed SCSS mixed-decls warnings (wrapped declarations in `& {}`)
3. ❌ **Something broke thumbnail endpoint** - Likely import/dependency issue

**Suspected Causes:**
1. **Import Error** - Missing import in `app/routes/videos.py`
2. **Path Validation Error** - `validate_path_security()` failing
3. **Database Query Error** - Stream lookup failing
4. **File Not Found Handling** - Exception not caught properly

### Files to Check

**Primary Suspect:**
- `app/routes/videos.py` (Lines ~441-515)
  - Function: `get_video_thumbnail(stream_id: int, ...)`
  - Check imports, path validation, error handling

**Related Files:**
- `app/utils/file_utils.py` - `validate_path_security()`
- `app/models.py` - `Stream` model relationships
- `app/services/metadata_service.py` - Thumbnail generation

### Expected Behavior

**Should return:**
- **200 OK** with JPEG image data (thumbnail exists)
- **404 Not Found** with JSON error (thumbnail missing) - **NOT 500!**

**Current behavior:**
- **500 Internal Server Error** with JSON error (endpoint crashes)

### Fix Strategy

1. **Check Backend Logs** - Get exact error traceback
   ```bash
   docker logs streamvault-develop --tail 100 | grep "ERROR"
   docker logs streamvault-develop --tail 100 | grep "thumbnail"
   ```

2. **Verify Imports** - Check `app/routes/videos.py` imports
   ```python
   from app.utils.file_utils import validate_path_security  # Required!
   from pathlib import Path
   from fastapi import HTTPException
   from fastapi.responses import FileResponse
   ```

3. **Add Error Handling** - Wrap in try/except, return 404 instead of 500
   ```python
   try:
       validated_path = validate_path_security(stream.recording_path, "read")
       # ... thumbnail logic
   except HTTPException:
       raise  # Re-raise 404 errors
   except Exception as e:
       logger.error(f"Thumbnail error for stream {stream_id}: {e}")
       raise HTTPException(status_code=404, detail="Thumbnail not found")
   ```

4. **Test Locally** - Verify fix works
   ```bash
   curl http://localhost:8000/api/videos/42/thumbnail
   # Expected: 200 OK (image) OR 404 Not Found (JSON) - NOT 500!
   ```

---

## 🔴 Critical Bug #2: Recording System Failures (Suspected)

### Problem Description

**If thumbnails are broken, recording system likely affected:**

**Suspected Issues:**
- Recording start/stop endpoints may be broken
- File path validation failing across all endpoints
- Import errors affecting multiple services
- Database queries failing

### Verification Required

**Test Recording System:**
1. Start a test recording manually
2. Check backend logs for errors
3. Verify recording file created
4. Stop recording and check cleanup
5. Verify video accessible after recording

**Test Endpoints:**
```bash
# Test recording start
curl -X POST http://localhost:8000/api/recording/start/{streamer_id}

# Test recording stop  
curl -X POST http://localhost:8000/api/recording/stop/{streamer_id}

# Test video streaming
curl http://localhost:8000/api/videos/42/stream
```

### Expected Results

**All should return:**
- **200 OK** with proper response
- **404 Not Found** if resource missing
- **Never 500** unless legitimate server crash

---

## 🔴 Critical Bug #3: Import Errors from Recent Changes

### Problem Description

**Recent frontend fixes may have broken backend imports:**

**What We Changed:**
- Added `as HTMLElement` type cast (frontend only - shouldn't affect backend)
- Wrapped SCSS in `& {}` blocks (frontend only - shouldn't affect backend)

**But:**
- Build process may have corrupted backend files
- Docker image rebuild may have failed partially
- Import paths may have changed unexpectedly

### Verification Required

**Check Python Imports:**
```bash
# Inside Docker container
docker exec -it streamvault-develop bash
python -c "from app.routes.videos import get_video_thumbnail; print('OK')"
python -c "from app.utils.file_utils import validate_path_security; print('OK')"
python -c "from app.models import Stream; print('OK')"
```

**Check Application Startup:**
```bash
docker logs streamvault-develop --tail 200 | grep "ERROR"
docker logs streamvault-develop --tail 200 | grep "ImportError"
docker logs streamvault-develop --tail 200 | grep "NameError"
```

---

## 📋 Action Plan for Tomorrow (Priority Order)

### Phase 1: Diagnose (30 minutes)

**Step 1: Get Error Logs**
```bash
# Production logs
docker logs streamvault-develop --tail 200 > /tmp/backend_errors.log

# Search for critical errors
grep "ERROR" /tmp/backend_errors.log
grep "500" /tmp/backend_errors.log
grep "thumbnail" /tmp/backend_errors.log
```

**Step 2: Test Endpoints Manually**
```bash
# Test thumbnail endpoint
curl -v http://localhost:8000/api/videos/42/thumbnail

# Test streaming endpoint
curl -v http://localhost:8000/api/videos/42/stream

# Test recording start
curl -X POST http://localhost:8000/api/recording/start/1
```

**Step 3: Check Imports**
```bash
docker exec -it streamvault-develop python -c "
from app.routes.videos import get_video_thumbnail
from app.utils.file_utils import validate_path_security
print('Imports OK')
"
```

---

### Phase 2: Fix Thumbnail Endpoint (1-2 hours)

**Goal:** Return 404 instead of 500 for missing thumbnails

**Files to Fix:**
- `app/routes/videos.py` (Line ~441)

**Implementation:**
1. Add comprehensive error handling
2. Return 404 for missing files
3. Add logging for debugging
4. Test with real stream IDs

**Validation:**
- ✅ Existing thumbnails return 200 OK
- ✅ Missing thumbnails return 404 (not 500!)
- ✅ Frontend shows placeholder for 404
- ✅ No 500 errors in logs

---

### Phase 3: Fix Recording System (2-3 hours)

**Goal:** Ensure recordings work end-to-end

**Test Scenarios:**
1. **Manual Recording Start**
   - Start recording via API
   - Verify file created
   - Check logs for errors

2. **Automatic Recording (EventSub)**
   - Trigger stream start webhook
   - Verify recording starts automatically
   - Check background tasks

3. **Recording Stop**
   - Stop recording via API
   - Verify file finalized
   - Check post-processing tasks

4. **Video Playback**
   - Stream video via `/api/videos/{id}/stream`
   - Verify no 500 errors
   - Check range request support

**Files to Check:**
- `app/services/recording/recording_service.py`
- `app/services/recording/process_manager.py`
- `app/routes/videos.py` (streaming endpoint)
- `app/utils/streamlink_utils.py`

**Validation:**
- ✅ Recording starts successfully
- ✅ Video file created on disk
- ✅ Recording stops cleanly
- ✅ Post-processing completes
- ✅ Video streams without errors
- ✅ Thumbnails generated correctly

---

### Phase 4: Smoke Test All Core Features (30 minutes)

**Test Checklist:**
- [ ] Add new streamer
- [ ] Start manual recording
- [ ] Stop recording
- [ ] View video list
- [ ] Stream video
- [ ] View streamer detail page
- [ ] Check stream history
- [ ] Verify thumbnails load
- [ ] Check background queue
- [ ] Test cleanup policies

---

## 🛠️ Debugging Commands

### Get Backend Logs
```bash
# Last 200 lines
docker logs streamvault-develop --tail 200

# Follow live logs
docker logs streamvault-develop -f

# Search for errors
docker logs streamvault-develop --tail 500 | grep "ERROR"
docker logs streamvault-develop --tail 500 | grep "500"
docker logs streamvault-develop --tail 500 | grep "thumbnail"
```

### Test API Endpoints
```bash
# Health check
curl http://localhost:8000/health

# Thumbnail endpoint (BROKEN)
curl -v http://localhost:8000/api/videos/42/thumbnail

# Video streaming (BROKEN?)
curl -v http://localhost:8000/api/videos/42/stream

# Recording start
curl -X POST http://localhost:8000/api/recording/start/1 \
  -H "Cookie: session=YOUR_SESSION_TOKEN"
```

### Check Python Imports
```bash
# Inside container
docker exec -it streamvault-develop bash

# Test imports
python -c "from app.routes.videos import router; print('OK')"
python -c "from app.utils.file_utils import validate_path_security; print('OK')"
python -c "from app.models import Stream; print('OK')"
```

### Restart Services
```bash
# Restart backend only
docker compose restart streamvault-develop

# Rebuild if needed
docker compose down
docker compose up -d --build
```

---

## 📊 Success Criteria

**Backend is considered FIXED when:**
- ✅ Thumbnail endpoint returns 200 or 404 (never 500)
- ✅ Video streaming works without errors
- ✅ Recording can be started manually
- ✅ Recording can be stopped cleanly
- ✅ Post-processing completes successfully
- ✅ No 500 errors in production logs
- ✅ All core endpoints respond correctly

**Then and ONLY then:** Move to frontend rework.

---

## 🔗 Related Issues

- **Issue #17** - Video Streaming & UI Bugs (SUPERSEDED by this issue)
- **Issue #14** - Startup & Player Bugs (may be related to import errors)
- **Issue #16** - Float Import Missing (similar import issue pattern)

---

## 📝 Notes for Developer

**Key Points:**
1. **Frontend appearance doesn't matter** if backend is broken
2. **Fix backend first** - thumbnails, streaming, recording
3. **Test systematically** - one endpoint at a time
4. **Get logs early** - diagnose before fixing
5. **Validate thoroughly** - ensure no regressions

**Recent Changes That May Have Caused This:**
- TypeScript fix in VideoPlayer.vue (Line 193)
- SCSS mixed-decls fix (wrapped in `& {}`)
- Docker rebuild after frontend changes
- Possible import path corruption during build

**What NOT to Do:**
- ❌ Don't start frontend work until backend 100% working
- ❌ Don't guess - get actual error logs first
- ❌ Don't fix one thing and assume others work
- ❌ Don't skip validation steps

**Expected Timeline:**
- **Phase 1 (Diagnose):** 30 minutes
- **Phase 2 (Fix Thumbnails):** 1-2 hours
- **Phase 3 (Fix Recording):** 2-3 hours
- **Phase 4 (Smoke Test):** 30 minutes
- **Total:** 4-6 hours

---

**Last Updated:** November 13, 2025  
**Status:** 🔴 PRODUCTION DOWN - CRITICAL PRIORITY  
**Next Steps:** Start Phase 1 (Diagnose) tomorrow morning
