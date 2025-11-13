# StreamVault - Master Task List

**Last Updated:** 12. November 2025  
**Total Tasks:** 59 (Backend: 8 | Frontend: 51)  
**Completed:** 34 (58%)  
**Remaining:** 25 (42%)

---

## 📊 Status Overview

### Backend Features (8 tasks total)
- ✅ **COMPLETED:** 5 tasks (62.5%)
  - H.265/AV1 Codec Support (implemented, needs testing)
  - Stream Recovery After Restart (zombie cleanup)
  - Apprise Integration (4 notification points)
  - Toast Notification System
  - Recording Failure Detection
- 🔴 **CRITICAL:** 2 tasks (Multi-Proxy + Streamlink Recovery)
- ⏸️ **DEFERRED:** 1 task

### Frontend Issues (51 tasks total)
- ✅ **COMPLETED:** 29 tasks (57%)
  - Design System Migration (complete)
  - Mobile Optimization (Session 6)
  - SCSS Breakpoint Refactoring (50+ files)
  - Component Polish (Session 2-5)
- 🔴 **CRITICAL:** 6 tasks (UI Bugs from testing)
- 🟡 **HIGH PRIORITY:** 3 tasks (Mobile tables, last stream info)
- 🟢 **MEDIUM PRIORITY:** 13 tasks (polish & enhancements)

---

## 🔴 CRITICAL PRIORITY (Do First)

### 1. ✅ Apprise Integration (COMPLETED)
**Status:** ✅ PRODUCTION READY - Needs end-to-end testing  
**Time:** ~90 minutes (already done)  
**Impact:** HIGH - External notifications for recording events

**Completed:**
- ✅ Migration 027: Error tracking columns
- ✅ Migration 028: Notification settings columns
- ✅ Backend: 4 notification points in process_manager.py
- ✅ Service: external_notification_service.py
- ✅ Frontend: NotificationSettingsPanel.vue (checkboxes + UI)

**Testing Needed:**
- [ ] Configure Apprise URL (ntfy/Discord/Telegram)
- [ ] Test recording_started notification
- [ ] Test recording_failed notification
- [ ] Test recording_completed notification
- [ ] Verify logs: `tail -f logs/streamvault.log | grep "Apprise"`

**Files:**
- `app/services/recording/process_manager.py` (lines 330, 573, 711, 1169)
- `app/services/notifications/external_notification_service.py`
- `app/frontend/src/components/settings/NotificationSettingsPanel.vue`

**Documentation:** `docs/SESSION_7_STATUS.md`

---

### 2. 🔴 Fix 6 UI Bugs from Testing (CRITICAL)
**Status:** 🔴 NOT STARTED  
**Priority:** 1 - MUST FIX before production  
**Time:** 2.5-4 hours (Phase 1: 90-120min | Phase 2: 60-105min)  
**Impact:** HIGH - User experience broken

**Phase 1: Functional Bugs (90-120 minutes)**

#### Bug 1: Test Notification Button Broken (20-30min)
- **Problem:** Button exists but does nothing when clicked
- **File:** `NotificationSettingsPanel.vue` (~372)
- **Root Cause:** Parent event handler disconnected after rework
- **Fix:** Reconnect @test-notification="handleTestNotification" in SettingsView.vue
- **Verify:** API endpoint /api/settings/test-notification exists

#### Bug 2: Clear Notifications Button Broken (20-30min)
- **Problem:** Button doesn't clear notification list
- **File:** `NotificationPanel.vue`
- **Root Cause:** Event handler or API endpoint issue
- **Fix:** Check event handler connection + API endpoint /api/notifications/clear
- **Verify:** State cleared after API success

#### Bug 3: Chapter Duplicate - First Chapter Shown 2x (30-45min)
- **Problem:** First chapter appears twice in list (Screenshot: Screen2)
- **File:** `WatchView.vue`, `app/services/metadata/chapter_service.py`
- **Root Cause:** Database duplicate OR query issue OR v-for key problem
- **Debug:**
  ```sql
  SELECT * FROM chapters WHERE stream_id = 37 ORDER BY start_time;
  ```
- **Fix:** Fix query or ensure v-for :key="chapter.id" (unique ID, not index)

#### Bug 4: Fullscreen Exit Broken (20-30min)
- **Problem:** Native browser exit button doesn't work, video stays fullscreen
- **File:** `WatchView.vue`
- **Root Cause:** Missing fullscreenchange event listener
- **Fix:**
  ```typescript
  onMounted(() => {
    document.addEventListener('fullscreenchange', () => {
      isFullscreen.value = !!document.fullscreenElement
    })
  })
  ```

**Phase 2: Design Polish (60-105 minutes)**

#### Bug 5: Notifications Panel Design Missing (30-45min)
- **Problem:** Works but needs Design System tokens
- **File:** `NotificationPanel.vue`
- **Fix:** Apply CSS variables (--background-card, --spacing-*, --radius-*)

#### Bug 6: Video Player Design Missing (30-60min)
- **Problem:** Works but styling doesn't match requirements
- **File:** `WatchView.vue`
- **Fix:** User requirements needed + apply Design System tokens

**Documentation:** `docs/KNOWN_ISSUES_SESSION_7.md` (complete debugging guide)

---

### 3. 🔴 Multi-Proxy System with Health Checks (CRITICAL)
**Status:** 📝 Documented - Ready for Implementation  
**Priority:** CRITICAL (current proxy DOWN → recordings fail)  
**Time:** 3-4 hours  
**Impact:** HIGH - Prevents recording failures

**Current Problem:**
- Proxy `http://serph91p:***@77.90.19.62:9999` returns 500 error
- ALL recordings fail after ~1 minute
- No fallback mechanism

**Solution: Application-Level Proxy Rotation**

**Backend Tasks (2-3 hours):**
1. **Migration 025:** `proxy_settings` table
   - Fields: proxy_url, priority, enabled, health_status, last_health_check
   - Backfill existing proxy from recording_settings
2. **ProxyHealthService:** Health check service (NEW file)
   - `check_proxy_health()`: Test connectivity (10s timeout)
   - `get_best_proxy()`: Select best proxy by health/priority
   - `run_health_checks()`: Periodic checks (5 min interval)
3. **ProcessManager Update:** Use proxy rotation
   - Get proxy from `ProxyHealthService`
   - Fallback to direct connection if all proxies fail
4. **API Endpoints:** `/api/proxy/*` (list, add, remove, test, toggle)

**Frontend Tasks (1 hour):**
1. **ProxySettingsPanel.vue:** NEW component
   - List proxies with health status badges
   - Add/Remove proxy functionality
   - Test proxy button (manual health check)
   - Enable/Disable toggle
   - Priority sorting
2. **useProxySettings.ts:** NEW composable
   - Fetch proxies, add/remove/test/toggle
   - WebSocket listener for health updates
   - System status computed property

**Files to Create:**
- `migrations/025_add_multi_proxy_support.py`
- `app/services/proxy/proxy_health_service.py`
- `app/routes/proxy.py`
- `app/frontend/src/types/proxy.ts`
- `app/frontend/src/composables/useProxySettings.ts`
- `app/frontend/src/components/settings/ProxySettingsPanel.vue`

**Files to Modify:**
- `app/services/recording/process_manager.py` (_build_streamlink_command)
- `app/models.py` (RecordingSettings - add proxy config fields)

**Documentation:** `docs/BACKEND_FEATURES_PLANNED.md` (Section 2)

**Testing Checklist:**
- [ ] Migration runs successfully
- [ ] Add proxy via UI
- [ ] Health checks run every 5 minutes
- [ ] Proxy auto-disables after 3 failures
- [ ] Recordings use best available proxy
- [ ] Fallback to direct connection works
- [ ] WebSocket updates frontend in real-time

---

### 4. 🔴 H.265/AV1 Codec Support (HIGH PRIORITY)
**Status:** 📝 Documented - Ready for Implementation  
**Priority:** HIGH (enables 1440p recordings)  
**Time:** 4-6 hours  
**Impact:** HIGH - Better quality, smaller files

**Background:**
- Twitch supports H.265 (1440p60) and AV1 streams
- Streamlink 8.0.0+ has `--twitch-supported-codecs` argument
- Current recordings limited to H.264 (1080p60 max)

**Backend Tasks (3-4 hours):**
1. **Migration 024:** Add codec preference fields
   - `supported_codecs` (String, default: "h264,h265")
   - `prefer_higher_quality` (Boolean, default: True)
2. **Constants:** Add codec options to `app/config/constants.py`
   ```python
   SUPPORTED_CODECS = {
     "h264": "H.264 (1080p max)",
     "h265": "H.265 (1440p capable)",
     "h264,h265": "H.264 + H.265 (RECOMMENDED)"
   }
   ```
3. **ProcessManager:** Add codec arg to streamlink command
   ```python
   command.extend(["--twitch-supported-codecs", codec_preference])
   ```
4. **API Endpoints:**
   - GET `/api/recording/codec-options`
   - POST `/api/recording/settings` (with codec validation)

**Frontend Tasks (2 hours):**
1. **CodecSettingsPanel.vue:** NEW component
   - Radio buttons for codec selection (5 options)
   - Recommended badge on "h264,h265"
   - Warning alerts for low compatibility codecs
   - Info box explaining codecs
2. **useRecordingSettings.ts:** Add codec methods
   - `fetchCodecOptions()`
   - `updateCodecSettings()`
   - `codecWarnings` computed property

**Files to Create:**
- `migrations/024_add_codec_preferences.py`
- `app/frontend/src/components/settings/CodecSettingsPanel.vue`

**Files to Modify:**
- `app/config/constants.py` (add SUPPORTED_CODECS)
- `app/services/recording/process_manager.py` (_build_streamlink_command)
- `app/routes/recording.py` (add codec endpoints)
- `app/frontend/src/types/settings.ts` (add codec fields)
- `app/frontend/src/composables/useRecordingSettings.ts`
- `app/frontend/src/views/SettingsView.vue` (add CodecSettingsPanel)

**Documentation:** `docs/BACKEND_FEATURES_PLANNED.md` (Section 1 - complete implementation guide)

**Benefits:**
- ✅ Up to 1440p60 recordings (broadcaster dependent)
- ✅ ~30% smaller files with H.265
- ✅ Future-proof with AV1 support
- ✅ Automatic fallback to H.264

**Testing Checklist:**
- [ ] Migration adds columns successfully
- [ ] Default codec "h264,h265" set
- [ ] Streamlink receives correct --twitch-supported-codecs arg
- [ ] Test with h264-only channel (most channels)
- [ ] Test with h265-capable channel (1440p streamer)
- [ ] Verify file sizes (h265 ≈ 30% smaller)
- [ ] Test playback compatibility

---

## 🟡 HIGH PRIORITY (Next After Critical)

### 5. 🟡 Settings Tables Mobile Responsive
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH (mobile UX broken)  
**Time:** 6-8 hours  
**Impact:** HIGH - Tables unusable on mobile

**Problem:**
- Notification settings table: 5+ columns don't fit on mobile
- Recording settings table: Complex layout with select dropdowns
- Horizontal scroll is bad UX
- Checkboxes too small for touch (18px)

**Solution: Transform to Cards < 768px**

**Files to Modify:**
- `app/frontend/src/components/settings/NotificationSettingsPanel.vue`
- `app/frontend/src/components/settings/RecordingSettingsPanel.vue`

**Implementation:**

**1. NotificationSettingsPanel.vue (3-4 hours):**
```vue
<!-- Desktop: Table (≥ 768px) -->
<table class="desktop-only">...</table>

<!-- Mobile: Cards (< 768px) -->
<div class="mobile-only streamer-cards">
  <GlassCard v-for="streamer in streamers" :key="streamer.id">
    <div class="card-header">
      <img :src="streamer.profile_image" />
      <h3>{{ streamer.display_name }}</h3>
    </div>
    
    <div class="notification-toggles">
      <label class="toggle-row">
        <span>Notify when online</span>
        <input type="checkbox" v-model="streamer.notify_online" />
      </label>
      <!-- ... more toggles ... -->
    </div>
  </GlassCard>
</div>
```

**2. RecordingSettingsPanel.vue (3-4 hours):**
```vue
<!-- Mobile Cards with select dropdowns -->
<div class="streamer-card">
  <div class="setting-row">
    <label>Quality</label>
    <select v-model="streamer.quality">...</select>
  </div>
  
  <div class="setting-row">
    <label>Filename</label>
    <input v-model="streamer.filename" />
  </div>
</div>
```

**CSS Requirements:**
- Show/hide based on screen size (`.desktop-only`, `.mobile-only`)
- Touch-friendly: min-height 44px on all inputs
- iOS zoom prevention: 16px font-size on selects/inputs
- Checkboxes: 20-24px (not 18px)
- Cards: GlassCard with proper spacing

**Documentation:** `docs/REMAINING_FRONTEND_TASKS.md` (#NEW8)

**Testing Checklist:**
- [ ] Tables hidden on mobile (< 768px)
- [ ] Cards shown on mobile
- [ ] All checkboxes 44px touch targets
- [ ] Selects don't trigger iOS zoom (16px font)
- [ ] Layout works on 375px, 414px, 640px
- [ ] Desktop table still works (≥ 768px)

---

### 6. 🟡 Last Stream Info for Offline Streamers
**Status:** 🔴 NOT STARTED  
**Priority:** MEDIUM-HIGH (UX improvement)  
**Time:** 4-6 hours (Backend: 2-3h | Frontend: 1-2h | Testing: 1h)  
**Impact:** HIGH - Better card consistency

**Problem:**
- Offline streamers show generic "No description available"
- Cards look empty, lots of whitespace
- No context about last stream

**Desired Behavior:**
```
OFFLINE Card:
[Avatar]
[Name]
[Last Stream Title] (grayed out, opacity: 0.6)
[Last Category] (grayed out)
[VODs count] [Last streamed: 2 days ago]
```

**Backend Tasks (2-3 hours):**

1. **Model Update:** `app/models.py`
   ```python
   class Streamer(Base):
       # NEW FIELDS
       last_stream_title = Column(String, nullable=True)
       last_stream_category_name = Column(String, nullable=True)
       last_stream_viewer_count = Column(Integer, nullable=True)
       last_stream_ended_at = Column(DateTime(timezone=True), nullable=True)
   ```

2. **Migration 023:** `migrations/023_add_last_stream_info.py`
   - Add 4 columns to `streamers` table
   - Backfill from most recent ended stream per streamer
   - Safe for re-runs (column existence checks)

3. **Event Handler:** `app/events/handler_registry.py`
   - Update `handle_stream_offline()` to save last stream info
   ```python
   streamer.last_stream_title = stream.title
   streamer.last_stream_category_name = stream.category_name
   streamer.last_stream_ended_at = datetime.now(timezone.utc)
   ```

4. **API Response:** `app/routes/streamers.py`
   - Include last_stream_* fields when `is_live = False`
   - Don't send when live (avoid data bloat)

**Frontend Tasks (1-2 hours):**

1. **StreamerCard.vue:**
   ```vue
   <!-- OFFLINE with last stream info -->
   <div v-else-if="streamer.last_stream_title" class="offline-last-stream">
     <p class="stream-title offline-title">{{ streamer.last_stream_title }}</p>
     <p class="stream-category offline-category">
       {{ streamer.last_stream_category_name }}
     </p>
   </div>
   
   <style>
   .offline-title {
     color: var(--text-secondary);
     opacity: 0.7;
     font-style: italic;
   }
   </style>
   ```

**Files to Create:**
- `migrations/023_add_last_stream_info.py`

**Files to Modify:**
- `app/models.py` (Streamer model)
- `app/schemas/streamers.py` (StreamerResponse)
- `app/routes/streamers.py` (API response)
- `app/events/handler_registry.py` (handle_stream_offline)
- `app/frontend/src/components/cards/StreamerCard.vue`

**Documentation:** `docs/REMAINING_FRONTEND_TASKS.md` (#6)

**Testing Checklist:**
- [ ] Migration runs successfully
- [ ] Existing streamers backfilled with last stream data
- [ ] New stream offline events update last_stream_* fields
- [ ] API returns last stream data when offline
- [ ] Frontend displays grayed-out info
- [ ] Live streamers don't show last stream data

---

## 🟢 MEDIUM PRIORITY (Nice to Have)

### 7. 🟢 Favorite Games - Light Mode & Spacing
**Status:** ✅ ALREADY VERIFIED  
**Time:** 1-2 hours (NOT NEEDED - already correct)

**Verification:** Search input already uses `var(--background-darker)`, grid has `gap: 20px`

**File:** `app/frontend/src/components/settings/FavoritesSettingsPanel.vue`

**No action needed.**

---

### 8. 🟢 Add Streamer Modal - Minor Polish
**Status:** 🔴 NOT STARTED  
**Priority:** LOW-MEDIUM (polish items)  
**Time:** 2-3 hours  
**Impact:** MEDIUM

**Optional Improvements:**
1. Add icon to username input field (#icon-user)
2. Improve OR divider visual contrast
3. Widen callback URL container on mobile

**Files:**
- `app/frontend/src/views/AddStreamerView.vue`
- `app/frontend/src/components/AddStreamerForm.vue`
- `app/frontend/src/components/TwitchImportForm.vue`

**Note:** Current implementation already good, these are polish items

**Documentation:** `docs/REMAINING_FRONTEND_TASKS.md` (#NEW4)

---

### 9. 🟢 Settings View - 10+ Minor Issues
**Status:** 🔴 NOT STARTED  
**Priority:** LOW-MEDIUM  
**Time:** 12-20 hours total (break into smaller tasks)  
**Impact:** MEDIUM

**Issues:**
- Borders inconsistency
- Button alignment
- PWA panel styling
- Advanced tab (remove or keep?)
- About section links
- Network tab borders
- Streamer notification matrix redesign
- Per-streamer settings modal
- Animation toggle functionality
- Sidebar active state edge cases

**Recommendation:** Break into 10+ separate tasks, tackle one at a time

**Documentation:** `docs/REMAINING_FRONTEND_TASKS.md` (#5)

---

## ⏸️ DEFERRED (Low Priority / Not Urgent)

### 10. ⏸️ Streamlink Recovery on Proxy Failure
**Status:** 📝 Documented  
**Time:** 6-8 hours  
**Impact:** MEDIUM (nice to have if Multi-Proxy implemented)

**Solution:**
- Detect proxy failure mid-recording
- Switch to next proxy or direct connection
- Restart Streamlink process seamlessly
- Create new segment file
- Merge all segments at end

**Depends On:** Multi-Proxy System (Task #3)

**Documentation:** `docs/BACKEND_FEATURES_PLANNED.md` (Section 3)

---

## 📋 Recommended Execution Order

### Sprint 1: Critical Bugs & Features (6-10 hours)
**Goal:** Fix broken functionality, enable key features

1. **🔴 Fix 6 UI Bugs** (2.5-4h) - **PRIORITY 1**
   - Phase 1: Functional bugs (Test button, Clear button, Chapter duplicate, Fullscreen)
   - Phase 2: Design polish (Notifications panel, Video player)
   
2. **🔴 Multi-Proxy System** (3-4h) - **PRIORITY 2**
   - Migration 025
   - ProxyHealthService
   - ProxySettingsPanel.vue
   
3. **🔴 H.265/AV1 Codec Support** (4-6h) - **PRIORITY 3**
   - Migration 024
   - CodecSettingsPanel.vue
   - Streamlink integration

**Outcome:** All critical issues resolved, recordings stable, better quality enabled

---

### Sprint 2: Mobile UX & Enhancements (10-14 hours)
**Goal:** Perfect mobile experience

1. **🟡 Settings Tables Mobile** (6-8h)
   - NotificationSettingsPanel cards
   - RecordingSettingsPanel cards
   
2. **🟡 Last Stream Info** (4-6h)
   - Backend migration + event handler
   - Frontend StreamerCard update

**Outcome:** Mobile-friendly settings, better card consistency

---

### Sprint 3: Polish & Remaining Tasks (12-20 hours)
**Goal:** Perfect user experience

1. **🟢 Add Streamer Modal Polish** (2-3h)
2. **🟢 Settings View Minor Issues** (12-20h)
   - Break into 10+ smaller tasks
   - Tackle one per day

**Outcome:** Production-ready, polished application

---

## 📊 Progress Tracking

### Completed Tasks (34 total)

**Backend (5 tasks):**
- ✅ H.265/AV1 Codec Implementation (needs testing)
- ✅ Stream Recovery After Restart (zombie cleanup)
- ✅ Apprise Integration (4 notification points)
- ✅ Toast Notification System
- ✅ Recording Failure Detection

**Frontend (29 tasks):**
- ✅ Design System Migration (complete)
- ✅ Mobile Optimization (Session 6 - 7 tasks)
- ✅ SCSS Breakpoint Refactoring (50+ files)
- ✅ Component Polish (Session 2-5 - 20+ tasks)
- ✅ Glassmorphism Design Overhaul
- ✅ PWA Features

**Total Progress:** 34/59 (58%)

---

## 🎯 Success Metrics

### Sprint 1 Goals (Next 10 hours):
- [ ] All 6 UI bugs fixed
- [ ] Multi-Proxy system operational
- [ ] H.265/AV1 codec support enabled
- [ ] Recordings stable with proxy fallback

### Sprint 2 Goals (Next 14 hours):
- [ ] Settings tables work on mobile
- [ ] Offline streamers show last stream info
- [ ] Mobile UX perfect across all screens

### Sprint 3 Goals (Next 20 hours):
- [ ] All polish items complete
- [ ] Application production-ready
- [ ] Zero known bugs

**Overall Goal:** 59/59 tasks complete (100%) = Production deployment ready

---

## 📝 Notes

**Master Task List Maintenance:**
- Update after each completed task
- Add new tasks as discovered
- Mark completed with ✅ and commit hash
- Keep time estimates accurate based on actual work
- Reference detailed docs for implementation guides

**Documentation References:**
- Backend: `docs/BACKEND_FEATURES_PLANNED.md`
- Frontend: `docs/REMAINING_FRONTEND_TASKS.md`
- Quick Ref: `docs/QUICK_REFERENCE_REMAINING_TASKS.md`
- Known Issues: `docs/KNOWN_ISSUES_SESSION_7.md`
- Session Status: `docs/SESSION_7_STATUS.md`

**Last Review:** 12. November 2025
**Next Review:** After Sprint 1 completion
