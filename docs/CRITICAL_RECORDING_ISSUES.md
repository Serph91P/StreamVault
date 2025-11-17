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

## 🔴 FIXED: H.265/1440p Streams Not Recording in Native Quality

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
According to [Twitch Documentation](https://help.twitch.tv/s/article/2k-streaming):
> **You are not logged in**: Higher resolution playback is currently limited to logged-in viewers. Logged-out viewers can still watch content in 1080p.

Streamlink runs **unauthenticated by default** → Twitch treats it like a logged-out viewer → **1080p max**!

**Proof (From Twitch Web Player):**
```
Download Resolution: 2560x1440
Codecs: hev1.1.2.L150.90 (H.265/HEVC)
Protocol: HLS
```

Dhalucard **DOES** stream 1440p H.265, but only for authenticated users!

**Fix (Commit: pending):**
- Added `TWITCH_OAUTH_TOKEN` environment variable in `settings.py`
- Modified `get_streamlink_command()` to accept `oauth_token` parameter
- Added `--twitch-api-header "Authorization=OAuth <token>"` to streamlink command
- Updated `process_manager.py` to pass OAuth token from settings
- Created streamlink config file at `/app/config/streamlink/config.twitch`
- Updated README with OAuth token setup guide

**How to Enable:**
1. Open Twitch.tv in browser and login
2. Press F12 → Console
3. Run: `document.cookie.split("; ").find(item=>item.startsWith("auth-token="))?.split("=")[1]`
4. Copy token and add to `.env`: `TWITCH_OAUTH_TOKEN=your_token_here`
5. Restart container

**Without OAuth**: Limited to 1080p60 H.264  
**With OAuth**: Access to 1440p60 H.265/HEVC ✅

**Documentation:** See `docs/TWITCH_OAUTH_H265_SETUP.md` for complete setup guide

**Files Changed:**
- `app/config/settings.py` - Added TWITCH_OAUTH_TOKEN
- `app/utils/streamlink_utils.py` - Added --config parameter, per-streamer codec override
- `app/services/recording/process_manager.py` - Per-streamer codec priority
- `app/services/system/streamlink_config_service.py` - Auto-generate config from DB
- `app/routes/settings.py` - Quality/codec endpoints, config regeneration trigger
- `app/models.py` - Added StreamerRecordingSettings.supported_codecs
- `app/schemas/recording.py` - Added supported_codecs to schema
- `migrations/031_add_per_streamer_codecs.py` - Migration for per-streamer codecs
- `docker/docker-compose.yml` - Added env var and config volume
- `config/streamlink/.gitkeep` - Config directory README
- `README.md` - OAuth setup instructions

**How It Works:**
1. **Global Config** (`/app/config/streamlink/config.twitch`):
   - OAuth Token (from environment)
   - Default Codecs (from GlobalSettings)
   - Proxy Settings (from GlobalSettings)
   - Static Options (timeouts, retries, etc.)

2. **Per-Streamer Overrides** (CLI parameters):
   - Quality (from StreamerRecordingSettings.quality)
   - Codecs (from StreamerRecordingSettings.supported_codecs or global fallback)
   - Proxy (from health check - best available)

3. **Config Regeneration Triggers**:
   - Application startup
   - User changes proxy settings
   - User changes global codec preferences

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

1. **App Logs Created at Midnight Rotation:**
   - `TimedRotatingFileHandler` with `when='midnight'` doesn't create file until first rotation event
   - Path object was passed to handler instead of string (compatibility issue)
   - Fixed by converting to `str(app_logs_dir / 'streamvault.log')`
   - Added try/except to catch handler creation errors and log them

2. **FFmpeg Output Cluttering App Logs:**
   - `log_ffmpeg_output()` wrote full FFmpeg stdout/stderr to app logs via `ffmpeg_logger.info()`
   - App logs became cluttered with FFmpeg progress bars and verbose output
   - Fixed to only write summary to app logs (concise INFO/ERROR messages)
   - Full FFmpeg output ONLY in per-streamer files: `/app/logs/ffmpeg/{streamer_name}/`

3. **FFmpeg Logs Only for Post-Processing:**
   - FFmpeg logs created during metadata_embed, ts_to_mp4, thumbnail extraction
   - NOT created during live recording (only Streamlink runs)
   - Expected behavior - FFmpeg only used for post-processing operations

4. **Streamlink Logs Working:**
   - All streamers have proper log directories
   - Proves directory creation works correctly
   - Shows recording is active for all streamers

**Fix Applied (Commit: pending):**
- `app/config/logging_config.py`: Convert Path to string, add try/except for handler creation
- `app/services/system/logging_service.py`: Separate FFmpeg output from app logs (DEBUG only)
- FFmpeg stdout/stderr now ONLY written to per-streamer files
- App logs get concise summary: `✅ operation completed for streamer - logs: /path/`

**Files Changed:**
- `app/config/logging_config.py` - Fix TimedRotatingFileHandler path, add error handling
- `app/services/system/logging_service.py` - Remove FFmpeg output from app logs

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
