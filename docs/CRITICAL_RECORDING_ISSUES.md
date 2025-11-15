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

**Expected:** Record streams in their native codec and resolution
**Actual:** Downgraded to H.264/1080p

**Investigation Needed:**
1. Check streamlink command arguments in logs
2. Verify `--twitch-supported-codecs h264,h265` is working
3. Check if Twitch provides H.265 stream URLs
4. Verify streamlink version supports H.265

**Log Files:**
- `logs/streamlink_20251115_100208.log` (Dhalucard recording)
- `logs/streamlink_20251115_122547.log` (CohhCarnage recording)

**Streamlink Command Used:**
```bash
streamlink twitch.tv/Dhalucard best -o <output_path> \
  --hls-live-edge 99999 \
  --stream-timeout 200 \
  --stream-segment-timeout 200 \
  --stream-segment-threads 5 \
  --ffmpeg-fout mpegts \
  --twitch-disable-ads \
  --retry-streams 10 \
  --retry-max 5 \
  --loglevel debug \
  --twitch-supported-codecs h264,h265
```

**Possible Causes:**
1. Twitch not offering H.265 streams to StreamVault's user agent
2. Streamlink selecting 1080p60 instead of 1440p60
3. `--twitch-supported-codecs` not functioning as expected
4. Regional restrictions on H.265 streams

---

## 🟡 HIGH: Missing Log Files

**Problem:** Not all logs are being written to `/app/logs/` directory

**Expected Logs:**
- `app/logs/streamvault.log` (general app log)
- `app/logs/ffmpeg/<streamer>/` (FFmpeg operations)
- `app/logs/streamlink/<streamer>/` (Streamlink recordings)

**What's Missing:**
- `app/` directory completely empty (no new writes)
- `ffmpeg/` has only CohhCarnage (missing other streamers)
- General FFmpeg log missing
- `streamlink/` missing some streamer directories
- General streamlink log missing

**Files Found:**
- `logs/streamvault.log` (10MB - working)
- `logs/metadata_embed_20251115_181046_2025-11-15.log` (working)
- `logs/metadata_embed_20251115_181753_2025-11-15.log` (working)
- `logs/streamlink_20251115_100208.log` (working)
- `logs/streamlink_20251115_122547.log` (working)
- `logs/streamlink_20251115_124104.log` (working)

**Investigation Needed:**
1. Check logging configuration in `app/config/`
2. Verify directory permissions for `/app/logs/`
3. Check if logger is initialized correctly
4. Verify all recording operations use correct log paths

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
