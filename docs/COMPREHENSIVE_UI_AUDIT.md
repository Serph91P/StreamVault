# Comprehensive UI Issues - Desktop Audit (November 14, 2025)
**Updated:** November 16, 2025 - Session 10 Testing

## 🔴 CRITICAL Issues (Fix First)

### ✅ FIXED - Session 10 (November 18, 2025)
- [x] **JSON Parse Errors (Dev Console)** - Added error handling in router guard
- [x] **Setup page infinite reload loop** - Fixed by router guard error handling
- [x] **Setup redirects to /login instead of /welcome** - Fixed redirect path
- [x] **Auth Setup page design completely broken** - Added missing SVG icons, fixed input padding
- [x] **Notification profile images show Apprise logo** - Changed ntfy parameter from 'icon=' to 'attach='

### StreamerDetailView
- [ ] **Stream category timeline missing**
  - Expected: "14:32 - ARC Raiders, 15:45 - L4D2" with timestamps
  - Should use stream_events table for category changes
  - Files: app/frontend/src/views/StreamerDetailView.vue, GET chapters endpoint
  - Priority: HIGH (metadata visibility)

- [ ] **More button and expand-btn overlap**
  - Buttons positioned on top of each other
  - Dropdown menu floats instead of anchoring to button
  - Priority: MEDIUM

- [ ] **Filter SVG icon missing again**
  - Icon was removed in previous fix
  - Gray background on filter should be removed
  - Priority: MEDIUM

- [ ] **Back button missing SVG icon** (arrow left)
- [ ] **Filter button missing SVG icon** (funnel/filter icon)
- [ ] **Statistics cards not calculating** (Total Streams, Recorded, Avg Duration show 0)
- [ ] **"Recorded" card missing icon** (should have check-circle like Total Streams has film icon)
- [ ] **"Avg Duration" card icon missing background** (clock icon needs circular background)
- [ ] **Statistics cards have top border** (inconsistent - remove borders)
- [ ] **Stream History shows "No Streams Yet"** despite database having 4 recordings

### VideoPlayerView
- [ ] **Back button has different design** than rest of site
- [ ] **Back button missing SVG icon** (arrow left)
- [ ] **Title displayed twice** (once in header, once in card below video)
- [ ] **Time display confusing** (0:00 / 1m0s under video + time in player)
- [ ] **Unnecessary card below video** showing title, duration, chapter 2, stream ID
- [ ] **Stream ID visible to user** (why does user need this?)
- [ ] **Select button far top right missing SVG icon**
- [ ] **Filter button animation inconsistent** (smooth open, no animation on close)
- [ ] **Chapter durations display incorrectly** (all show "1m" instead of actual duration)
  - Expected: Chapter 1: 0:00:00-1:33:32, Chapter 2: 1:33:32-1:33:38, Chapter 3: 1:33:38-END
  - Actual: All chapters show "1m" duration displayed sequentially
  - Works: Next Chapter button jumps to correct timestamps
  - Issue: Frontend duration calculation or API data parsing

### Header (Global)
- [ ] **Jobs button "+" not aligned** with text "Jobs"
- [ ] **Jobs button color inconsistent** ("+" and "Jobs" text different color than "0", but bell/moon icons use same white)
- [ ] **Notification badge only shows count after clicking** bell icon
- [ ] **Theme toggle has border** (moon icon) - inconsistent with bell icon

### NotificationFeed
- [ ] **Needs new design language** (glassmorphism)
- [ ] **Notification cards have blue left border** that looks like nested container
- [ ] **Double container visual** (card edges show background container behind)
- [ ] **Clear All doesn't persist** - notifications reappear with "Just now" timestamp when reopening

## 🟡 HIGH Priority Issues

### Dashboard
- [ ] **"Live Now" count positioned far right**
  - Count "3" should be next to "Live Now" headline on desktop
  - Mobile layout is already correct
  - Files: app/frontend/src/views/HomeView.vue
  - Fix: Adjust flexbox/grid layout
  - Priority: MEDIUM (visual polish)

### Search Component
- [ ] **Search input missing SVG icon** (magnifying glass before placeholder text)
- [ ] **Border radius inconsistent** (corners different roundness)

### SubscriptionsView
- [ ] **Missing SVG icons** on buttons
- [ ] **"Subscription Management" headline missing SVG icon** (has empty space before text)
- [ ] **Action buttons missing SVG icons**

### SettingsView - General
- [ ] **Multiple SVG icons missing** throughout page
- [ ] **Advanced tab has no function** (remove if not needed)
- [ ] **Scroll position not reset** when navigating between pages

### SettingsView - Recording Settings
- [ ] **Inconsistent design patterns** (multiple design systems mixed)
- [ ] **Dropdown fields inconsistent** (some rounded, some sharp corners)
- [ ] **Codec section border stops** abruptly
- [ ] **Table layout broken** - help texts overlap table headers
- [ ] **Help texts should be tooltips** instead of inline
- [ ] **No visible scroll indicator** for table
- [ ] **Buttons at table end suddenly blue** (inconsistent color)

### SettingsView - Storage Tab
- [ ] **4 nested borders visible** (too many container layers)
- [ ] **Dropdowns now rounded** (inconsistent with other pages)
- [ ] **2 Save buttons present** (duplicate)
- [ ] **Category list has mixed colors** with strange borders

### SettingsView - Proxy Page
- [ ] **Top element has red left border** (inconsistent)
- [ ] **"Add Proxy" button too large**
- [ ] **Cards touch each other** - overlap on hover
- [ ] **Proxy card has red left border** (inconsistent)
- [ ] **Test Now / Priority / Delete buttons too large** (not using SCSS button system)
- [ ] **Save button at top of card** instead of bottom (UX issue - read before save)

### SettingsView - Favorite Games
- [ ] **Title missing SVG icon**
- ✅ Otherwise looks good

### SettingsView - Appearance
- [ ] **Missing SVG icons** on buttons and inputs
- [ ] **Button styles inconsistent** (Supported indicator, toggles all look different)
- [ ] **Dark mode toggle becomes invisible** when disabled (can't see it exists)
- [ ] **Animation toggle has no function** (implement or remove)
- [ ] **Question: Is this page needed?**

### SettingsView - Advanced
- [ ] **Debug toggle doesn't work**
- [ ] **"Enable Animations" duplicated** (already in Appearance tab)
- [ ] **"Clear Cache" function unclear** (what does it do?)
- [ ] **Question: Is this tab needed?**

### SettingsView - PWA
- [ ] **Missing SVG icons**
- ✅ Otherwise generally good

### SettingsView - About
- ✅ Looks okay

## 🟢 DESIGN CONSISTENCY Issues

### Cards
- [ ] **Streamer stats cards have top border** - no other cards on site use this
- [ ] **Inconsistent border usage** across different views
- [ ] **Red borders on some cards** (proxy settings) vs no borders elsewhere

### Buttons
- [ ] **Hover states inconsistent** (red on red background on streamer page?)
- [ ] **Button transparency unclear** on hover
- [ ] **Large buttons not using SCSS design system** (proxy page, recording settings)
- [ ] **Jobs button hover different** from bell icon hover

### Backgrounds
- [ ] **Stream History has circle pattern background** (inconsistent)
- [ ] **Background patterns not used elsewhere**

### Icons/SVG
- [ ] **Missing icons documented above** (~20+ locations)
- [ ] **Icon alignment issues** (Jobs button "+" vs text)
- [ ] **Icon backgrounds inconsistent** (some have circular bg, some don't)

## 📱 MOBILE Issues (To Test After Desktop Fixed)

### Video Player Mobile (CRITICAL)
- [ ] **Video player completely broken on mobile devices**
  - Player invisible or has "eckig" (blocky) design
  - Controls may be cut off or inaccessible
  - Files: app/frontend/src/views/VideoPlayerView.vue, VideoPlayer.vue
  - Reference: COMPREHENSIVE_UI_AUDIT.md
  - Priority: CRITICAL (mobile users completely blocked)

### Dashboard Mobile (HIGH)
- [ ] **Live streamers cut off on desktop (no scroll)**
  - Horizontal scroll mechanism missing
  - Streamers overflow hidden
  - Priority: HIGH

- [ ] **Live streamers weird touch behavior on mobile**
  - Swipe selects streamer instead of scrolling
  - Touch events incorrectly trigger navigation
  - Files: app/frontend/src/views/HomeView.vue
  - Priority: HIGH

### Background Jobs Panel (MEDIUM)
- [ ] **Background Jobs panel cut off on mobile**
  - Panel disappears to the right
  - Text cut off at bottom
  - Priority: MEDIUM

### Navigation (MEDIUM)
- [ ] **Hamburger menu opens on right when button is on left**
  - Menu should slide from left (same side as button)
  - Current behavior confusing
  - Priority: MEDIUM

- [ ] **Scroll position not reset on navigation**
  - When navigating between pages, scroll stays at previous position
  - Should reset to top on route change
  - Files: Router navigation guards
  - Priority: MEDIUM

### General Mobile
- [ ] Full mobile responsive audit needed
- [ ] Touch target sizes
- [ ] Mobile navigation

## ✅ COMPLETED (Session 9)
- ✅ Backend notification tracking with DB persistence (Commit 3326261c)
- ✅ Frontend notification API integration (Commit d1dc8ab1)
- ✅ VideoPlayerView back button text format fixed (removed `<span>`)
- ✅ StreamerDetailView filter button SVG removed (was overlapping)

## 🎯 Recommended Fix Order

### Phase 1: Critical Functionality (NOW)
1. Fix notification persistence (Clear All + badge count)
2. Fix streams not displaying in StreamerDetailView
3. Fix statistics calculation (Total Streams, Recorded, Avg Duration)

### Phase 2: Missing Icons (Quick Wins)
4. Add all missing SVG icons systematically
5. Fix icon alignment issues (Jobs button)
6. Add icon backgrounds where needed (Avg Duration clock)

### Phase 3: Design Consistency
7. Remove inconsistent borders (stats cards, proxy cards)
8. Standardize button styles (use SCSS system)
9. Fix button hover states
10. Standardize dropdown/input field styles

### Phase 4: Layout Issues
11. Fix VideoPlayerView duplicate title/info
12. Fix SettingsView table layouts
13. Fix scroll position reset on navigation
14. Optimize card spacing (proxy page overlap)

### Phase 5: Settings Cleanup
15. Remove/implement Advanced tab features
16. Remove duplicate functions (animations toggle)
17. Implement missing toggle functions
18. Add tooltips for help texts

### Phase 6: Mobile Audit
19. Full mobile responsive test
20. Touch target optimization
21. Mobile-specific layout fixes

## Notes
- **User confirmed:** All changes are pulled (current state is correct)
- **Screen 1 & 2:** Caching issue - ignored
- **Deadline:** Completed before 18:00 (notification system)
- **Priority:** Fix critical issues before design consistency
- **Testing:** Desktop first, then mobile

## Questions for User
1. Is Advanced tab needed at all?
2. Is Appearance page needed?
3. What should "Clear Cache" do?
4. Should Stream ID be hidden from users?
5. Should VideoPlayerView info card be removed entirely?
