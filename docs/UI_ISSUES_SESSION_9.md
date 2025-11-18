# UI Issues - Session 9 (November 14, 2025)

## Fixed Issues ✅

### 1. Back Button Consistency
**Problem:** VideoPlayerView had back button with `<span>Back</span>` instead of plain text  
**Fix:** Changed to match StreamerDetailView style (SVG + "Back" text inline)  
**Files:** `app/frontend/src/views/VideoPlayerView.vue`

### 2. Filter Icon Positioning
**Problem:** Filter SVG was positioned ABOVE the filter button instead of inside it  
**Fix:** Removed SVG from button (select dropdown doesn't need external icon)  
**Files:** `app/frontend/src/views/StreamerDetailView.vue`

## Remaining Issues 📋

### 3. Streams Not Displaying
**Status:** Documented in `STREAMS_DISPLAY_BUG.md`  
**Priority:** Medium  
**Details:** StreamerDetailView shows "No Streams Yet" despite 4 recordings existing in database

### 4. Notification System
**Status:** ✅ COMPLETED (Backend + Frontend)  
**Commits:** 
- Backend: 3326261c
- Frontend: d1dc8ab1

### 5. Statistics Tracking
**Status:** ✅ DOCUMENTED  
**Details:** All statistics are computed properties from streams array (Total Streams, Recorded, Avg Duration)

## Design Audit Fixes (Previous Session)

The following issues were fixed in earlier commits:

1. ✅ Back button SVG missing (StreamerDetailView)
2. ✅ Jobs button alignment on mobile
3. ✅ NotificationFeed glassmorphism redesign
4. ✅ Video player control consistency
5. ✅ Chapter panel mobile improvements
6. ✅ Settings page mobile responsiveness
7. ✅ Toast notification positioning

## Next Steps

1. Debug streams display issue (when API returns data but UI shows empty state)
2. Verify filter dropdown works without icon
3. Test back button behavior on VideoPlayerView
4. Full mobile responsive test on all views

## Session 10 Issues (November 16, 2025)

### Background
After fixing Streamlink config (commit bb19eecb) and verifying 1440p60 H.265 recording works, user performed acceptance testing and discovered 12 frontend issues.

### Critical Issues - Session 10

#### 1. JSON Parse Errors (Dev Console)
**Status:** 🔴 CRITICAL - BLOCKING  
**Priority:** 1 (Highest)  
**Problem:** 25+ errors: "SyntaxError: JSON.parse: unexpected character at line 1 column 1"  
**Impact:** May be blocking API responses, causing empty pages (login, setup)  
**Source:** index-D7nDdiKj.js:6:24720  
**Files:** app/frontend/src/router/index.ts, API client  
**Screenshot:** Screen 6 (Dev console)  

#### 2. Setup Page Infinite Reload Loop
**Status:** 🔴 CRITICAL  
**Priority:** 2  
**Problem:** URL changes to /auth/setup but page never renders, keeps reloading  
**Expected:** Setup form appears  
**Files:** Router guards, SetupView.vue  
**Screenshot:** Screen 4  

#### 3. Setup Redirects to /login Instead of /welcome
**Status:** 🔴 CRITICAL  
**Priority:** 3  
**Problem:** After account creation, redirects to /login; login page shows empty content (no form)  
**Expected:** Setup → Welcome flow, OR working login page  
**Files:** app/frontend/src/router/index.ts  
**Screenshot:** Screen 3  

#### 4. Auth Setup Design Broken
**Status:** 🔴 CRITICAL  
**Priority:** 4  
**Problem:**  
- SVG icons overlap input text  
- "Create Admin Account" button missing SVG content  
- Button invisible when not hovered  
**Files:** app/frontend/src/views/SetupView.vue  
**Design Refs:** COMPLETE_DESIGN_OVERHAUL_SUMMARY.md, frontend.instructions.md  
**Screenshot:** Screen 2  

#### 5. Notification Profile Images Wrong
**Status:** 🟡 HIGH  
**Priority:** 5  
**Problem:** Ntfy shows Apprise logo instead of Twitch avatars  
**Backend:** Generates correct URL: `icon=https://static-cdn.jtvnw.net/jtv_user_pictures/...`  
**Investigation:** Need to verify Ntfy icon parameter format  
**Files:** app/services/communication/notification_manager.py  
**Screenshot:** Screen 1  

### High Priority - Session 10

#### 6. Stream Category Timeline Missing
**Status:** 🟡 HIGH  
**Priority:** 6  
**Expected:** "14:32 - ARC Raiders, 15:45 - L4D2" with timestamps  
**Data Source:** stream_events table (category changes)  
**Files:** app/frontend/src/views/StreamerDetailView.vue, GET chapters endpoint  
**Screenshot:** Screen 7  

#### 7. Dashboard Live Streamers Cut Off (Desktop)
**Status:** 🟡 HIGH  
**Priority:** 7  
**Problem:** No horizontal scroll, streamers overflow hidden  
**Files:** app/frontend/src/views/HomeView.vue  
**Screenshot:** Screen 8  

#### 8. Dashboard Touch Behavior (Mobile)
**Status:** 🟡 HIGH  
**Priority:** 8  
**Problem:** Swipe selects streamer instead of scrolling  
**Files:** app/frontend/src/views/HomeView.vue  
**Screenshot:** Screen 8  

### Medium Priority - Session 10

#### 9. StreamerDetailView Button Overlap
**Status:** 🟢 MEDIUM  
**Priority:** 9  
**Problems:**  
- "More" button and expand-btn overlap  
- Dropdown menu floats instead of anchoring to button  
- Filter SVG icon missing  
- Gray background on filter should be removed  
**Screenshot:** Screen 7  

#### 10. Video Player Broken on Mobile
**Status:** 🟢 MEDIUM  
**Priority:** 10  
**Problem:** Player invisible or has "eckig" (blocky) design on desktop emulation  
**Files:** app/frontend/src/views/VideoPlayerView.vue, VideoPlayer.vue  
**Reference:** COMPREHENSIVE_UI_AUDIT.md  
**Screenshot:** Screen 10  

#### 11. Background Jobs Panel Cut Off (Mobile)
**Status:** 🟢 MEDIUM  
**Priority:** 11  
**Problem:** Panel disappears to right, text cut off at bottom  
**Screenshot:** Screen 11  

#### 12. Hamburger Menu Opens Wrong Side
**Status:** 🟢 MEDIUM  
**Priority:** 12  
**Problem:** Menu opens right when button is on left  
**Expected:** Opens from left (same side as button)  
**Screenshot:** Screen 12  

#### 13. Dashboard Live Count Position
**Status:** 🟢 MEDIUM  
**Priority:** 13  
**Problem:** "3" (count) positioned far right instead of next to "Live Now"  
**Note:** Mobile layout already correct  
**Files:** app/frontend/src/views/HomeView.vue  
**Screenshot:** Screen 9  

#### 14. Scroll Position Not Reset
**Status:** 🟢 MEDIUM  
**Priority:** 14  
**Problem:** Scroll stays at previous position when navigating  
**Expected:** Reset to top on route change  
**Files:** Router navigation guards  
**Screenshot:** Screen 13  

### Screenshots Reference
- Screen 1: Notification with wrong profile image  
- Screen 2: Auth Setup page design issues  
- Screen 3: Login page empty content  
- Screen 4: Setup page reload loop  
- Screen 5: (Not referenced)  
- Screen 6: Dev console JSON errors  
- Screen 7: StreamerDetailView button overlap + category timeline missing  
- Screen 8: Dashboard live streamers cut off  
- Screen 9: Dashboard live count position  
- Screen 10: Video player mobile broken  
- Screen 11: Background jobs panel cut off  
- Screen 12: Hamburger menu wrong side  
- Screen 13: Scroll position not reset  

## Session 9 Summary

**Time:** Completed before 18:00 deadline (November 14, 2025)  
**Focus:** Notification tracking system implementation + UI consistency fixes  
**Commits:** 2 (backend notification tracking + frontend integration)  
**Files Changed:** 6 frontend files, 3 backend files, 1 migration

## Session 10 Summary

**Time:** November 16, 2025  
**Focus:** Acceptance testing after Streamlink fix (1440p60 H.265 recording working!)  
**Issues Found:** 12 frontend bugs documented  
**Priority Breakdown:**  
- 🔴 Critical: 5 (JSON errors, Auth flow, Notifications)  
- 🟡 High: 3 (Category timeline, Dashboard scroll, Mobile touch)  
- 🟢 Medium: 6 (Button overlap, Video player mobile, Jobs panel, Hamburger, Live count, Scroll reset)  
**Next Steps:** Fix all 14 issues in next session, starting with JSON errors (blocks everything else)
