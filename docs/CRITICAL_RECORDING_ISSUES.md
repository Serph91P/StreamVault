# Critical Recording Issues - November 15, 2025

## 🔴 FIXED: Max Concurrent Recordings Limit

**Problem:** Application had hardcoded 3-stream recording limit
- Prevented recording more than 3 streamers simultaneously
- Caused "CAPACITY_BLOCK: Cannot start recording: at maximum capacity (3/3)" errors
- Not documented anywhere in frontend/settings
- No user control over this limit

**Impact:** If 3 streamers were live and 2 more went live, only 3 would be recorded

**Fix (Commit: pending):**
- Removed `max_concurrent_recordings` from `RecordingStateManager.__init__`
- Removed `is_at_max_capacity()` and `can_start_new_recording()` methods
- Removed capacity check from `RecordingLifecycleManager.start_recording()`
- Removed from stats output (`get_recording_stats()`)
- Removed legacy reference in `RecordingService`

**Files Changed:**
- `app/services/recording/recording_state_manager.py`
- `app/services/recording/recording_lifecycle_manager.py`
- `app/services/recording/recording_service.py`

---

## 🔴 CRITICAL: H.265/1440p Streams Not Recording in Native Quality

**Problem:** Dhalucard streams in H.265/1440p but recordings are H.264/1080p

**Root Cause Found (Log Analysis):**
Streamlink log shows Twitch only offers limited qualities:
```
[2025-11-15 10:02:10][cli][info] Available streams: audio_only, 360p30 (worst), 480p30, 720p60, 1080p60 (best)
```

**Issue:** Despite `--twitch-supported-codecs h264,h265` being set, Twitch API does NOT return:
- 1440p quality option
- H.265/HEVC codec streams

**Why This Happens:**
1. Twitch may require Turbo/subscriber access for higher qualities
2. Geographic restrictions on H.265 streams
3. Streamlink user agent not recognized as supporting H.265
4. Twitch partners may have different stream availability

**Possible Solutions:**
1. Add Twitch OAuth authentication for authenticated requests
2. Try different Streamlink user agent strings
3. Check if Twitch even offers 1440p to third-party apps
4. Investigate if Dhalucard actually streams 1440p (might be 1080p source)

**Next Steps:**
- Test with authenticated Twitch session
- Check Twitch API documentation for quality tiers
- Verify streamer's actual output resolution
- Consider adding quality verification to UI

---

## 🟡 HIGH: Missing Log Files

**Problem:** Not all logs are being written to `/app/logs/` directory

**Current State (Docker Container `/app/logs/`):**
```bash
/app/logs/
├── app/          # EMPTY - no logs written
├── ffmpeg/       # Only CohhCarnage - missing Dhalucard, maxim
│   └── cohhcarnage/
└── streamlink/   # CORRECT - all streamers present
    ├── cohhcarnage/
    ├── dhalucard/
    └── maxim/
```

**Root Cause Analysis:**

1. **App Logs Empty:**
   - `get_streamer_log_dir()` creates subdirectories for each streamer
   - If directory creation fails, falls back to `base_dir` BUT doesn't create the file
   - `log_recording_activity_to_file()` tries to write to non-existent paths
   - Error logging indicates failure but doesn't prevent silent failures

2. **FFmpeg Logs Incomplete:**
   - Only CohhCarnage has FFmpeg logs (metadata_embed operations)
   - Dhalucard and maxim recordings don't trigger FFmpeg operations
   - Possible causes:
     * Segments not being merged yet
     * Post-processing not triggered
     * Different recording state for different streamers

3. **Streamlink Logs Working:**
   - All streamers have proper log directories
   - Proves directory creation works for streamlink
   - Shows recording is active for all streamers

**Fix Applied:**
- Changed `get_streamer_log_dir()` logging from `DEBUG` to `INFO` level
- Added explicit warning when falling back to base directory
- Better error visibility for directory creation failures

**Still Needed:**
- Verify why FFmpeg logs only created for one streamer
- Check if app log writes are failing silently
- Add directory creation validation at startup
- Implement health check for log directory writability

---

## 🔴 CRITICAL: Chapter Display Incorrect

**Problem:** Video player shows all chapters as 1 minute duration, displayed sequentially

**Expected Behavior:**
- Chapter 1: 0:00:00 - 1:33:32 (1 hour 33 min 32 sec)
- Chapter 2: 1:33:32 - 1:33:38 (6 seconds)
- Chapter 3: 1:33:38 - END

**Actual Behavior (UI):**
- All chapters show "1m" duration
- Displayed as sequential 1-minute blocks

**What Works:**
- ✅ Clicking "Next Chapter" button jumps to correct timestamp
- ✅ Chapter data timestamps are correct in backend

**Investigation Needed:**
1. Check chapter parsing in VideoPlayerView
2. Verify chapter duration calculation logic
3. Check if UI is using `start_time` instead of duration
4. Verify chapter data structure from API

**Affected Component:** `app/frontend/src/views/VideoPlayerView.vue` or `VideoPlayer.vue`

---

## 🟡 MEDIUM: Recording Progress Shows Fixed 50%

**Problem:** Recording progress indicator shows fixed 50% progress

**Why This Makes No Sense:**
- Live streams have unknown end time
- Cannot calculate progress percentage without knowing stream duration
- Misleading to users

**Recommendation:** 
- Remove progress percentage entirely
- Show "Recording..." status instead
- OR show elapsed time (e.g., "Recording for 1h 23m")

**Files to Check:**
- Recording state tracking
- Frontend display components
- API responses with recording status

---

## 📝 Next Steps

### Immediate (Now):
1. ✅ Remove max concurrent recordings limit
2. 🔄 Fix chapter display duration calculation
3. 🔄 Document H.265 codec investigation

### High Priority (Today):
4. Remove/fix recording progress indicator
5. Investigate missing log files
6. Debug H.265/1440p recording issue

### Medium Priority (Later):
7. Add codec/resolution info to recording metadata
8. Add frontend display of actual recording quality
9. Add user setting for preferred codec/resolution

---

## Testing Requirements

After fixes:
1. Test recording 5+ simultaneous streams
2. Verify H.265 streams record in native quality
3. Verify chapter durations display correctly
4. Check all logs are written to correct directories
5. Verify recording progress is removed/fixed

---

**Created:** November 15, 2025
**Status:** In Progress
**Priority:** Critical
