# H.265/AV1 Codec Support for Higher Quality Recordings

## 🟡 Priority: HIGH
**Status:** 🟡 PARTIALLY IMPLEMENTED - Needs UI & Testing  
**Estimated Time:** 2-3 hours  
**Sprint:** Sprint 1 - Critical Bugs & Features  
**Impact:** HIGH - Enables 1440p60 recordings (up from 1080p60)

---

## 📝 Problem Description

### Current Limitation (H.264 Only)

**Maximum Quality Available:**
- Current recordings limited to **H.264 codec**
- Maximum resolution: **1080p60** (Full HD)
- Works on all hardware but limited quality

**User Impact:**
- Cannot record streams in **1440p60** (2K quality)
- Missing out on higher quality content from streamers who broadcast in H.265/AV1
- Future-proofing: More streamers switching to modern codecs

### Why This Matters

**Twitch Platform Changes:**
- Twitch now allows streamers to broadcast in:
  - **H.265 (HEVC)**: Up to 1440p60 on supported channels
  - **AV1**: Up to 1440p60 (experimental, very rare)
  - **H.264 (legacy)**: Maximum 1080p60 (current default)

**Example Scenario:**
1. Streamer broadcasts in 1440p60 using H.265
2. StreamVault currently only requests H.264 streams
3. Gets downscaled 1080p60 version instead
4. **Result:** Lower quality recording than available

**Real-World Availability:**
- Not all channels support H.265/AV1 (most still use H.264)
- Depends on broadcaster settings and Twitch platform support
- When available, quality improvement is **significant** (40% better bitrate efficiency)

---

## 🎯 Solution: Enable H.265/AV1 Codec Support

### Overview

Implement codec selection in recording settings using Streamlink 8.0.0+ feature: `--twitch-supported-codecs`

**Key Features:**
- User-configurable codec preferences
- Safe defaults (H.264 + H.265 fallback)
- Automatic quality selection
- Backend already partially implemented (Migration 024 exists)
- **Missing:** Frontend UI for configuration

### How Streamlink Codec Selection Works

**Available Codec Combinations:**
- `h264` - H.264 only (maximum 1080p60, highest compatibility)
- `h265` - H.265 only (1440p60 capable, requires modern hardware)
- `av1` - AV1 only (experimental, newest hardware required)
- `h264,h265` - **RECOMMENDED** - Prefer H.265, fallback to H.264
- `h264,h265,av1` - All codecs (future-proof)

**Selection Logic:**
- Streamlink requests specified codecs from Twitch
- Twitch returns available stream qualities for those codecs
- Streamlink selects best available quality (if `prefer_higher_quality=true`)
- Falls back to next codec if primary not available

**Example Stream Availability:**

When codec preference = `h264` only:
```
Available qualities:
- 1080p60 (H.264) - chunked
- 720p30 (H.264)
- 480p30 (H.264)
- audio_only
```

When codec preference = `h264,h265`:
```
Available qualities:
- 1440p60 (H.265) - chunked  ← NEW! Higher quality
- 1080p60 (H.264)
- 720p60 (H.265)
- 480p30 (H.264) - fallback
- audio_only
```

---

## 📋 Current Implementation Status

### ✅ Already Implemented (Backend)

**Database Schema (Migration 024):**
- `RecordingSettings.supported_codecs` column exists
- `RecordingSettings.prefer_higher_quality` column exists
- Default value: `"h264,h265"` (safe default with fallback)

**File:** `app/models.py` (line 234-236)
```
supported_codecs: str = Column(String, default="h264,h265")
prefer_higher_quality: bool = Column(Boolean, default=True)
```

**Process Manager Integration:**
- File: `app/services/recording/process_manager.py` (line 174)
- Codec preferences read from database
- Passed to Streamlink command via `--twitch-supported-codecs` argument

### ❌ Missing (Needs Implementation)

**Frontend UI Components:**
1. Codec selection dropdown in Settings
2. Quality preference toggle
3. Codec capability warnings (hardware requirements)
4. Real-time codec info display during recording

**API Endpoints:**
1. GET `/api/recording/codec-options` - List available codec combinations
2. POST `/api/recording/settings` - Update codec preferences (already exists, needs codec fields)

**Documentation:**
1. User guide explaining codec options
2. Hardware requirements for H.265/AV1 playback
3. Troubleshooting section for decode issues

---

## 📋 Required Changes

### Backend Components

**1. Constants Definition**
- Location: `app/config/constants.py`
- Purpose: Define codec options with metadata
- Constants needed:
  - `SUPPORTED_CODECS` - Dictionary mapping codec strings to metadata (label, description, max resolution, compatibility level, hardware requirements)
  - `DEFAULT_CODEC_PREFERENCE` - Default safe value ("h264,h265")
  - Codec metadata structure:
    - `label`: Display name (e.g., "H.264 + H.265 (Recommended)")
    - `description`: Explanation of codec capabilities
    - `max_resolution`: Maximum available resolution (e.g., "1440p60")
    - `compatibility`: Hardware compatibility level (high/medium/low)
    - `requires_modern_hardware`: Boolean flag for hardware requirements
    - `recommended`: Boolean flag to mark recommended option

**2. API Endpoint - Codec Options**
- Location: `app/routes/recording.py`
- New endpoint: GET `/api/recording/codec-options`
- Purpose: Return list of available codec combinations with descriptions
- Response structure:
  - `codecs`: Dictionary of codec options with metadata
  - `default`: Default codec preference string
  - `recommended`: Recommended codec string
- Returns 5 codec options: h264, h265, av1, h264+h265, h264+h265+av1

**3. API Endpoint - Settings Update**
- Location: `app/routes/recording.py`
- Existing endpoint: POST `/api/recording/settings`
- Add support for codec fields:
  - `supported_codecs` (string): Comma-separated codec list
  - `prefer_higher_quality` (boolean): Auto-select highest quality flag
- Validation requirements:
  - Codec string must contain only valid codecs: h264, h265, av1
  - Comma-separated format required (no spaces)
  - Reject empty string
  - Normalize to lowercase
- Response includes updated settings

**4. Process Manager Integration**
- Location: `app/services/recording/process_manager.py` (line ~174)
- Already implemented: Reads codec preference from database
- Passes to Streamlink command via `--twitch-supported-codecs` argument
- Logs codec selection decision
- No changes needed (verify implementation)

---

### Frontend Components

**1. TypeScript Types**
- Location: Update `app/frontend/src/types/settings.ts`
- Add `CodecOption` interface:
  - `value`: string (codec string like "h264,h265")
  - `label`: string (display name)
  - `description`: string (explanation)
  - `maxResolution`: string (e.g., "1440p60")
  - `compatibility`: 'high' | 'medium' | 'low'
  - `requiresModernHardware`: boolean
  - `recommended`: boolean (optional)
- Update `RecordingSettings` interface:
  - Add `supported_codecs`: string field
  - Add `prefer_higher_quality`: boolean field

**2. Composable**
- Location: Update `app/frontend/src/composables/useRecordingSettings.ts`
- Add codec management functionality:

**State to add:**
- `codecOptions` - Array of CodecOption objects from API
- `currentCodecs` - Currently selected codec string
- `preferHigherQuality` - Boolean flag

**Methods to implement:**
- `fetchCodecOptions()` - Load available codec combinations from API
- `updateCodecPreference(codecs: string)` - Update codec preference
- `toggleQualityPreference()` - Toggle prefer_higher_quality flag

**Computed Properties:**
- `selectedCodecOption` - Find current codec option in codecOptions array
- `codecWarnings` - Generate warning messages for selected codec:
  - Show H.265 hardware warning if "h265" in codec string
  - Show AV1 hardware warning if "av1" in codec string
  - Show fallback warning if no "h264" in codec string
  - Show compatibility warning if compatibility === 'low'

**3. CodecSettingsPanel Component**
- Location: New file `app/frontend/src/components/settings/CodecSettingsPanel.vue`
- Display in: Settings View (Recording section or new Codec section)

**UI Elements Required:**

**Codec Selection (Dropdown or Radio Buttons):**
- List all 5 codec options from API
- Show label and description for each option
- Highlight recommended option ("h264,h265") with badge
- Display max resolution for each codec
- Show compatibility indicator (high/medium/low)

**Selected Codec Details:**
- Display currently selected codec name
- Show maximum resolution available
- Display compatibility level with icon/color
- Show hardware requirements if applicable

**Hardware Warnings (Conditional Display):**
- Show when H.265 selected:
  - "⚠️ H.265 playback requires hardware decoding support (Intel 6th gen+, AMD Polaris+, NVIDIA 9xx+, Apple M1+)"
- Show when AV1 selected:
  - "⚠️ AV1 playback requires very modern hardware (Intel 11th gen+, AMD Zen 3+, NVIDIA 30xx+, Apple M3+)"
- Show when no H.264 fallback:
  - "⚠️ No H.264 fallback - some streams may not be recordable"

**Quality Preference Toggle:**
- Label: "Prefer Higher Quality"
- Description: "Automatically select highest available quality when multiple codecs available"
- Default: ON (true)
- Toggle switch component

**Info Section:**
- Explain codec availability depends on broadcaster
- Note: Not all streams support H.265/AV1
- Link to documentation for more details

**Save/Apply Button:**
- Save codec preferences to database
- Show success toast on save
- Show error toast on failure

**4. Settings View Integration**
- Location: `app/frontend/src/views/SettingsView.vue`
- Add CodecSettingsPanel to Recording section
- Can be separate section or part of existing Recording settings
- Import CodecSettingsPanel component
- Add section header: "Video Codec Settings"

---

---

## 📂 Files to Create

**Backend:**
- None (Migration 024 already exists and is applied)

**Frontend:**
- `app/frontend/src/components/settings/CodecSettingsPanel.vue` - New Vue component for codec configuration UI

---

## 📂 Files to Modify

**Backend:**
- `app/config/constants.py` - Add SUPPORTED_CODECS dictionary with codec metadata
- `app/routes/recording.py` - Add GET `/api/recording/codec-options` endpoint
- `app/routes/recording.py` - Update existing POST `/api/recording/settings` to include codec fields

**Frontend:**
- `app/frontend/src/types/settings.ts` - Add CodecOption interface and update RecordingSettings
- `app/frontend/src/composables/useRecordingSettings.ts` - Add codec management methods and computed properties
- `app/frontend/src/views/SettingsView.vue` - Import and render CodecSettingsPanel component

---

## ✅ Acceptance Criteria

### Database & Migration
- [x] Migration 024 exists and has been applied
- [x] `RecordingSettings.supported_codecs` column exists with default "h264,h265"
- [x] `RecordingSettings.prefer_higher_quality` column exists with default TRUE
- [ ] Settings persist across application restarts

### Backend API
- [ ] GET `/api/recording/codec-options` returns 5 codec options with metadata
- [ ] Response includes recommended codec flag
- [ ] POST `/api/recording/settings` accepts `supported_codecs` field
- [ ] POST `/api/recording/settings` accepts `prefer_higher_quality` field
- [ ] Codec string validation rejects invalid codecs
- [ ] API returns 400 error for invalid codec strings

### Process Manager Integration
- [x] ProcessManager reads codec preference from database (line 174)
- [x] Streamlink command includes `--twitch-supported-codecs` argument
- [x] Codec selection logged in recording logs
- [ ] Verify argument passed correctly in test recording

### Frontend UI
- [ ] CodecSettingsPanel displays 5 codec options
- [ ] Recommended badge visible on "h264,h265" option
- [ ] Hardware requirement warnings display for H.265/AV1
- [ ] No fallback warning shows when H.264 not in codec string
- [ ] Compatibility indicator (high/medium/low) visible for each option
- [ ] "Prefer Higher Quality" toggle functional
- [ ] Save button updates settings via API
- [ ] Success toast shows after successful save
- [ ] Error toast shows on API failure
- [ ] Settings reflect in UI after page reload

### Recording Quality
- [ ] New recording with "h264,h265" uses H.265 when available
- [ ] Recording with "h264" only uses H.264 (max 1080p60)
- [ ] Recording with H.265 available shows 1440p60 quality option
- [ ] Recording without H.265 available falls back to H.264
- [ ] File size smaller with H.265 (~30% reduction at same quality)
- [ ] Playback successful on modern browsers

---

## 🧪 Testing Checklist

### Backend Testing
- [ ] Run migration 024 (if not already applied): `python migrations/manage.py upgrade`
- [ ] Verify default codec in database: `SELECT supported_codecs FROM recording_settings;`
- [ ] Expected result: `h264,h265`
- [ ] Test API endpoint GET `/api/recording/codec-options` in browser/Postman
- [ ] Verify response contains 5 codec options with metadata
- [ ] Test API validation: POST `/api/recording/settings` with invalid codec "xyz"
- [ ] Expected: 400 error "Invalid codec specified"

### Frontend Testing
- [ ] Open Settings page
- [ ] Navigate to Recording/Codec settings section
- [ ] Verify 5 codec options displayed
- [ ] Verify "h264,h265" marked as Recommended
- [ ] Select "h265" only
- [ ] Expected: Hardware warning appears
- [ ] Expected: No fallback warning appears
- [ ] Select "av1" only
- [ ] Expected: Modern hardware warning appears
- [ ] Expected: Low compatibility warning appears
- [ ] Expected: No fallback warning appears
- [ ] Toggle "Prefer Higher Quality" off/on
- [ ] Click Save button
- [ ] Expected: Success toast appears
- [ ] Reload page
- [ ] Expected: Settings preserved

### Recording Integration Testing
- [ ] Set codec to "h264" only
- [ ] Start test recording with any Twitch channel
- [ ] Check logs for: `🎬 Using codec preference: h264`
- [ ] Check streamlink command includes: `--twitch-supported-codecs h264`
- [ ] Stop recording
- [ ] Check maximum available quality was 1080p60
- [ ] Set codec to "h264,h265"
- [ ] Start recording with 1440p-capable channel (if available)
- [ ] Check logs for: `🎬 Using codec preference: h264,h265`
- [ ] Verify 1440p60 quality option available (if broadcaster supports)
- [ ] Compare file sizes between h264-only and h264+h265 recording
- [ ] Expected: h265 file ~30% smaller at same resolution

### Playback Testing
- [ ] Test playback on Chrome/Edge (built-in H.265 support on Windows)
- [ ] Test playback on Firefox (check H.265 support)
- [ ] Test playback on Safari (native H.265 support)
- [ ] Test playback on mobile device (check hardware decode)
- [ ] Test playback on older device (verify fallback to H.264 if needed)

### Edge Case Testing
- [ ] Test with channel that doesn't support H.265
- [ ] Expected: Falls back to H.264, recording still works
- [ ] Test with very old Twitch VOD (h264 only)
- [ ] Expected: Recording succeeds with H.264
- [ ] Test network interruption during h265 recording
- [ ] Expected: Recovery works same as h264

---

## 📖 Documentation References

**Primary Implementation Guide:**
- `docs/BACKEND_FEATURES_PLANNED.md` (Section 1, lines 1-556) - Complete implementation details with all code examples

**Task Tracking:**
- `docs/MASTER_TASK_LIST.md` (Task #4) - Project task list entry

**External Documentation:**
- [Streamlink Twitch Plugin - supported-codecs](https://streamlink.github.io/cli/plugins/twitch.html#twitch-supported-codecs) - Official Streamlink documentation
- [Twitch Engineering Blog - H.265 Rollout](https://blog.twitch.tv/) - Twitch's codec support announcement (if available)

**Related Database Migrations:**
- `migrations/024_add_codec_preferences.py` - Database schema migration (already applied)

---

## 🔒 Security Considerations

**No sensitive data in codec preferences:**
- Codec strings are safe to log (no user data, no credentials)
- No PII in codec selection

**Validation required:**
- Validate codec string against allowed values (h264, h265, av1)
- Reject malformed or unsafe input
- Prevent SQL injection via parameterized queries

**Performance considerations:**
- No security risk from codec choice
- H.265 decode may use more CPU on older hardware
- Recommend hardware decode acceleration warning in UI

---

## 🎯 Best Practices

**Safe Defaults:**
- Default to "h264,h265" (not h265 only) - ensures fallback
- Enable "prefer_higher_quality" by default - users want best quality
- Never default to AV1 only - too low compatibility

**User Experience:**
- Show clear warnings for low compatibility codecs
- Explain hardware requirements upfront
- Provide "Recommended" badge for safe option
- Allow easy reset to default

**Codec Selection Logic:**
- Always include h264 in production setups (fallback safety)
- Test h265 availability before recommending h265-only
- AV1 should be opt-in experimental (not default)

**Error Handling:**
- Log codec selection decisions
- Handle streamlink codec errors gracefully
- Fall back to default codec on validation failure

**Performance:**
- H.265 reduces file size ~30% (saves storage)
- Decode performance depends on hardware acceleration
- Monitor CPU usage on older devices

**Testing:**
- Test with both h265-capable and h264-only channels
- Verify fallback behavior works correctly
- Test playback on target devices before production

---

## 🤖 Copilot Instructions

### Context & Background

**Feature Goal:**
Enable H.265/AV1 codec support for Twitch recordings using Streamlink 8.0.0+ `--twitch-supported-codecs` argument. This allows recording in 1440p60 quality (up from 1080p60 H.264 limit) while reducing file sizes by ~30%.

**Current State:**
- Backend ~80% complete (Migration 024 applied, database columns exist, process manager integration exists)
- Frontend 0% complete (no UI components exist)
- Need: API endpoints, frontend UI, testing

**Technical Background:**
- Streamlink 8.0.0+ introduced `--twitch-supported-codecs` argument
- Twitch streams available in multiple codecs: H.264 (1080p60 max), H.265/HEVC (1440p60), AV1 (experimental)
- Not all channels support H.265/AV1 (most still H.264 only)
- Codec availability depends on broadcaster settings

---

### Architecture Overview

**Data Flow:**
```
User selects codec in UI
  → Frontend saves to API
  → Backend updates RecordingSettings table
  → ProcessManager reads codec preference
  → Streamlink command includes --twitch-supported-codecs
  → Twitch returns available qualities for codecs
  → Recording proceeds with best quality
```

**Key Components:**
1. **Database:** `recording_settings.supported_codecs` (string, default "h264,h265")
2. **Constants:** `SUPPORTED_CODECS` dictionary with codec metadata
3. **API:** GET `/codec-options`, POST `/settings` (update existing)
4. **Frontend:** CodecSettingsPanel.vue, useRecordingSettings composable
5. **Process Manager:** Reads codec, passes to streamlink (already implemented)

---

### Implementation Patterns

**Pattern 1: Safe Defaults**
```
Always default to "h264,h265" (not h265 only)
Reason: Provides fallback if h265 unavailable
Result: Works with all channels, gets h265 when available
```

**Pattern 2: Validation**
```
Valid codecs: h264, h265, av1
Format: Comma-separated string (no spaces)
Validation: Split by comma, check each against allowed list
Reject: Empty string, unknown codecs, malformed input
```

**Pattern 3: Hardware Warnings**
```
Show warnings based on codec selection:
- H.265: Requires Intel 6th gen+, AMD Polaris+, NVIDIA 9xx+
- AV1: Requires Intel 11th gen+, AMD Zen 3+, NVIDIA 30xx+
- No H.264 in string: Warn about missing fallback
```

**Pattern 4: Streamlink Command**
```
Existing implementation (line 174 in process_manager.py):
codec_preference = recording_settings.supported_codecs or "h264,h265"
command.extend(["--twitch-supported-codecs", codec_preference])
```

---

### Dependencies

**Backend Dependencies (Already Satisfied):**
- ✅ Streamlink 8.0.0+ (check requirements.txt)
- ✅ PostgreSQL database
- ✅ Migration 024 applied

**Frontend Dependencies:**
- ✅ Vue 3 Composition API
- ✅ TypeScript
- ✅ Existing useRecordingSettings composable (extend it)
- ✅ Global SCSS utilities (use for component styling)

**External Dependencies:**
- Twitch platform support for H.265/AV1 (broadcaster-dependent)
- User hardware decode acceleration (playback quality)

---

### Files to Read First

1. **`migrations/024_add_codec_preferences.py`** - See database schema structure
2. **`app/models.py` (lines 234-236)** - See existing database columns
3. **`app/services/recording/process_manager.py` (line ~174)** - See how codec passed to streamlink
4. **`docs/BACKEND_FEATURES_PLANNED.md` (Section 1)** - Complete implementation guide with code examples
5. **`app/frontend/src/composables/useRecordingSettings.ts`** - Existing settings management pattern

---

### Testing Strategy

**Phase 1: Backend Validation**
1. Test API endpoint returns 5 codec options
2. Test codec validation rejects invalid input
3. Test settings persist to database
4. Test streamlink command includes codec argument

**Phase 2: Frontend Integration**
1. Test UI displays codec options correctly
2. Test warnings show for low compatibility codecs
3. Test save functionality updates backend
4. Test settings persist after page reload

**Phase 3: Recording Integration**
1. Test recording with "h264" only → Check logs for codec
2. Test recording with "h264,h265" → Check for 1440p availability
3. Compare file sizes (h265 should be ~30% smaller)
4. Test fallback when h265 unavailable

**Phase 4: Playback Testing**
1. Test on Chrome/Edge (Windows H.265 support)
2. Test on Firefox (may need plugin)
3. Test on Safari (native H.265)
4. Test on mobile device

---

### Success Criteria

**Backend Complete When:**
- ✅ Migration 024 applied successfully
- ✅ API endpoints return correct data
- ✅ Settings validation works
- ✅ Codec passed to streamlink command

**Frontend Complete When:**
- CodecSettingsPanel component functional
- All 5 codec options selectable
- Warnings display correctly
- Save button updates backend
- Settings persist after reload

**Feature Complete When:**
- Recording with h265 produces 1440p60 (when available)
- Recording with h264 falls back correctly
- File sizes reduced with h265 (~30%)
- Playback works on modern browsers
- User can easily switch codecs

---

### Common Pitfalls

**❌ Pitfall 1: Assuming all channels support H.265**
- Reality: Most channels still use H.264 only
- Solution: Always include H.264 in codec preference (fallback)
- Test with both h265-capable and h264-only channels

**❌ Pitfall 2: Not showing hardware warnings**
- Reality: H.265/AV1 require hardware decode for smooth playback
- Solution: Show warnings for compatibility/hardware requirements
- Recommend "h264,h265" as default (fallback included)

**❌ Pitfall 3: Validation errors not user-friendly**
- Reality: Users may enter invalid codec strings
- Solution: Validate on frontend AND backend, show clear error messages
- Normalize input (lowercase, trim whitespace)

**❌ Pitfall 4: Not testing fallback behavior**
- Reality: Codec may not be available even if requested
- Solution: Test with h264-only channels to verify fallback works
- Log codec selection in recording logs

**❌ Pitfall 5: Forgetting to update existing settings endpoint**
- Reality: POST `/api/recording/settings` already exists
- Solution: Extend existing endpoint, don't create duplicate
- Ensure backward compatibility with existing fields

---

### Debugging Tips

**Backend Issues:**
```
Check logs for: "🎬 Using codec preference: h264,h265"
Verify database: SELECT supported_codecs FROM recording_settings;
Test streamlink command manually: streamlink --twitch-supported-codecs=h264,h265 <url> best
Check Streamlink version: streamlink --version (must be 8.0.0+)
```

**Frontend Issues:**
```
Check browser console for API errors
Verify fetch includes credentials: 'include'
Check network tab for API request/response
Verify TypeScript types match backend response
Test with Vue DevTools for component state
```

**Recording Issues:**
```
Check if broadcaster supports H.265 (most don't yet)
Verify streamlink command in logs includes codec argument
Test with known h265-capable channel
Compare available qualities with h264 vs h264+h265
Check file properties (codec, resolution) with mediainfo
```

---

### External Resources

**Streamlink Documentation:**
- [Twitch Plugin - supported-codecs](https://streamlink.github.io/cli/plugins/twitch.html#twitch-supported-codecs)
- Explains argument format and behavior

**Codec Information:**
- H.264: Universal compatibility, max 1080p60, larger files
- H.265/HEVC: 30% better compression, max 1440p60, requires modern hardware
- AV1: Best compression, experimental, requires very modern hardware (2020+)

**Hardware Decode Requirements:**
- H.265: Intel 6th gen+ (Skylake), AMD Polaris+, NVIDIA 9xx+, Apple M1+
- AV1: Intel 11th gen+, AMD Zen 3+, NVIDIA 30xx+, Apple M3+

---

**Remember:**
- Default to "h264,h265" (safe + quality)
- Validate codec strings (security)
- Show hardware warnings (UX)
- Test fallback behavior (reliability)
- Log codec selections (debugging)

Feature is ~80% done - mainly needs frontend UI implementation and testing!


