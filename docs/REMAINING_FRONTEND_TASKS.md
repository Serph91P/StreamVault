# Remaining Frontend Tasks - Continuation Guide
**Date:** 11. November 2025 (Updated - Session 6 Extended + SCSS Refactoring)  
**Status:** ✅ Outstanding Progress - 34/59 Issues Fixed (58%)  
**Session:** Day 6 Extended - Mobile Final Optimizations + Critical SCSS Refactoring Complete

## 🎯 CRITICAL MILESTONE: SCSS Breakpoint System Migration ✅

**Commit:** 12d23ab7 (11. Nov 2025)  
**Impact:** ALL 50+ Vue components now use centralized SCSS breakpoint system  
**Status:** ✅ **PRODUCTION READY** - Best Practice Implemented

### What Changed
- ❌ **REMOVED:** Hard-coded `@media (max-width: XXXpx)` from ALL Vue files
- ✅ **IMPLEMENTED:** Centralized SCSS mixin system (`@include m.respond-below()`)
- ✅ **ADDED:** New `'sm': 640px` breakpoint to system
- ✅ **DOCUMENTED:** MANDATORY usage in `frontend.instructions.md`

### Breakpoint System (NEW)
```scss
// app/frontend/src/styles/_variables.scss
$breakpoints: (
  'xs': 375px,   // Mobile extra-small (iPhone SE)
  'sm': 640px,   // Mobile / Phablet (NEW!)
  'md': 768px,   // Tablet portrait
  'lg': 1024px,  // Desktop / Tablet landscape
  'xl': 1200px   // Large desktop
);
```

### Usage Pattern (MANDATORY)
```scss
// ✅ CORRECT - ALWAYS use this pattern
@use '@/styles/mixins' as m;

@include m.respond-below('sm') {  // < 640px
  .component { padding: 8px; }
}

// ❌ FORBIDDEN - NEVER do this
@media (max-width: 640px) {
  .component { padding: 8px; }
}
```

### Files Refactored (50+)
**Views:** HomeView, VideosView, StreamersView, StreamerDetailView, VideoPlayerView, SettingsView, LoginView, SetupView, WelcomeView, SubscriptionsView, AddStreamerView, PWATester

**Components:** AdminPanel, PostProcessingManagement, VideoPlayer, VideoCard, StreamerCard, StatusCard, RecordingSettingsPanel, NotificationSettingsPanel, FavoritesSettingsPanel, PWAPanel, VideoModal, NotificationFeed, BackgroundQueueMonitor, CleanupPolicyEditor, ToastNotification, + 25 more

### Documentation Added
**File:** `.github/instructions/frontend.instructions.md`  
**Section:** "SCSS Breakpoints & Responsive Design (CRITICAL)"

**Key Rules:**
1. ⚠️ **FORBIDDEN:** `@media (max-width: XXXpx)` in Vue components
2. ✅ **REQUIRED:** `@use '@/styles/mixins' as m;` at top of `<style>`
3. ✅ **REQUIRED:** `@include m.respond-below('breakpoint')` for responsive
4. ✅ **REQUIRED:** Comment explaining viewport size (e.g., `// < 640px`)
5. 📝 **PRE-COMMIT:** Check for hard-coded breakpoints in diff

### Build Verification
```
✓ 164 modules transformed
✓ built in 3.30s
Bundle: 3188.15 KiB
Errors: 0 ✅
Warnings: 0 ✅
```

---

## ✅ Completed Today (Session 6 Extended - 11. Nov 2025)

### Issue #NEW14: StreamerDetailView Mobile Optimization ✅
**Status:** COMPLETED  
**Commit:** ee220ac6  
**Changes:**
- Action buttons: 44px min-height for touch targets
- View toggle: 44x44px buttons with 22px icons
- Sort select: 44px height, 16px font prevents iOS zoom
- Stats cards: Stack vertically on mobile (single column)
- Modal actions: Stack vertically on extra-small screens (< 375px)
- Profile avatar: Scales down 96px on mobile
- Enhanced spacing and gaps for better mobile UX
**File:** `app/frontend/src/views/StreamerDetailView.vue`

### Issue #NEW15: HomeView Empty State Enhancement ✅
**Status:** COMPLETED  
**Commit:** 9b49a001  
**Changes:**
- Conditional empty state logic:
  - No streamers → "Welcome to StreamVault" with "Add Your First Streamer" CTA
  - Streamers exist but none live → "No Live Streams" with helpful message
- Better user onboarding and guidance
- Improved first-time user experience
**File:** `app/frontend/src/views/HomeView.vue`

### Issue #NEW16: Settings View Mobile Tabs ✅
**Status:** COMPLETED  
**Commit:** e65c42f9  
**Changes:**
- Horizontal scroll tabs with scroll-snap for smooth scrolling
- Nav items: 44px min-height (touch-friendly)
- Active item: Scale effect (1.02) + shadow for visual feedback
- Inputs/selects: 44px height, 16px font (iOS zoom prevention)
- About links: Full-width 48px on mobile
- Proper gap and padding optimization
**File:** `app/frontend/src/views/SettingsView.vue`

### Issue #NEW17: Video Player Mobile Controls ✅
**Status:** COMPLETED  
**Commit:** a9266abd  
**Changes:**
- Back button: 44px min-height with larger 18px icon
- Progressive padding reduction: md (768px) → sm (640px) → xs (375px)
- Content states: Optimized min-height (300px → 250px → smaller)
- Landscape mode: 40px button height for compact orientation
- Proper breakpoint cascade for smooth transitions
**File:** `app/frontend/src/views/VideoPlayerView.vue`

### Issue #NEW18: SCSS Breakpoint Migration ✅ (CRITICAL)
**Status:** PRODUCTION READY  
**Commit:** 12d23ab7  
**Impact:** **ENTIRE PROJECT** - 50+ files refactored  
**Changes:**
- Migrated ALL hard-coded `@media` queries to SCSS mixins
- Added `lang="scss"` to 40+ components
- Fixed `@use` import order in all files
- Removed 24 duplicate `@use` statements
- Handled special cases (landscape orientation, import placement)
- Created comprehensive documentation with migration guide
**Benefits:**
1. Single source of truth for breakpoints
2. Consistent responsive behavior across all components
3. Easy maintenance (change once, apply everywhere)
4. Type-safe breakpoint names
5. Better developer experience

---

## ✅ Completed in Previous Sessions (Session 6 Initial)

### Issue #NEW10: PWA Panel Button Styling ✅
**Status:** VERIFIED - Enhanced button consistency  
**Commit:** 8a51f13f  
**Changes:**
- Removed inline style `style="margin-left: 8px;"` → `.btn-spacing` class
- Icon size: 16px → 18px
- Added `min-height: 40px` for touch-friendly targets
- Enhanced hover states with translateY + box-shadow
**File:** `app/frontend/src/components/settings/PWAPanel.vue`

### Issue #NEW11: Sidebar Active State Consistency ✅
**Problem:** Active state lacked visual depth and consistency across themes  
**Solution:** Enhanced with inset box-shadow and improved hover states  
**Commit:** e312221e  
**Changes:**
- Added inset box-shadow for depth (left border effect)
- Dark mode: White semi-transparent inset shadow
- Light mode: Primary-700 solid inset shadow
- Active+hover: Lighter background (primary-400 dark, primary-500 light)
- Improved visual hierarchy
**File:** `app/frontend/src/components/navigation/SidebarNav.vue`

### Issue #NEW12: VideosView Filters Mobile Optimization ✅
**Problem:** Filter controls not optimized for mobile touch interaction  
**Solution:** Comprehensive mobile breakpoint with touch-friendly controls  
**Commit:** 0f54f08e  
**Changes:**
- Filter/sort buttons: min-height 44px (touch-friendly)
- Filter selects: 16px font-size (prevents iOS zoom)
- Clear filters button: full-width, centered, 44px height
- Search box reordered to top on mobile (order: -1)
- Filter panel: vertical stack layout with proper spacing
- Filter groups: full-width with enhanced label styling
- Removed duplicate mobile breakpoint section
**Mobile Optimization:**
- ✅ All touch targets >= 44px
- ✅ iOS zoom prevention (16px font-size on selects)
- ✅ Column stack layout for filters
- ✅ Consistent spacing via design tokens
**File:** `app/frontend/src/views/VideosView.vue`

### Issue #NEW13: StreamersView Controls Mobile Optimization ✅
**Problem:** Search, filter tabs, view toggle not optimized for mobile  
**Solution:** Touch-friendly controls with proper sizing and spacing  
**Commit:** eef27862  
**Changes:**
- Search input: 44px min-height, 16px font-size
- Clear button: 32px x 32px with 18px icon
- Filter tabs: 40px min-height, optimized padding
- View toggle buttons: 44px x 44px, 22px icons
- Sort select: 44px min-height, 16px font-size
- Auto ON/OFF toggle: 44px min-height
- Tablet breakpoint (1024px): Search top, full-width
- Mobile breakpoint (640px): Touch-optimized controls
**Mobile Optimization:**
- ✅ All interactive elements >= 40px (44px preferred)
- ✅ iOS zoom prevention on all inputs/selects
- ✅ Larger icons (18-22px) for visibility
- ✅ Optimized spacing, compact filter tabs
**File:** `app/frontend/src/views/StreamersView.vue`

---

## ✅ Completed in Session 5 (Previous)

### Video Cards Mobile Responsive ✅
### Settings Glassmorphism Enhancement ✅
### Animation Toggle Feature ✅
### About Page External Links ✅
### Welcome Page Improvements ✅

---

## ✅ Completed in Session 4 (11. Nov 2025)

### Issue #NEW9: Last Stream Info for Offline Streamers ✅
**Problem:** Offline streamers show generic "No description available" without context  
**Solution:** Full-stack implementation to display last stream info when offline  
**Implementation:**

**Backend (Commit: 54191f60):**
- ✅ Added 4 fields to Streamer model: last_stream_title, last_stream_category_name, last_stream_viewer_count, last_stream_ended_at
- ✅ Created migration 023 with backfill from most recent ended streams
- ✅ Updated StreamerResponse schema with new fields
- ✅ Updated /api/streamers endpoint to include last stream info when offline
- ✅ Updated handle_stream_offline event to save last stream info

**Frontend (Commit: b9dc50e6):**
- ✅ Extended Streamer interface with last_stream_* fields
- ✅ Display last stream title + category when offline (grayed out, opacity: 0.6)
- ✅ Updated lastStreamTime to use last_stream_ended_at
- ✅ Added CSS styling for offline-last-stream section
- ✅ Maintains card layout consistency

**UI Behavior:**
- Live: "Stream Title" + "Category" (full color)
- Offline with data: "Last Stream Title" + "Last Category" (grayed out) + "3h ago"
- Offline without data: Streamer description

**Files:**
- Backend: models.py, schemas/streamers.py, routes/streamers.py, events/handler_registry.py, migrations/023_add_last_stream_info.py
- Frontend: components/cards/StreamerCard.vue

---

## ✅ Completed Today (Session 3 - 11. Nov 2025)

### Issue #NEW7: Favorite Games - Light Mode & Spacing ✅
**Status:** VERIFIED - Already correctly implemented  
**Findings:**
- ✅ Search input uses `var(--background-darker)` (line 641)
- ✅ Category grid has `gap: 20px` with responsive values (16px/20px/24px)
- ✅ Works perfectly in both light and dark themes
**File:** `app/frontend/src/components/settings/FavoritesSettingsPanel.vue`  
**Action:** No changes needed

### Issue #NEW8: Settings Tables Mobile Responsive ✅
**Problem:** Notification and Recording settings tables use horizontal scroll on mobile  
**Solution:** Transform tables to vertical card layout on mobile (< 768px)  
**Implementation:**
- ✅ NotificationSettingsPanel: Enhanced mobile card layout with 44px touch targets, 20px checkboxes
- ✅ RecordingSettingsPanel: Added data-label attributes + mobile card layout
- Optimized select dropdowns and text inputs for mobile (16px font to prevent iOS zoom)
- Stack action buttons vertically on mobile
- Card styling with shadows, borders, distinct backgrounds
- Vertical label centering with transform
- Extra small screen optimizations (< 480px)
**Files:**  
- `app/frontend/src/components/settings/NotificationSettingsPanel.vue`
- `app/frontend/src/components/settings/RecordingSettingsPanel.vue`
**Commit:** 71fbb59b

---

## ✅ Completed Today (Session 2 - 11. Nov 2025)

### Issue #8: Design System Colors - SidebarNav ✅
**Problem:** Hardcoded teal colors in SidebarNav.vue broke design consistency  
**Solution:** Replaced with CSS variables `var(--primary-color)`, `var(--primary-600)`  
**File:** `app/frontend/src/components/navigation/SidebarNav.vue`  
**Commit:** 61f16b68

### Issue #3: Light Mode Button Visibility - Verification ✅
**Status:** Already correct - buttons use CSS variables throughout  
**Action:** Documented button color patterns with clarity comments  
**File:** Various components  
**Commit:** 0101d9a8

### Issue #9: Add Missing Icons - SVG Sprite ✅
**Problem:** Icons referenced in code but not displaying (not loaded correctly)  
**Solution:** Embedded ALL 28 icons inline in App.vue <template> for guaranteed loading  
**Icons Added:** circle, film, arrow-right, video-off, plus, trash, refresh, edit, check, x, download, gamepad, menu, log-out, clock, more-vertical, play, eye  
**Files:**  
- `app/frontend/src/App.vue` (inline SVG sprite with <defs>)
- `app/frontend/index.html` (removed fetch() script)  
**Commits:** 80610ffe (initial), 777f7451 (inline fix)

### Issue #11: Recording Animation - Grid View ✅
**Problem:** Static red border on recording cards, no pulsing animation  
**Solution:** Added pulse-recording & pulse-border animations to StreamerCard  
**File:** `app/frontend/src/components/cards/StreamerCard.vue`  
**Commit:** dca57696

### Issue #NEW1: Login & Setup Pages - Icons & Styling ✅
**Problem:** Icons not displaying despite being added to icons.svg  
**Solution:** Embedded all 41 icons inline in App.vue <template> for guaranteed loading  
**Files:** `app/frontend/src/App.vue`, `app/frontend/src/views/WelcomeView.vue`  
**Commit:** d597e451

### Issue #NEW2: HomeView Mobile Layout ✅
**Problem:** Live cards left-aligned, red border overwhelming, shadow clipping  
**Solution:** Centered live cards on mobile, removed red border from card (kept on avatar), increased padding  
**Files:** `app/frontend/src/views/HomeView.vue`, `app/frontend/src/components/cards/StreamerCard.vue`  
**Commit:** 65c53ef2

### Issue #NEW3 & #5: Mobile Header & Hamburger Menu - VERIFIED ✅
**Status:** Already correctly implemented - no changes needed  
**Verification:** ThemeToggle (44x44px), BackgroundQueueMonitor (mobile styles), notification handlers, hamburger menu with slideInRight  
**Components:** `ThemeToggle.vue`, `BackgroundQueueMonitor.vue`, `App.vue`

### Issue #NEW6: StreamerDetailView Settings Modal ✅
**Problem:** Settings button non-functional, icon size inconsistency, button text wrapping on mobile  
**Solution:** Added per-streamer settings modal, icon-only buttons < 480px, verified StatusCard icons already correct  
**File:** `app/frontend/src/views/StreamerDetailView.vue`  
**Commit:** b8e45f17

### Issue #12-15: Button Icons - VERIFIED ✅
**Status:** All icons already present in StreamersView, VideosView, SubscriptionsView  
**Findings:**
- ✅ StreamersView: Auto ON (#icon-refresh-cw), Search (#icon-search), Grid/List toggles
- ✅ VideosView: Cancel/Select (#icon-check-square), Filters (#icon-filter), Grid/List toggles
- ✅ SubscriptionsView: Refresh (#icon-refresh-cw), Resubscribe (#icon-repeat), Delete (#icon-trash-2)
**Action:** Task descriptions were outdated - icons already implemented correctly

---

## ✅ Completed Today (Session 1)

### Issue #1: View Details Navigation ✅
**Problem:** Route mismatch - empty page when clicking "View Details"  
**Solution:** Changed route from `/streamer/:id` to `/streamers/:id` (plural)  
**File:** `app/frontend/src/router/index.ts`  
**Commit:** 2bcbab92

### Issue #7: Scroll-to-Top on Navigation ✅
**Problem:** Scroll position remembered across page changes  
**Solution:** Added `scrollBehavior` to router config  
**File:** `app/frontend/src/router/index.ts`  
**Commit:** 2bcbab92

### Issue #4: Streamer Card Vertical Layout ✅
**Problem:** Long names truncated, horizontal layout cramped  
**Solution:** Complete vertical redesign with centered avatar, name (2 lines), stats at bottom  
**File:** `app/frontend/src/components/cards/StreamerCard.vue`  
**Commit:** 2bcbab92

### Issue #4b: Live Card Readability ✅
**Problem:** Red gradient made text unreadable, category appeared twice  
**Solution:** Removed gradient, added subtle red border, reorganized layout, title 3 lines  
**File:** `app/frontend/src/components/cards/StreamerCard.vue`  
**Commit:** a24d3d68

### Issue #2: Bottom Nav Fixed Position ✅
**Status:** CSS already correct (`position: fixed`), likely browser cache issue  
**Action:** User needs to hard refresh browser (Ctrl+F5)

---

## 🔴 HIGH PRIORITY - Start Here Tomorrow

### Issue #5: Mobile Hamburger Menu (CRITICAL)
**Status:** ✅ ALREADY IMPLEMENTED  
**Priority:** HIGH - Blocks mobile usability  
**Estimated Time:** 3-4 hours

**VERIFICATION:** Mobile menu already fully implemented in App.vue!

**Current Implementation:**
- ✅ Hamburger button visible only on mobile (< 768px)
- ✅ Slide-in menu from right with overlay
- ✅ Contains: Notifications, ThemeToggle, Logout
- ✅ Click outside to close
- ✅ Smooth animations
- ✅ Desktop shows full nav in header (≥ 768px)

**File:** `app/frontend/src/App.vue`  
**No changes needed - this was already done!**

---

### Issue #8: Design System Colors (CRITICAL)
**Status:** ✅ ALREADY FIXED  
**Priority:** HIGH - Breaks design consistency  
**Estimated Time:** 1-2 hours

**VERIFICATION:** SidebarNav.vue already uses CSS variables!

**Current Implementation:**
```scss
&.active {
  background: var(--primary-color);
  color: white;
  
  // Light mode: Uses CSS variable instead of hardcoded
  [data-theme="light"] & {
    background: var(--primary-color-dark);  // ✅ Uses CSS variable
    color: white;
    border-left: 4px solid v.$primary-700;  // ✅ Uses SCSS variable
  }
}
```

**File:** `app/frontend/src/components/navigation/SidebarNav.vue` (lines 160-179)  
**Commit:** 61f16b68  
**No additional changes needed!**

**Solution:**

**Step 1: Check Design System Variables**
File: `app/frontend/src/styles/_variables.scss`
```scss
// Find the correct CSS variable names
$primary-500: #14b8a6;  // Teal
$primary-600: #0d9488;  // Darker teal

// Check if there are contrast-safe variants
$primary-500-safe: ...; // For light mode
```

**Step 2: Update SidebarNav.vue**
File: `app/frontend/src/components/navigation/SidebarNav.vue`

```scss
&.active {
  background: var(--primary-500);
  color: white;
  
  // FIXED: Use CSS variables with proper light mode override
  [data-theme="light"] & {
    // Option A: Use darker primary for contrast
    background: var(--primary-600);
    color: white;
    border-left: 4px solid var(--primary-700);
    
    // Option B: Use inverted primary (if available)
    background: var(--primary-contrast);
    color: var(--primary-contrast-text);
  }
  
  .nav-icon {
    stroke: white;
  }
}
```

**Step 3: Verify in Both Themes**
- Dark mode: Active item clearly visible
- Light mode: Active item has sufficient contrast (4.5:1 ratio)
- Test with browser dev tools → Emulate vision deficiencies

**Files to Modify:**
- `app/frontend/src/components/navigation/SidebarNav.vue` (lines 168-179)
- Possibly: `app/frontend/src/styles/_variables.scss` (if variables missing)

**Reference:**
- Commit with hardcoded colors: 8a4cc414
- Design system doc: `docs/COMPLETE_DESIGN_OVERHAUL_SUMMARY.md`

---

### Issue #3: Light Mode Button Visibility (HIGH)
**Status:** ✅ ALREADY FIXED  
**Priority:** HIGH - Usability issue  
**Estimated Time:** 2-3 hours

**VERIFICATION:** All buttons already use CSS variables!

**Settings Components Checked:**
- ✅ `RecordingSettingsPanel.vue` - All buttons use `var(--primary-color)`, `var(--danger-color)`, etc.
- ✅ `NotificationSettingsPanel.vue` - All colors use CSS variables with fallbacks
- ✅ `PWAPanel.vue` - Buttons use `btn-primary`, `btn-secondary` classes
- ✅ `FavoritesSettingsPanel.vue` - Search input uses `var(--background-card)`

**Button Classes:**
```scss
.btn-primary { background-color: var(--primary-color); color: white; }
.btn-secondary { background-color: var(--background-darker); color: white; }
.btn-danger { background-color: var(--danger-color); color: white; }
.btn-warning { background-color: var(--warning-color); color: #212529; }
.btn-info { background-color: var(--info-color); color: white; }
```

**Commits:** 61f16b68, 0101d9a8  
**No additional changes needed!**

---

### Issue #NEW1: Login & Setup Pages - Missing Icons & Button Styling (CRITICAL)
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH - First impression issues  
**Estimated Time:** 2-3 hours

**Problems:**

**1. Login Page (LoginView.vue)**
- Missing icons on login form (user icon, lock icon)
- Login button has no styling (looks like plain text)
- Light mode: Insufficient contrast on input fields

**2. Setup Page (SetupView.vue)**  
- Missing icons (same as login page)
- Setup wizard steps lack visual indicators
- Buttons inconsistent with design system

**3. Welcome Page (WelcomeView.vue)**
- "Go to Dashboard" button redirects to `/home` instead of `/`
- Missing icons on feature cards
- Button styling inconsistent

**Files to Fix:**
```
app/frontend/src/views/LoginView.vue
app/frontend/src/views/SetupView.vue
app/frontend/src/views/WelcomeView.vue
```

**Required Icons:**
- `icon-user` (username input)
- `icon-lock` (password input)
- `icon-check-circle` (success states)
- `icon-alert-circle` (error states)

**Button Fixes:**
```scss
.login-btn, .setup-btn, .dashboard-btn {
  // Use design system button styles
  background: var(--primary-color);
  color: white;
  padding: var(--spacing-3) var(--spacing-6);
  border-radius: var(--radius-lg);
  font-weight: 600;
  
  &:hover {
    background: var(--primary-600);
    transform: translateY(-2px);
  }
}
```

**Route Fix:**
```typescript
// WelcomeView.vue
const goToDashboard = () => {
  router.push('/') // FIXED: Was '/home'
}
```

---

### Issue #NEW2: Home View Mobile - Layout & Alignment Issues (HIGH)
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH - Mobile user experience  
**Estimated Time:** 2-3 hours

**Problems:**

**1. Live Now Section - Cards Left-Aligned**
- Live streamer cards are left-aligned instead of centered
- Looks unbalanced on mobile (< 640px)
- **Solution:** Center cards in container

**2. Live Card - Red Border Too Prominent**
- Outer red border on entire card is overwhelming
- **Better:** Only profile image should have red border
- Keep pulsing effect for recording indicator

**3. Quick Stats - Video Icon Width Issue**
- Video stat card background is wider than others
- Icons inconsistent sizes
- **Solution:** Standardize icon container width

**4. Live Card Shadow Clipping**
- Box shadow on live streamer card is cut off
- Parent container has `overflow: hidden`
- **Solution:** Add padding or remove overflow constraint

**5. Recent Recordings Background**
- Confusing background image/pattern
- **Question:** What is this supposed to be?
- **Solution:** Remove or replace with subtle gradient

**Files to Fix:**
```
app/frontend/src/views/HomeView.vue
app/frontend/src/components/cards/StreamerCard.vue
app/frontend/src/components/cards/StatusCard.vue
```

**CSS Fixes:**

```scss
// HomeView.vue - Center live cards on mobile
.live-streamers-grid {
  @media (max-width: 640px) {
    justify-content: center; // ADDED
  }
}

// StreamerCard.vue - Subtle border on profile only
.streamer-card.is-live {
  :deep(.glass-card-content) {
    border: none; // REMOVED: 2px solid var(--danger-color)
  }
  
  .streamer-avatar {
    border: 3px solid var(--danger-color); // KEEP THIS
    box-shadow: 0 0 0 4px rgba(var(--danger-color-rgb), 0.2);
  }
}

// StatusCard.vue - Standardize icon sizes
.status-icon {
  width: 48px;  // FIXED: Was inconsistent
  height: 48px;
  
  .icon {
    width: 24px;  // FIXED: Was 24-28px
    height: 24px;
  }
}

// Remove or explain recent recordings background
.recent-recordings-section {
  background: none; // REMOVED: background-image
  // OR
  background: linear-gradient(135deg, 
    rgba(var(--primary-500-rgb), 0.05) 0%,
    rgba(var(--accent-500-rgb), 0.05) 100%
  );
}
```

---

### Issue #NEW3: Mobile Header - Jobs Window & Hamburger Menu UX (CRITICAL)
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH - Unusable on mobile  
**Estimated Time:** 3-4 hours

**Problems:**

**1. Jobs Window Off-Center**
- Background queue monitor (JOBS 0) is shifted off-screen
- Unreadable on mobile
- **Solution:** Reposition or make responsive

**2. Hamburger Menu Confusion**
- Button is on LEFT side of header
- Menu slides in from RIGHT side
- **Expected:** Button and menu on same side
- **Solution:** Move button to right OR slide menu from left

**3. Notifications Button (Mobile)**
- Button visible but does nothing when clicked
- No dropdown/panel appears
- **Solution:** Make notification panel work on mobile

**4. Theme Toggle - Hit Area Too Small**
- Button same size as notification button
- Only icon + border respond to clicks
- Background doesn't respond
- **Solution:** Increase clickable area

**Files to Fix:**
```
app/frontend/src/App.vue (header)
app/frontend/src/components/BackgroundQueueMonitor.vue
app/frontend/src/components/ThemeToggle.vue
```

**Mobile Header Fixes:**

```vue
<!-- App.vue - Better mobile layout -->
<header class="app-header">
  <!-- Mobile: Hamburger on RIGHT (matches menu slide) -->
  <router-link to="/" class="app-logo">StreamVault</router-link>
  
  <div class="header-right">
    <!-- Jobs monitor - HIDE on mobile or make compact -->
    <BackgroundQueueMonitor class="desktop-only" />
    
    <!-- Mobile controls -->
    <button @click="toggleNotifications" class="mobile-notification-btn">
      <svg><use href="#icon-bell" /></svg>
      <span v-if="unreadCount" class="badge">{{ unreadCount }}</span>
    </button>
    
    <button @click="toggleMobileMenu" class="hamburger-btn">
      <svg><use href="#icon-menu" /></svg>
    </button>
  </div>
</header>

<!-- Mobile menu slides from RIGHT (matches button) -->
<div v-if="showMobileMenu" class="mobile-menu" :class="{ 'slide-right': true }">
  <ThemeToggle /> <!-- Full-width button -->
  <NotificationPanel v-if="showNotifications" /> <!-- Mobile-friendly -->
  <BackgroundQueueMonitor /> <!-- Compact view -->
  <button @click="logout" class="logout-btn-mobile">Logout</button>
</div>
```

**Theme Toggle Fix:**
```scss
// ThemeToggle.vue
.theme-toggle {
  min-width: 44px;  // Touch target
  min-height: 44px;
  padding: var(--spacing-2);
  
  // ENTIRE button clickable
  cursor: pointer;
  background: transparent;
  
  &:hover {
    background: rgba(var(--primary-500-rgb), 0.1);
  }
}
```

**Jobs Window Responsive:**
```scss
// BackgroundQueueMonitor.vue
@media (max-width: 768px) {
  .queue-monitor {
    // Option 1: Hide and show in mobile menu
    display: none;
    
    // Option 2: Compact badge
    .queue-count {
      font-size: var(--text-xs);
      padding: 2px 6px;
    }
    
    .queue-label {
      display: none; // Hide "JOBS" text
    }
  }
}
```

---

### Issue #NEW4: Add Streamer View - Light Mode & Layout Issues (HIGH)
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH - Broken UX  
**Estimated Time:** 2-3 hours

**Problems:**

**1. Light Mode Design Mismatch**
- Input fields have poor contrast
- Buttons not styled correctly
- Card backgrounds don't use design system

**2. Twitch Import Section - Text Too Narrow**
- Callback URL text is cramped
- Hard to read, poor UX
- **Solution:** Wider container or scrollable

**3. "OR" Divider Unreadable**
- Separator between manual/import is invisible
- Lost in background design
- **Solution:** Higher contrast, better styling

**4. Mobile Layout Issues**
- Cards overlap
- Buttons too small for touch
- Form inputs cramped

**Files to Fix:**
```
app/frontend/src/views/AddStreamerView.vue
```

**Design Fixes:**

```vue
<!-- AddStreamerView.vue -->
<template>
  <div class="add-streamer-view">
    <!-- Manual Add Card -->
    <GlassCard variant="medium" class="add-card">
      <h3>Add by Username</h3>
      <input 
        type="text" 
        v-model="username"
        placeholder="Enter Twitch username"
        class="streamer-input"
      />
      <button @click="checkUsername" class="btn-primary">
        <svg><use href="#icon-search" /></svg>
        Check
      </button>
      <button @click="addStreamer" class="btn-success">
        <svg><use href="#icon-plus" /></svg>
        Add Streamer
      </button>
    </GlassCard>
    
    <!-- OR Divider - IMPROVED -->
    <div class="divider-container">
      <div class="divider-line"></div>
      <span class="divider-text">OR</span>
      <div class="divider-line"></div>
    </div>
    
    <!-- Twitch Import Card -->
    <GlassCard variant="medium" class="import-card">
      <h3>
        <svg><use href="#icon-download" /></svg>
        Import from Twitch
      </h3>
      <p class="import-description">
        Import streamers you already follow on your Twitch account
      </p>
      
      <!-- WIDER callback URL container -->
      <div class="callback-info">
        <p><strong>Before connecting, configure your Twitch Developer Dashboard:</strong></p>
        <div class="callback-url">
          <label>Callback URL format:</label>
          <code class="url-code">https://your-streamvault-domain.com/api/twitch/callback</code>
          <button @click="copyCallback" class="btn-copy">
            <svg><use href="#icon-copy" /></svg>
            Copy
          </button>
        </div>
      </div>
      
      <button @click="connectTwitch" class="btn-twitch">
        <svg><use href="#icon-twitch" /></svg>
        Connect with Twitch
      </button>
    </GlassCard>
  </div>
</template>

<style scoped lang="scss">
// Light mode fixes
[data-theme="light"] & {
  .streamer-input {
    background: white;
    border: 2px solid var(--border-color);
    color: var(--text-primary);
  }
  
  .add-card, .import-card {
    background: rgba(255, 255, 255, 0.9);
  }
}

// OR Divider - High contrast
.divider-container {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
  margin: var(--spacing-6) 0;
  
  .divider-line {
    flex: 1;
    height: 2px;
    background: var(--border-color);
  }
  
  .divider-text {
    font-size: var(--text-lg);
    font-weight: 700;
    color: var(--text-primary);
    background: var(--background-card);
    padding: var(--spacing-2) var(--spacing-4);
    border-radius: var(--radius-full);
    border: 2px solid var(--border-color);
  }
}

// Wider callback URL
.callback-url {
  background: var(--background-darker);
  padding: var(--spacing-4);
  border-radius: var(--radius-md);
  margin: var(--spacing-3) 0;
  
  .url-code {
    display: block;
    font-family: 'Courier New', monospace;
    font-size: var(--text-sm);
    color: var(--primary-color);
    word-break: break-all; // FIXED: Allows wrapping
    padding: var(--spacing-2);
    background: var(--background-card);
    border-radius: var(--radius-sm);
    margin: var(--spacing-2) 0;
  }
}

// Mobile responsive
@media (max-width: 640px) {
  .add-card, .import-card {
    padding: var(--spacing-4);
  }
  
  button {
    min-height: 44px; // Touch target
    width: 100%;
  }
}
</style>
```

---

### Issue #NEW5: Settings Tables - Mobile Responsive Design (HIGH)
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH - Unusable on mobile  
**Estimated Time:** 4-6 hours

**Problems:**

**Affected Tables:**
1. **Notification Settings** - Streamer notification matrix
2. **Recording Settings** - Per-streamer recording config
3. **Favorite Games** - Search input doesn't match theme

**Current Issues:**
- Tables don't collapse on mobile (< 768px)
- Horizontal scroll is bad UX
- Checkboxes too small for touch
- Headers get lost
- Light mode: Poor contrast

**Files to Fix:**
```
app/frontend/src/views/SettingsView.vue (Notifications tab)
app/frontend/src/views/SettingsView.vue (Recording tab)
app/frontend/src/views/SettingsView.vue (Favorite Games tab)
```

**Solution: Transform Tables to Cards on Mobile**

```vue
<!-- Notification Settings - Mobile Cards -->
<template>
  <!-- Desktop: Table (≥ 768px) -->
  <table class="streamer-notifications-table desktop-only">
    <thead>
      <tr>
        <th>Streamer</th>
        <th>Online</th>
        <th>Offline</th>
        <th>Updates</th>
        <th>Favorites</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="streamer in streamers" :key="streamer.id">
        <!-- ... -->
      </tr>
    </tbody>
  </table>
  
  <!-- Mobile: Cards (< 768px) -->
  <div class="streamer-notifications-cards mobile-only">
    <GlassCard v-for="streamer in streamers" :key="streamer.id" class="streamer-card">
      <div class="card-header">
        <img :src="streamer.profile_image" :alt="streamer.display_name" />
        <h3>{{ streamer.display_name }}</h3>
      </div>
      
      <div class="notification-toggles">
        <label class="toggle-row">
          <span>Notify when online</span>
          <input type="checkbox" v-model="streamer.notify_online" />
        </label>
        <label class="toggle-row">
          <span>Notify when offline</span>
          <input type="checkbox" v-model="streamer.notify_offline" />
        </label>
        <label class="toggle-row">
          <span>Title/Category changes</span>
          <input type="checkbox" v-model="streamer.notify_updates" />
        </label>
        <label class="toggle-row">
          <span>Favorite game notifications</span>
          <input type="checkbox" v-model="streamer.notify_favorites" />
        </label>
      </div>
      
      <div class="card-actions">
        <button @click="editStreamer(streamer)" class="btn-edit">
          <svg><use href="#icon-edit" /></svg>
          Edit
        </button>
        <button @click="deleteStreamer(streamer)" class="btn-danger">
          <svg><use href="#icon-trash" /></svg>
          Delete
        </button>
      </div>
    </GlassCard>
  </div>
</template>

<style scoped lang="scss">
// Show/hide based on screen size
.desktop-only {
  display: table;
  @media (max-width: 768px) {
    display: none;
  }
}

.mobile-only {
  display: none;
  @media (max-width: 768px) {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-4);
  }
}

// Mobile card styling
.streamer-card {
  .card-header {
    display: flex;
    align-items: center;
    gap: var(--spacing-3);
    margin-bottom: var(--spacing-4);
    
    img {
      width: 48px;
      height: 48px;
      border-radius: 50%;
    }
    
    h3 {
      font-size: var(--text-lg);
      font-weight: 600;
    }
  }
  
  .notification-toggles {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
    
    .toggle-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: var(--spacing-3);
      background: var(--background-darker);
      border-radius: var(--radius-md);
      min-height: 44px; // Touch target
      
      span {
        font-size: var(--text-sm);
        color: var(--text-primary);
      }
      
      input[type="checkbox"] {
        width: 24px;
        height: 24px;
        cursor: pointer;
      }
    }
  }
  
  .card-actions {
    display: flex;
    gap: var(--spacing-2);
    margin-top: var(--spacing-4);
    
    button {
      flex: 1;
      min-height: 44px;
    }
  }
}

// Favorite Games search fix
.game-search-input {
  background: var(--background-card);
  border: 2px solid var(--border-color);
  color: var(--text-primary);
  padding: var(--spacing-3);
  border-radius: var(--radius-lg);
  
  &::placeholder {
    color: var(--text-secondary);
  }
  
  // Light mode fix
  [data-theme="light"] & {
    background: white;
    border-color: var(--border-color);
  }
}
```

---

### Issue #NEW6: StreamerDetailView - Settings Button & Layout Issues (MEDIUM)
**Status:** 🔴 NOT STARTED  
**Priority:** MEDIUM - UX improvement  
**Estimated Time:** 2-3 hours  
**Screenshot:** Screen #streamer-detail

**Problems:**

**1. Settings Button Has No Function**
- "Settings" button exists but does nothing when clicked
- No clear purpose or destination
- Takes up valuable space on mobile

**Proposed Solutions:**

**Option A: Per-Streamer Settings Modal (RECOMMENDED)**
Opens a modal/drawer with streamer-specific settings:

```vue
<!-- StreamerDetailView.vue -->
<template>
  <button @click="openStreamerSettings" class="btn btn-secondary">
    <svg class="icon"><use href="#icon-settings" /></svg>
    Settings
  </button>
  
  <!-- Settings Modal -->
  <Teleport to="body">
    <div v-if="showSettings" class="modal-overlay" @click.self="closeSettings">
      <div class="modal-content settings-modal">
        <div class="modal-header">
          <h2>Settings for {{ streamer.display_name }}</h2>
          <button @click="closeSettings" class="btn-close">
            <svg class="icon"><use href="#icon-x" /></svg>
          </button>
        </div>
        
        <div class="modal-body">
          <!-- Recording Quality Override -->
          <div class="setting-group">
            <label>Recording Quality</label>
            <select v-model="streamerSettings.quality">
              <option value="">Use Global Setting</option>
              <option value="best">Best Available</option>
              <option value="1080p60">1080p60</option>
              <option value="720p60">720p60</option>
              <option value="480p">480p</option>
            </select>
          </div>
          
          <!-- Custom Filename Template -->
          <div class="setting-group">
            <label>Custom Filename Template</label>
            <input 
              v-model="streamerSettings.filenameTemplate" 
              placeholder="Leave empty to use global template"
            />
          </div>
          
          <!-- Auto-Record Toggle -->
          <div class="setting-group">
            <label>
              <input type="checkbox" v-model="streamerSettings.autoRecord" />
              Auto-record this streamer when live
            </label>
          </div>
          
          <!-- Notification Preferences -->
          <div class="setting-group">
            <label>Notifications</label>
            <label>
              <input type="checkbox" v-model="streamerSettings.notifyOnline" />
              Notify when goes online
            </label>
            <label>
              <input type="checkbox" v-model="streamerSettings.notifyOffline" />
              Notify when goes offline
            </label>
          </div>
        </div>
        
        <div class="modal-footer">
          <button @click="closeSettings" class="btn btn-secondary">Cancel</button>
          <button @click="saveSettings" class="btn btn-primary">Save Settings</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
const showSettings = ref(false)
const streamerSettings = ref({
  quality: '',
  filenameTemplate: '',
  autoRecord: true,
  notifyOnline: true,
  notifyOffline: true
})

const openStreamerSettings = () => {
  // Load current settings from API
  loadStreamerSettings()
  showSettings.value = true
}

const closeSettings = () => {
  showSettings.value = false
}

const saveSettings = async () => {
  // Save to API
  await fetch(`/api/streamers/${streamer.id}/settings`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(streamerSettings.value)
  })
  closeSettings()
}
</script>
```

**Option B: Navigate to Settings Page (Alternative)**
```typescript
// Route to global settings with streamer pre-selected
router.push(`/settings/recording?streamer=${streamer.id}`)
```

**Option C: Remove Button (Simplest)**
If per-streamer settings aren't needed, just remove the button and give more space to "Record Now" and "Delete All".

**Recommendation:** Option A (Modal) - Most user-friendly and consistent with design

**2. Avg Duration Icon Background Larger Than Others**
- "Avg Duration" stat card icon background is wider
- Inconsistent with "Total VODs" and "Total Size" icons
- Visual imbalance

**Fix:**
```scss
// StreamerDetailView.vue (or StatusCard.vue)
.stat-icon {
  width: 48px;   // FIXED: Standardize all icons
  height: 48px;  // FIXED: Standardize all icons
  flex-shrink: 0;  // Prevent growing/shrinking
  
  display: flex;
  align-items: center;
  justify-content: center;
  
  .icon {
    width: 24px;  // Icon itself (consistent)
    height: 24px;
  }
}
```

**3. Button Text Wrapping on Mobile**
- "Delete All" and "Record Now" buttons wrap to 2 lines on small screens
- Caused by "Settings" button taking up space

**Solution (if keeping Settings button):**
```scss
@media (max-width: 480px) {
  .action-buttons {
    flex-wrap: wrap;
    gap: var(--spacing-2);
    
    button {
      flex: 1 1 calc(50% - var(--spacing-1)); // 2 buttons per row
      min-width: 0; // Allow text truncation
      font-size: var(--text-sm); // Slightly smaller text
    }
  }
}
```

**Solution (if removing Settings button):**
```vue
<!-- Only 2 buttons = more space -->
<div class="action-buttons">
  <button class="btn btn-primary">Record Now</button>
  <button class="btn btn-danger">Delete All</button>
</div>
```

**Files to Modify:**
- `app/frontend/src/views/StreamerDetailView.vue`
- `app/frontend/src/components/cards/StatusCard.vue` (icon sizing)
- Optional: Create `app/frontend/src/components/modals/StreamerSettingsModal.vue`

**Implementation Steps:**
1. **Decide:** Modal vs Route vs Remove
2. **If Modal:**
   - Create modal component
   - Add settings state management
   - Create API endpoint `/api/streamers/:id/settings`
   - Add backend model for per-streamer settings
3. **If Route:** Update router and settings view
4. **If Remove:** Delete button, adjust layout
5. Fix icon sizing for all stat cards
6. Test button layout on mobile (375px, 414px)

**API Endpoint Needed (if Modal):**
```python
# app/routes/streamers.py
@router.get("/api/streamers/{streamer_id}/settings")
async def get_streamer_settings(streamer_id: int):
    return {
        "quality": streamer.quality_override or None,
        "filename_template": streamer.filename_template_override or None,
        "auto_record": streamer.auto_record,
        "notify_online": streamer.notify_online,
        "notify_offline": streamer.notify_offline
    }

@router.put("/api/streamers/{streamer_id}/settings")
async def update_streamer_settings(streamer_id: int, settings: StreamerSettings):
    # Update settings
    # Return updated settings
```

---

## 🟡 MEDIUM PRIORITY

### Issue #6: Last Stream Info for Offline Streamers
**Status:** 🟡 NOT STARTED  
**Priority:** MEDIUM - Nice to have  
**Estimated Time:** 4-6 hours (includes backend)

**Problem:**
Offline streamer cards look empty, lots of whitespace.

**Current Behavior:**
```
OFFLINE Card:
[Avatar]
[Name]
[Description] or empty
[VODs count]
```

**Desired Behavior:**
```
OFFLINE Card:
[Avatar]
[Name]
[Last Stream Title] (grayed out)
[Last Category] (grayed out)
[VODs count] [Last streamed: 2 days ago]
```

**Benefits:**
- Less whitespace
- More informative
- Consistent card heights

**Backend Changes Required:**

**1. Add Fields to Streamer Model**
File: `app/models.py`

```python
class Streamer(Base):
    # ... existing fields ...
    
    # NEW: Cache last stream info
    last_stream_title = Column(String, nullable=True)
    last_stream_category = Column(String, nullable=True)
    last_stream_date = Column(DateTime(timezone=True), nullable=True)
    
    @property
    def last_stream_info(self):
        """Get last stream info (fallback to most recent VOD)"""
        if self.last_stream_title:
            return {
                'title': self.last_stream_title,
                'category': self.last_stream_category,
                'date': self.last_stream_date
            }
        
        # Fallback: Query most recent stream
        latest_stream = (
            object_session(self)
            .query(Stream)
            .filter(Stream.streamer_id == self.id)
            .filter(Stream.title.isnot(None))
            .order_by(Stream.created_at.desc())
            .first()
        )
        
        if latest_stream:
            return {
                'title': latest_stream.title,
                'category': latest_stream.category_name,
                'date': latest_stream.created_at
            }
        
        return None
```

**2. Update Streamer on Stream End**
File: `app/services/recording_service.py` or `app/services/eventsub_service.py`

```python
async def on_stream_offline(streamer_id: int, stream_data: dict):
    """Update streamer with last stream info when going offline"""
    streamer = db.query(Streamer).filter(Streamer.id == streamer_id).first()
    if streamer and stream_data:
        streamer.last_stream_title = stream_data.get('title')
        streamer.last_stream_category = stream_data.get('category_name')
        streamer.last_stream_date = datetime.now(timezone.utc)
        db.commit()
```

**3. Migration Script**
File: `migrations/0XX_add_last_stream_info.py`

```python
def upgrade():
    # Add columns
    op.add_column('streamers', sa.Column('last_stream_title', sa.String(), nullable=True))
    op.add_column('streamers', sa.Column('last_stream_category', sa.String(), nullable=True))
    op.add_column('streamers', sa.Column('last_stream_date', sa.DateTime(timezone=True), nullable=True))
    
    # Backfill from existing streams
    connection = op.get_bind()
    connection.execute("""
        UPDATE streamers s
        SET 
            last_stream_title = latest.title,
            last_stream_category = latest.category_name,
            last_stream_date = latest.created_at
        FROM (
            SELECT DISTINCT ON (streamer_id) 
                streamer_id, title, category_name, created_at
            FROM streams
            WHERE title IS NOT NULL
            ORDER BY streamer_id, created_at DESC
        ) latest
        WHERE s.id = latest.streamer_id
    """)
```

**4. Update API Response**
File: `app/routes/streamers.py`

```python
@router.get("/api/streamers")
async def get_streamers(...):
    return {
        "streamers": [{
            "id": s.id,
            "username": s.username,
            "is_live": s.is_live,
            # ... existing fields ...
            
            # NEW: Last stream info (only when offline)
            "last_stream_title": s.last_stream_title if not s.is_live else None,
            "last_stream_category": s.last_stream_category if not s.is_live else None,
            "last_stream_date": s.last_stream_date.isoformat() if s.last_stream_date and not s.is_live else None,
        } for s in streamers]
    }
```

**Frontend Changes:**

File: `app/frontend/src/components/cards/StreamerCard.vue`

```vue
<template>
  <div class="stream-info-container">
    <!-- LIVE -->
    <div v-if="isLive" class="live-info">
      <p class="stream-title">{{ streamer.title }}</p>
    </div>
    
    <!-- OFFLINE with last stream info -->
    <div v-else-if="streamer.last_stream_title" class="offline-info">
      <p class="stream-title offline-title">{{ streamer.last_stream_title }}</p>
      <p v-if="streamer.last_stream_category" class="stream-category offline-category">
        <svg class="category-icon"><use href="#icon-gamepad" /></svg>
        {{ streamer.last_stream_category }}
      </p>
    </div>
    
    <!-- OFFLINE without info -->
    <p v-else class="streamer-description no-description">
      No recent streams
    </p>
  </div>
</template>

<style scoped lang="scss">
.offline-title {
  color: var(--text-secondary);  // Grayed out
  opacity: 0.7;
  font-style: italic;
}

.offline-category {
  color: var(--text-secondary);
  opacity: 0.6;
}
</style>
```

**Testing Checklist:**
- [ ] Migration runs successfully
- [ ] Existing streamers have backfilled data
- [ ] New streams update last_stream_* on offline
- [ ] API returns last stream data
- [ ] Frontend displays grayed-out info
- [ ] Live streamers don't show last stream data
- [ ] No performance impact (indexed queries)

---

### Issue #9: Add Missing Icons Throughout App
**Status:** 🟡 NOT STARTED  
**Priority:** MEDIUM - Visual polish  
**Estimated Time:** 3-4 hours

**Problem:**
Icons missing in many places throughout the app.

**Affected Areas:**

**1. Home View - Quick Stats**
File: `app/frontend/src/views/HomeView.vue`

Current (NO ICONS):
```
Quick Stats
-----------
2              Total Streamers
0              Live Now
0              Recording
0              Recent Videos
```

Add Icons:
```vue
<StatusCard
  :value="2"
  label="Total Streamers"
  icon="users"  <!-- ADD -->
  type="primary"
/>
<StatusCard
  :value="0"
  label="Live Now"
  icon="radio"  <!-- ADD (or "wifi" or "live") -->
  type="danger"
/>
<StatusCard
  :value="0"
  label="Recording"
  icon="video"  <!-- ADD -->
  type="warning"
/>
<StatusCard
  :value="0"
  label="Recent Videos"
  icon="film"  <!-- ADD -->
  type="info"
/>
```

**2. Add Streamer View**
File: Needs to be identified (likely `AddStreamerView.vue` or similar)

Missing icons on buttons:
- "Check" button
- "Add Streamer" button
- "Connect with Twitch" button

**3. Settings View - About Section**
File: `app/frontend/src/views/SettingsView.vue` (About tab)

```vue
<!-- Current: Empty space above "StreamVault" -->
<div class="about-section">
  <h2>StreamVault</h2>
  ...
</div>

<!-- ADD: App icon/logo -->
<div class="about-section">
  <div class="app-icon">
    <svg class="logo-icon">
      <use href="#icon-logo" />  <!-- Or custom StreamVault logo -->
    </svg>
  </div>
  <h2>StreamVault</h2>
  ...
</div>
```

**4. Buttons Without Icons**
Search for buttons that should have icons:

```bash
# Find buttons without icons
grep -r "<button" app/frontend/src/views/*.vue | grep -v "svg"
```

Common patterns to add:
- Save buttons → `#icon-save` or `#icon-check`
- Delete buttons → `#icon-trash`
- Refresh buttons → `#icon-refresh`
- Edit buttons → `#icon-edit`
- Settings buttons → `#icon-settings`

**Icon Sprite Reference:**
File: `app/frontend/public/icons.svg` or check existing icons in codebase

Available icons (check sprite):
- users, user
- video, film, play
- live, radio, wifi
- trash, delete
- edit, settings
- check, x, close
- refresh, rotate
- save, download
- etc.

**Implementation:**
1. Audit all views for missing icons
2. Check available icons in sprite
3. Add missing icons to buttons/cards
4. Ensure consistent icon sizes (16px-24px depending on context)
5. Test visual balance

---

### Issue #11: Recording Animation in Streamer Overview (Grid)
**Status:** ✅ ALREADY IMPLEMENTED  
**Priority:** MEDIUM - Visual consistency  
**Estimated Time:** 1-2 hours

**VERIFICATION:** Animation already fully implemented in StreamerCard.vue!

**Current Implementation:**
```scss
// Recording indicator: Pulsing border animation
&.is-recording {
  :deep(.glass-card-content) {
    animation: pulse-recording 2s ease-in-out infinite;
  }
}

@keyframes pulse-recording {
  0% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
  }
}
```

**File:** `app/frontend/src/components/cards/StreamerCard.vue` (lines 330-335, 784-796)  
**Commit:** dca57696  
**Features:**
- ✅ Pulsing shadow effect when recording
- ✅ 2s ease-in-out animation
- ✅ Red color matches live badge
- ✅ Works in both grid and list view

**No additional changes needed!**

Find the working pulsing animation:
```scss
// COPY THESE animations from Detail View
@keyframes pulse-recording {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.05);
  }
}

@keyframes pulse-border {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
  }
}

.streamer-header.is-recording {
  border: 2px solid var(--danger-color);
  animation: pulse-border 2s ease-in-out infinite;
  
  .recording-badge {
    animation: pulse-recording 2s ease-in-out infinite;
  }
}
```

**2. Apply to StreamerCard Component**

File: `app/frontend/src/components/cards/StreamerCard.vue`

Current (BROKEN - no animation):
```scss
.streamer-card {
  &.is-live {
    :deep(.glass-card-content) {
      border: 2px solid var(--danger-color);  // Static border
      box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.1), var(--shadow-md);
    }
  }
}
```

Fixed (WITH animation):
```scss
// Add keyframes at component level
@keyframes pulse-recording {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.05);
  }
}

@keyframes pulse-border {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
  }
}

.streamer-card {
  // Live indicator (static)
  &.is-live {
    :deep(.glass-card-content) {
      border: 2px solid var(--danger-color);
      box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.1), var(--shadow-md);
    }
  }
  
  // Recording indicator (PULSING)
  &.is-recording {
    :deep(.glass-card-content) {
      border: 2px solid var(--danger-color);
      animation: pulse-border 2s ease-in-out infinite;  // ADD THIS
    }
    
    .live-badge,
    .recording-badge {
      animation: pulse-recording 2s ease-in-out infinite;  // ADD THIS
    }
  }
}
```

**3. Ensure Component Has `is-recording` Class**

Check template:
```vue
<template>
  <GlassCard
    @click="handleClick"
    class="streamer-card"
    :class="{ 
      'is-live': isLive,
      'is-recording': isRecording  <!-- ENSURE THIS EXISTS -->
    }"
  >
    <!-- ... -->
  </GlassCard>
</template>

<script setup lang="ts">
const isRecording = computed(() => {
  // Check if actively recording
  return props.streamer.is_recording || 
         props.streamer.current_stream?.status === 'recording'
})
</script>
```

**4. Alternative: Check if Badge Needs Animation**

Find the recording/live badge element:
```vue
<div v-if="isLive" class="live-badge">
  <span class="live-indicator"></span>
  <span class="live-text">LIVE</span>
</div>

<!-- Or if there's a separate recording badge -->
<div v-if="isRecording" class="recording-badge">
  <span class="recording-dot"></span>
  <span class="recording-text">RECORDING</span>
</div>
```

Apply animation to badge:
```scss
.live-badge,
.recording-badge {
  .live-indicator,
  .recording-dot {
    // Pulsing dot
    animation: pulse-recording 2s ease-in-out infinite;
  }
}

.streamer-card.is-recording {
  .live-badge,
  .recording-badge {
    // Entire badge pulses when recording
    animation: pulse-recording 2s ease-in-out infinite;
  }
}
```

**Implementation Steps:**
1. Open StreamerDetailView.vue and copy the working pulse animations
2. Add keyframes to StreamerCard.vue
3. Add `.is-recording` class logic to card
4. Apply `pulse-border` animation to card border
5. Apply `pulse-recording` animation to badge/indicator
6. Test with active recording
7. Verify animation matches Detail View exactly

**Testing Checklist:**
- [ ] Recording badge pulses in grid view (opacity + scale)
- [ ] Red border pulses with shadow effect in grid
- [ ] Animation timing matches Detail View (2s ease-in-out)
- [ ] Animation stops when recording ends
- [ ] No animation when only live (not recording)
- [ ] Looks good in both light and dark mode
- [ ] Works in both grid and list view

**Files to Modify:**
- `app/frontend/src/components/cards/StreamerCard.vue` (add animations)
- Copy animations from: `app/frontend/src/views/StreamerDetailView.vue`

**Alternative: Extract to Shared SCSS**

If animations are used in multiple places, extract to `_animations.scss`:

File: `app/frontend/src/styles/_animations.scss` (create if needed)

```scss
// Recording pulse animations - shared across components

@keyframes pulse-recording {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.05);
  }
}

@keyframes pulse-border {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
  }
}

// Mixin for recording state
@mixin recording-state {
  &.is-recording {
    border: 2px solid var(--danger-color);
    animation: pulse-border 2s ease-in-out infinite;
    
    .recording-badge,
    .live-badge {
      animation: pulse-recording 2s ease-in-out infinite;
    }
  }
}
```

Then import in both files:
```scss
@use '../styles/animations' as anim;

.streamer-card {
  @include anim.recording-state;
}

.streamer-header {
  @include anim.recording-state;
}
```

---

## � HIGH PRIORITY - New Issues from User Feedback (11. Nov 2025)

### Issue #12: StreamersView - Auto ON Button ✅ VERIFIED
**Status:** ✅ VERIFIED - Icons already present  
**Finding:** Button already has #icon-refresh-cw, uses correct CSS variables  
**Note:** Task description was outdated - icon was already implemented

**Original Problem (now resolved):**
- Button already functional with icon
- Uses var(--text-primary) for theme compatibility

---

### Issue #13: StreamersView - Search & Toggle Icons ✅ VERIFIED
**Status:** ✅ VERIFIED - Icons already present  
**Finding:** Search (#icon-search), Grid (#icon-grid), List (#icon-list) all implemented  

---

### Issue #14: VideosView - Button Icons ✅ VERIFIED
**Status:** ✅ VERIFIED - Icons already present  
**Finding:** Cancel/Select (#icon-check-square), Filters (#icon-filter) all implemented  

---

### Issue #15: SubscriptionsView - Button Icons ✅ VERIFIED
**Status:** ✅ VERIFIED - Icons already present  
**Finding:** Resubscribe (#icon-repeat), Delete All (#icon-trash-2), Refresh (#icon-refresh-cw) all implemented

---

### Issue #16: Settings - Notifications Tab - Buttons & Table Design 🔴
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH  
**Estimated Time:** 3-4 hours  
**Screenshot:** Screen #7

**Problems:**
1. "Save Settings", "Enable All", "Disable All" buttons white text (invisible)
2. Streamer notification table doesn't match glassmorphism design
3. Table has plain borders, no backdrop blur
4. Checkboxes not styled
5. Missing icons in table headers

**Current Table (PLAIN HTML):**
```vue
<table class="notifications-table">
  <thead>
    <tr>
      <th>Streamer</th>
      <th>Online</th>
      <th>Offline</th>
      <th>Updates</th>
      <th>Favorites</th>
      <th>Actions</th>
    </tr>
  </thead>
  <!-- ... -->
</table>
```

**Fix - GlassCard Integration:**
```vue
<div class="notifications-container">
  <GlassCard
    v-for="streamer in streamers"
    :key="streamer.id"
    variant="subtle"
    class="notification-card"
  >
    <div class="notification-row">
      <div class="streamer-info">
        <img :src="streamer.avatar" class="avatar" />
        <span>{{ streamer.name }}</span>
      </div>
      
      <div class="notification-toggles">
        <div class="toggle-item">
          <label>
            <input type="checkbox" v-model="streamer.notify_online" />
            <svg class="icon"><use href="#icon-video" /></svg>
            Online
          </label>
        </div>
        
        <div class="toggle-item">
          <label>
            <input type="checkbox" v-model="streamer.notify_offline" />
            <svg class="icon"><use href="#icon-video-off" /></svg>
            Offline
          </label>
        </div>
        
        <!-- etc -->
      </div>
    </div>
  </GlassCard>
</div>
```

**Files:**
- `app/frontend/src/views/SettingsView.vue` (Notifications tab)

---

### Issue #17: Settings - Recording Tab - Streamer Settings Table 🔴
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH  
**Estimated Time:** 3-4 hours  
**Screenshot:** Screen #8

**Problems:**
1. Streamer-specific recording settings table SEHR SCHLIMM (very bad design)
2. Plain table borders, no glassmorphism
3. Quality dropdowns plain select elements
4. "Policy" buttons misaligned
5. No icons anywhere

**Current Table:**
```vue
<table class="streamer-settings-table">
  <tr>
    <td><img src="avatar" /></td>
    <td>maxim</td>
    <td>
      <select v-model="quality">
        <option>Best Available</option>
      </select>
    </td>
    <td>
      <input type="text" placeholder="Use global template" />
    </td>
    <td>
      <button class="btn-policy">Policy</button>  <!-- Plain button -->
    </td>
  </tr>
</table>
```

**Fix - Card-Based Design:**
```vue
<div class="streamer-recording-settings">
  <GlassCard
    v-for="streamer in streamers"
    :key="streamer.id"
    variant="subtle"
    class="streamer-setting-card"
  >
    <div class="setting-row">
      <!-- Avatar & Name -->
      <div class="streamer-info">
        <img :src="streamer.avatar" class="avatar-small" />
        <span class="name">{{ streamer.name }}</span>
      </div>
      
      <!-- Record Toggle -->
      <div class="setting-item">
        <label class="switch">
          <input type="checkbox" v-model="streamer.recording_enabled" />
          <span class="slider"></span>
        </label>
        <span class="label">Record</span>
      </div>
      
      <!-- Quality Dropdown -->
      <div class="setting-item">
        <label>Quality</label>
        <select v-model="streamer.quality" class="styled-select">
          <option value="best">Best Available</option>
          <option value="1080p60">1080p60</option>
          <option value="720p">720p</option>
        </select>
      </div>
      
      <!-- Custom Filename -->
      <div class="setting-item">
        <input 
          type="text" 
          v-model="streamer.custom_filename"
          placeholder="Use global template"
          class="styled-input"
        />
      </div>
      
      <!-- Actions -->
      <div class="setting-actions">
        <button class="btn btn-secondary btn-sm">
          <svg class="icon"><use href="#icon-settings" /></svg>
          Policy
        </button>
        
        <button class="btn btn-secondary btn-sm">
          <svg class="icon"><use href="#icon-trash" /></svg>
        </button>
      </div>
    </div>
  </GlassCard>
</div>
```

**Styled Select Example:**
```scss
.styled-select {
  background: var(--background-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-2) var(--spacing-3);
  font-size: var(--text-sm);
  
  &:hover {
    border-color: var(--primary-color);
  }
  
  &:focus {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
}
```

**Files:**
- `app/frontend/src/views/SettingsView.vue` (Recording tab)

---

### Issue #18: Settings - Network Tab - Double Borders 🔴
**Status:** 🔴 NOT STARTED  
**Priority:** MEDIUM  
**Estimated Time:** 1-2 hours  
**Screenshot:** Screen #9

**Problems:**
1. Proxy URL examples box has DOUBLE border (inner + outer)
2. Box doesn't match glassmorphism design
3. Tips section looks inconsistent

**Current State:**
```vue
<div class="proxy-examples">
  <div class="examples-box" style="border: 1px solid; padding: 20px;">
    <!-- Double border created by box + content -->
    <h4>Proxy URL Examples:</h4>
    <ul>
      <li>...</li>
    </ul>
  </div>
</div>
```

**Fix:**
```vue
<GlassCard variant="subtle" class="proxy-info-card">
  <h4 class="card-title">
    <svg class="icon"><use href="#icon-info" /></svg>
    Proxy URL Examples
  </h4>
  
  <ul class="example-list">
    <li><code>http://proxy.example.com:8080</code> - Basic proxy</li>
    <li><code>http://username:password@proxy.example.com:8080</code> - Authenticated</li>
    <!-- ... -->
  </ul>
</GlassCard>

<GlassCard variant="subtle" class="tips-card">
  <h4 class="card-title">
    <svg class="icon"><use href="#icon-lightbulb" /></svg>
    Tips
  </h4>
  
  <ul class="tips-list">
    <li>Use HTTPS proxy for better security</li>
    <!-- ... -->
  </ul>
</GlassCard>
```

**Files:**
- `app/frontend/src/views/SettingsView.vue` (Network tab)

---

### Issue #19: Settings - Favorite Games - Search Black Background 🔴
**Status:** 🔴 NOT STARTED  
**Priority:** MEDIUM  
**Estimated Time:** 20 min  
**Screenshot:** Screen #10

**Problem:**
- Search input has black background in light mode (hardcoded)

**Current:**
```scss
.game-search {
  background: black;  // WRONG
  color: white;
}
```

**Fix:**
```scss
.game-search {
  background: var(--background-darker);  // Theme-aware
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  
  &::placeholder {
    color: var(--text-secondary);
  }
}
```

**Files:**
- `app/frontend/src/views/SettingsView.vue` (Favorite Games tab)

---

### Issue #20: Settings - Favorite Games - Too Much Whitespace (Desktop) 🟡
**Status:** 🟡 NOT STARTED  
**Priority:** MEDIUM  
**Estimated Time:** 1 hour  
**Screenshot:** Screen #13

**Problem:**
- Only 3 rows of game tiles on large desktop screens
- Tons of unused whitespace
- Could show 5-6 rows on 1920px+ screens

**Current Layout:**
```scss
.games-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--spacing-4);
}
```

**Suggested Fix - Responsive Columns:**
```scss
.games-grid {
  display: grid;
  gap: var(--spacing-4);
  
  // Mobile: 2 columns
  grid-template-columns: repeat(2, 1fr);
  
  // Tablet: 3 columns
  @media (min-width: 768px) {
    grid-template-columns: repeat(3, 1fr);
  }
  
  // Desktop: 4 columns
  @media (min-width: 1024px) {
    grid-template-columns: repeat(4, 1fr);
  }
  
  // Large Desktop: 5 columns
  @media (min-width: 1440px) {
    grid-template-columns: repeat(5, 1fr);
  }
  
  // Extra Large: 6 columns
  @media (min-width: 1920px) {
    grid-template-columns: repeat(6, 1fr);
  }
}
```

**Alternative - Fixed Max Width:**
```scss
.games-container {
  max-width: 1600px;  // Limit container width
  margin: 0 auto;
  
  .games-grid {
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  }
}
```

**Files:**
- `app/frontend/src/views/SettingsView.vue` (Favorite Games tab)

---

### Issue #21: Settings - PWA Tab - Buttons Eckig (Square) 🔴
**Status:** 🔴 NOT STARTED  
**Priority:** MEDIUM  
**Estimated Time:** 1 hour  
**Screenshot:** Screen #14

**Problems:**
1. Buttons have NO border-radius (square corners)
2. Buttons don't match design system
3. Missing icons on buttons
4. Button colors hardcoded

**Current Buttons:**
```vue
<button class="enable-notifications">Enable Notifications</button>  <!-- Square -->
<button class="test-notification">Test Notification</button>  <!-- Square -->
```

**Fix:**
```vue
<button class="btn btn-primary">
  <svg class="icon"><use href="#icon-bell" /></svg>
  Enable Notifications
</button>

<button class="btn btn-secondary">
  <svg class="icon"><use href="#icon-send" /></svg>
  Test Notification
</button>
```

**CSS Fix:**
```scss
// Ensure all buttons use design system
.pwa-settings {
  .btn,
  button {
    border-radius: var(--radius-lg);  // NOT 0
    // ... rest of button styles
  }
}
```

**Files:**
- `app/frontend/src/views/SettingsView.vue` (PWA & Mobile tab)

---

### Issue #22: Settings - Advanced Tab - Remove Entirely? 🟡
**Status:** 🟡 DISCUSSION NEEDED  
**Priority:** LOW  
**Estimated Time:** 30 min (if removing)  
**Screenshot:** None

**Problem:**
- Debug Mode: Can only be enabled via docker-compose environment variable (not saved in DB)
- Clear Cache Button: Purpose unclear, what does it clear?

**Options:**

**Option A: Remove Tab Entirely**
```vue
<!-- Remove from settings tabs array -->
const settingsTabs = [
  { id: 'notifications', label: 'Notifications', icon: 'bell' },
  { id: 'recording', label: 'Recording', icon: 'video' },
  { id: 'favorites', label: 'Favorite Games', icon: 'gamepad' },
  { id: 'appearance', label: 'Appearance', icon: 'sun' },
  { id: 'pwa', label: 'PWA & Mobile', icon: 'smartphone' },
  // { id: 'advanced', label: 'Advanced', icon: 'settings' },  // REMOVE
  { id: 'about', label: 'About', icon: 'info' }
]
```

**Option B: Repurpose Tab**
- Rename to "System" or "Developer"
- Add useful debugging info (read-only):
  - Backend version
  - Database size
  - Number of recordings
  - Disk space usage
  - System health checks

**Option C: Move Clear Cache to Different Tab**
- Move to Appearance tab (clear UI cache)
- Or PWA tab (clear PWA cache)

**Decision Needed:**
- What does "Clear Cache" currently do?
- Is debug mode toggle actually functional?
- Keep or remove?

**Files:**
- `app/frontend/src/views/SettingsView.vue`

---

### Issue #23: Settings - About Tab - Missing Icons & Broken Links 🔴
**Status:** 🔴 NOT STARTED  
**Priority:** MEDIUM  
**Estimated Time:** 30 min  
**Screenshot:** Screen #14

**Problems:**
1. Missing icon above "StreamVault" title
2. GitHub link not styled/clickable
3. Documentation link is placeholder

**Current State:**
```vue
<div class="about-section">
  <h2>StreamVault</h2>  <!-- No icon -->
  <p>Version: 1.0.0</p>
  
  <a href="https://github.com/...">GitHub</a>  <!-- Not styled -->
  <a href="#">Documentation</a>  <!-- Placeholder -->
</div>
```

**Fix:**
```vue
<GlassCard variant="medium" class="about-card">
  <!-- App Icon/Logo -->
  <div class="app-logo-container">
    <div class="app-logo">
      <svg class="logo-icon">
        <use href="#icon-briefcase" />  <!-- Or custom StreamVault logo -->
      </svg>
    </div>
  </div>
  
  <h2 class="app-name">StreamVault</h2>
  <p class="app-version">Version {{ appVersion }}</p>
  <p class="app-description">
    Automated Twitch stream recording and management platform
  </p>
  
  <div class="links-section">
    <a 
      href="https://github.com/Serph91P/StreamVault" 
      target="_blank"
      class="link-btn"
    >
      <svg class="icon"><use href="#icon-github" /></svg>
      View on GitHub
    </a>
    
    <a 
      href="https://github.com/Serph91P/StreamVault/wiki" 
      target="_blank"
      class="link-btn"
    >
      <svg class="icon"><use href="#icon-book" /></svg>
      Documentation
    </a>
    
    <a 
      href="https://github.com/Serph91P/StreamVault/issues" 
      target="_blank"
      class="link-btn"
    >
      <svg class="icon"><use href="#icon-bug" /></svg>
      Report Issue
    </a>
  </div>
</GlassCard>
```

**Link Button Styling:**
```scss
.link-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-lg);
  
  background: var(--background-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  
  text-decoration: none;
  font-weight: v.$font-medium;
  transition: all v.$duration-200 v.$ease-out;
  
  .icon {
    width: 18px;
    height: 18px;
  }
  
  &:hover {
    background: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }
}
```

**Files:**
- `app/frontend/src/views/SettingsView.vue` (About tab)
- Check if icons exist: icon-github, icon-book, icon-bug

---

### Issue #24: Sidebar vs Settings Menu - Inconsistent Active State 🔴
**Status:** 🔴 NOT STARTED  
**Priority:** MEDIUM  
**Estimated Time:** 1 hour  
**Screenshot:** Screen #15

**Problem:**
- Sidebar active state: Different color/style than Settings menu active state
- Should be consistent across app

**Current Sidebar (HARDCODED):**
```scss
// SidebarNav.vue
.nav-item.active {
  background: #14b8a6;  // Hardcoded teal
  color: white;
  border-left: 4px solid #0d9488;
}
```

**Current Settings Menu (CORRECT):**
```scss
// SettingsView.vue
.setting-item.active {
  background: var(--primary-color);
  color: white;
  border-left: 4px solid var(--primary-600);
}
```

**Fix - Make Sidebar Match Settings:**
```scss
// SidebarNav.vue - USE CSS VARIABLES
.nav-item {
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-md);
  transition: all v.$duration-200 v.$ease-out;
  
  color: var(--text-secondary);
  
  &:hover {
    background: var(--background-hover);
    color: var(--text-primary);
  }
  
  &.active {
    background: var(--primary-color);  // NOT hardcoded
    color: white;
    border-left: 4px solid var(--primary-600);
    
    // Light mode override (if needed)
    [data-theme="light"] & {
      background: var(--primary-600);  // Darker for contrast
      border-left-color: var(--primary-700);
    }
    
    .nav-icon {
      stroke: white;
    }
  }
}
```

**Files:**
- `app/frontend/src/components/navigation/SidebarNav.vue`
- Reference: `app/frontend/src/views/SettingsView.vue` (settings menu styling)

---

### Issue #25: Appearance Settings - Animation Toggle Does Nothing? 🟡
**Status:** 🟡 INVESTIGATION NEEDED  
**Priority:** LOW  
**Estimated Time:** 1-2 hours  

**Question:**
- Does the "Enable Animations" toggle in Appearance settings actually work?
- If not, implement it
- If yes, verify it affects all animations

**Expected Behavior:**
When "Enable Animations" is OFF:
- No page transitions
- No hover animations
- No pulsing/loading animations
- Instant state changes

**Implementation:**
```vue
<!-- SettingsView.vue - Appearance tab -->
<label class="switch">
  <input type="checkbox" v-model="animationsEnabled" @change="updateAnimations" />
  <span class="slider"></span>
</label>

<script setup>
const animationsEnabled = ref(true)

const updateAnimations = () => {
  if (animationsEnabled.value) {
    document.documentElement.style.removeProperty('--animation-duration')
  } else {
    document.documentElement.style.setProperty('--animation-duration', '0s')
  }
  
  localStorage.setItem('animations-enabled', animationsEnabled.value.toString())
}

onMounted(() => {
  const saved = localStorage.getItem('animations-enabled')
  if (saved !== null) {
    animationsEnabled.value = saved === 'true'
    updateAnimations()
  }
})
</script>
```

**CSS Changes:**
```scss
// _variables.scss
$duration-fast: var(--animation-duration, 0.15s);
$duration-normal: var(--animation-duration, 0.3s);
$duration-slow: var(--animation-duration, 0.5s);

// When animations disabled:
// --animation-duration: 0s (set via JS)
```

**Files:**
- `app/frontend/src/views/SettingsView.vue`
- `app/frontend/src/styles/_variables.scss`

---

## �🟢 LOW PRIORITY / NICE TO HAVE

### Issue #10: Settings View Complete Overhaul
**Status:** 🟢 NOT STARTED  
**Priority:** LOW - Big project for later  
**Estimated Time:** 8-12 hours

**10 Separate Issues in Settings:**

1. **Notifications Tab - Inconsistent Borders**
2. **Notifications Tab - Unreadable Buttons**
3. **Streamer Notification Settings - Missing Design**
4. **Recording Settings - Streamer-Specific Settings Broken**
5. **Favorite Games - Search Black in Light Mode**
6. **PWA Settings - Buttons Don't Match Design**
7. **Advanced Tab - Remove Entirely?**
8. **About Section - Missing Icon**
9. **GitHub Link - Not Working**
10. **Documentation Link - Placeholder**

**Recommendation:** 
- Tackle after mobile menu and design system colors
- Break into smaller PRs
- Each settings tab could be a separate task

---

### Other Small Issues from User Feedback

**Jobs Badge Misaligned (Mobile)**
- Location: Header "+ JOBS 0"
- Issue: "+" icon is offset/misaligned
- File: `BackgroundQueueMonitor.vue` or `App.vue` header
- Fix: Adjust flexbox alignment or icon position

**Jobs Modal Not Centered**
- Issue: Modal positioning looks off-center
- Fix: Check modal CSS, ensure proper centering with transform

**Notifications Modal Takes Full Screen**
- Issue: Should it match jobs modal style (smaller)?
- Decision needed: Full screen intentional or should be smaller popup?

**Grid/List Toggle on Mobile**
- Issue: Makes minimal difference on mobile
- Suggestion: Hide toggle on < 768px, always use single-column

**Last Subscription Missing Bottom Border**
- Issue: Visual inconsistency
- Fix: Ensure all subscription cards have consistent borders

---

## 📋 Quick Reference

**Build Command:**
```bash
cd app/frontend
npm run build
```

**Dev Server:**
```bash
cd app/frontend  
npm run dev
```

**Test Mobile:**
```bash
# Chrome DevTools
F12 → Toggle Device Toolbar → Choose device
# Breakpoints: 375px (iPhone SE), 414px (iPhone Pro), 768px (iPad)
```

**Git Workflow:**
```bash
git add -A
git commit -m "fix(ui): description"
git push origin develop
```

**Files Modified Today:**
- `app/frontend/src/router/index.ts`
- `app/frontend/src/components/cards/StreamerCard.vue`

**Key Documentation:**
- Issue tracker: `docs/FRONTEND_ISSUES_VISUAL_FEEDBACK.md`
- Design system: `docs/COMPLETE_DESIGN_OVERHAUL_SUMMARY.md`
- This file: `docs/REMAINING_FRONTEND_TASKS.md`

---

## 🚀 Recommended Workflow for Tomorrow

**Session 2: Morning (2-3 hours)**
1. ✅ Mobile Hamburger Menu (#5)
2. ✅ Design System Colors (#8)

**Session 2: Afternoon (2-3 hours)**
3. ✅ Light Mode Button Visibility (#3)
4. ⏳ Start Icons Audit (#9)

**Session 3: Full Day (6-8 hours)**
5. ⏳ Last Stream Info (Backend + Frontend) (#6)
6. ⏳ Settings View Overhaul (#10)

**Total Estimate:** 12-18 hours remaining work

---

## 💡 Tips for Continuation

**1. Always Check Design System First**
- Before hardcoding colors, check `_variables.scss`
- Use CSS variables: `var(--color-name)`
- Reference: `docs/COMPLETE_DESIGN_OVERHAUL_SUMMARY.md`

**2. Test in Both Themes**
- Dark mode (default)
- Light mode (toggle in app)
- Check contrast with DevTools

**3. Mobile-First**
- Test on 375px first
- Then scale up to 768px, 1024px, 1920px
- Use Chrome DevTools device emulation

**4. Commit Often**
- One fix per commit
- Clear commit messages
- Push after each successful build

**5. Document as You Go**
- Update this file with progress
- Mark todos as complete
- Add new issues discovered

---

## 📊 Session 3 Progress Update (11. Nov 2025 - Afternoon)

### Verified as Already Complete:
1. ✅ **Issue #5: Mobile Hamburger Menu** - Already in App.vue with slide-out, overlay, animations
2. ✅ **Issue #8: Design System Colors** - SidebarNav uses var(--primary-color-dark) since commit 61f16b68
3. ✅ **Issue #3: Light Mode Buttons** - All Settings components use CSS variables (btn-primary, etc.)
4. ✅ **Issue #11: Recording Animation** - StreamerCard has pulse-recording animation since commit dca57696

### Status After Verification:
- **Total Issues:** 59 originally documented
- **Completed:** 16 issues fixed (12 from Session 2 + 4 verified today)
- **Remaining:** 43 issues

### Next Priority Tasks (Actually Need Work):
1. **Last Stream Info for Offline Streamers** (#6) - Backend + Frontend (4-6h)
2. **Settings Table Mobile Responsive** (#16, #17) - Transform to cards (6-8h)
3. **Add Streamer Modal Redesign** (#NEW4) - Icons, divider, callback URL (2-3h)
4. **Favorite Games Spacing** (#19, #20) - Light mode search, grid layout (1-2h)

### Build Status:
- ✅ Frontend builds successfully (3-4s)
- ✅ Zero errors, zero warnings
- ✅ PWA: 100 entries precached
- ✅ All icons embedded inline in App.vue

### Key Files Modified Today:
- None (all verifications showed tasks already complete!)

### Recommendation for Next Session:
**Start with:** Add Streamer Modal Redesign (Issue #NEW4)
- Quick win (2-3 hours)
- High visibility improvement
- Already documented with complete code examples in lines 440-670

**Then tackle:** Last Stream Info (Issue #6)
- Bigger feature but high value
- Complete backend + frontend flow documented
- Will reduce card whitespace significantly

---

**Good luck! 🚀**

### Issues Documented Today: 14 NEW
- **HIGH Priority:** 9 issues (StreamersView, VideosView, SubscriptionsView, Settings tabs)
- **MEDIUM Priority:** 4 issues (Favorite Games spacing, PWA styling, About links, Sidebar consistency)
- **LOW/Discussion:** 1 issue (Advanced tab - remove?)

### Quick Wins (< 1 hour each):
1. Issue #12: Auto ON button light mode (30 min)
2. Issue #13: Search & view toggle icons (20 min)
3. Issue #14: Cancel button visibility (30 min)
4. Issue #15: Subscriptions buttons (1 hour)
5. Issue #19: Favorite Games search background (20 min)
6. Issue #23: About tab icons & links (30 min)
7. Issue #24: Sidebar active state consistency (1 hour)

**Quick Wins Total:** ~4-5 hours

### Bigger Tasks (2-4 hours each):
1. Issue #16: Notifications tab table redesign (3-4 hours)
2. Issue #17: Recording settings table redesign (3-4 hours)
3. Issue #18: Network tab borders (1-2 hours)
4. Issue #20: Favorite Games grid responsive (1 hour)
5. Issue #21: PWA buttons styling (1 hour)
6. Issue #22: Advanced tab decision (30 min - 2 hours)
7. Issue #25: Animation toggle functionality (1-2 hours)

**Bigger Tasks Total:** ~13-20 hours

### Estimated Total Time Remaining:
- **Quick Wins:** 4-5 hours
- **Bigger Tasks:** 13-20 hours
- **Previous Tasks:** 12-18 hours (from Session 1)
- **GRAND TOTAL:** ~29-43 hours

### Recommended Approach:
1. **Day 1:** Knock out all quick wins (4-5 hours)
2. **Day 2-3:** Tackle Settings tabs redesign (2 days, ~12-16 hours)
3. **Day 4-5:** Mobile menu + remaining tasks (2 days, ~12-16 hours)

### Files Most Affected:
- `app/frontend/src/views/SettingsView.vue` (8 issues)
- `app/frontend/src/views/StreamersView.vue` (2 issues)
- `app/frontend/src/views/VideosView.vue` (1 issue)
- `app/frontend/src/views/SubscriptionsView.vue` (1 issue)
- `app/frontend/src/components/navigation/SidebarNav.vue` (1 issue)
- `app/frontend/src/App.vue` (mobile menu - future)

### Design Patterns to Apply Consistently:
1. **All buttons:** `class="btn btn-{variant}"` with icons
2. **All tables:** Convert to GlassCard-based cards
3. **All inputs:** Theme-aware backgrounds with `var(--background-*)`
4. **All icons:** Inline SVG with `<use href="#icon-*">`
5. **All colors:** CSS variables, NEVER hardcode

---

## 📊 Session 4 Progress Update (11. Nov 2025 - Evening)

### Completed This Session:
1. ✅ **Issue #6: Last Stream Info** - Full-stack implementation
   - Backend: Migration 023, API endpoint `/api/streamers/{id}/last_stream_info`
   - Frontend: StreamerCard displays title, game, viewer count when offline
   - Commit: 54191f60, b9dc50e6, 78dbc380

### Status After Session 4:
- **Total Issues:** 59 originally documented
- **Completed:** 20 issues (16 from Sessions 1-3 + 1 from Session 4 + 3 verified)
- **Remaining:** 39 issues

### Build Status:
- ✅ Frontend builds successfully (3.15s)
- ✅ Zero errors, zero warnings
- ✅ Migration 023 runs automatically on app start

---

## 📊 Session 5 Progress Update (11. Nov 2025 - Late Evening)

### Completed This Session (5 NEW Tasks):
1. ✅ **Video Cards Mobile Layout** - VideoCard.vue responsive
   - Added @media (max-width: 767px) and (max-width: 480px)
   - Play button: 72px (tablets) → 56px (phones)
   - Optimized spacing, font sizes, badge positioning
   - Commit: 9f7e0d3b

2. ✅ **Advanced Settings Tab Decision** - KEEP
   - Verified Debug Mode toggle functional
   - Verified Clear Cache button functional
   - Decision: Keep tab (useful maintenance features)

3. ✅ **Settings Panel Borders Consistency** - Glassmorphism standardized
   - NotificationSettingsPanel: Added box-shadow + border
   - PWAPanel: Added box-shadow
   - FavoritesSettingsPanel: Added box-shadow to containers
   - LoggingPanel: Added box-shadow to stat-cards
   - All panels now: `box-shadow: 0 2px 8px rgba(0,0,0,0.15)` + `border: 1px solid var(--border-color)`
   - Commit: a3763a01

4. ✅ **Animation Toggle Functionality** - User preference control
   - Added toggle in Advanced Settings
   - localStorage persistence (`animationsEnabled`)
   - Applies `.no-animations` class to `<html>`
   - Disables all animations, transitions, scroll-behavior globally
   - Global CSS in main.scss with `!important` overrides
   - Commit: da402917

5. ✅ **About Section Links & Icons** - Enhanced UX
   - Icons increased: 16px → 20px
   - Touch targets: 44px (desktop), 48px (mobile)
   - Added box-shadow for glassmorphism depth
   - Enhanced hover: background tint + shadow lift
   - Mobile: Full-width stacked layout (< 640px)
   - Consistent button styling across all settings sections
   - Commit: 68e9c66a

### Status After Session 5:
- **Total Issues:** 59 originally documented
- **Completed:** 25 issues (20 from previous sessions + 5 from Session 5)
- **Remaining:** 34 issues

---

## 📋 REMAINING TASKS (34 Issues)

### 🔴 High Priority (Next Session)

#### 1. AdminView Mobile Tables (Session 6 Continuation)
**Status:** IN PROGRESS (partially committed)  
**Current Commit:** AdminPanel has mobile breakpoints added (12d23ab7)  
**Remaining Work:**
- [ ] Transform background queue tables to mobile cards
- [ ] Transform system stats table to cards
- [ ] Transform recording logs table to cards
- [ ] Add touch-friendly action buttons (44px min-height)
- [ ] Test table → card transformation on real mobile devices

**Affected Files:**
- `app/frontend/src/components/admin/AdminPanel.vue` (partially done)
- `app/frontend/src/components/admin/BackgroundQueueAdmin.vue`
- `app/frontend/src/components/admin/PostProcessingManagement.vue`

**Estimate:** 2-3 hours

---

### 🟡 Medium Priority (Design System Cleanup)

#### 2. Global Spacing Audit
**Problem:** Some components still use hard-coded spacing values  
**Task:**
- [ ] Audit all Vue files for hard-coded `padding`, `margin`, `gap` values
- [ ] Replace with `var(--spacing-*)` design tokens
- [ ] Document spacing scale in frontend.instructions.md

**Pattern:**
```scss
// ❌ WRONG
padding: 12px 16px;
margin: 8px;

// ✅ CORRECT
padding: var(--spacing-3) var(--spacing-4);
margin: var(--spacing-2);
```

**Estimate:** 3-4 hours

#### 3. Global Color Audit
**Problem:** Some components may still have hard-coded color values  
**Task:**
- [ ] Audit all Vue files for hex colors (#ffffff, #42b883, etc.)
- [ ] Replace with `var(--color-*)` design tokens
- [ ] Verify all status colors use `.status-border-*` classes

**Estimate:** 2-3 hours

#### 4. Global Border-Radius Audit
**Problem:** Inconsistent border-radius usage  
**Task:**
- [ ] Audit all Vue files for hard-coded `border-radius` values
- [ ] Replace with `var(--border-radius-*)` design tokens
- [ ] Standardize card, button, input border-radius

**Pattern:**
```scss
// ❌ WRONG
border-radius: 8px;
border-radius: 4px;

// ✅ CORRECT
border-radius: var(--border-radius);     // 8px - default
border-radius: var(--border-radius-sm);  // 4px
border-radius: var(--border-radius-lg);  // 12px
```

**Estimate:** 2-3 hours

---

### 🟢 Low Priority (Nice-to-Have)

#### 5. Animation Performance Audit
**Task:**
- [ ] Review all CSS animations for performance
- [ ] Replace `left`/`top` animations with `transform`
- [ ] Add `will-change` hints where appropriate
- [ ] Test animation performance on low-end devices

**Pattern:**
```scss
// ❌ BAD PERFORMANCE
@keyframes slide {
  from { left: -100%; }
  to { left: 0; }
}

// ✅ GOOD PERFORMANCE
@keyframes slide {
  from { transform: translateX(-100%); }
  to { transform: translateX(0); }
}
```

**Estimate:** 2-3 hours

#### 6. Mobile Touch Target Audit
**Task:**
- [ ] Audit ALL interactive elements (buttons, links, inputs)
- [ ] Ensure minimum 44x44px touch targets on mobile
- [ ] Add visual indicators for touch states (`:active`)

**Files to Check:**
- Navigation components (SidebarNav, BottomNav)
- All cards (VideoCard, StreamerCard, StatusCard)
- All forms (inputs, selects, checkboxes)
- All modals and dialogs

**Estimate:** 2-3 hours

#### 7. iOS Zoom Prevention Audit
**Task:**
- [ ] Audit ALL `<input>` and `<select>` elements
- [ ] Ensure `font-size: 16px` on mobile to prevent iOS zoom
- [ ] Test on real iOS devices (Safari)

**Current Status:** Partially done in Session 6 (VideosView, StreamersView, SettingsView)

**Remaining Files to Check:**
- AddStreamerView.vue
- LoginView.vue
- SetupView.vue
- All Settings panels
- AdminPanel forms

**Estimate:** 1-2 hours

#### 8. Accessibility (a11y) Improvements
**Task:**
- [ ] Add ARIA labels to icon-only buttons
- [ ] Add focus indicators for keyboard navigation
- [ ] Test with screen readers
- [ ] Add `alt` text to all images
- [ ] Ensure proper heading hierarchy

**Example:**
```vue
<!-- ❌ WRONG -->
<button class="btn-icon">
  <svg>...</svg>
</button>

<!-- ✅ CORRECT -->
<button class="btn-icon" aria-label="Delete video">
  <svg aria-hidden="true">...</svg>
</button>
```

**Estimate:** 4-5 hours

#### 9. Dark Mode Audit
**Task:**
- [ ] Verify all components work correctly in dark mode
- [ ] Check color contrast ratios (WCAG AA compliance)
- [ ] Fix any hard-coded colors that don't adapt
- [ ] Test theme switching for flash of unstyled content

**Estimate:** 2-3 hours

#### 10. Light Mode Audit
**Task:**
- [ ] Verify all components work correctly in light mode
- [ ] Check button visibility issues (already fixed in Session 3)
- [ ] Ensure proper text contrast on light backgrounds
- [ ] Test all glassmorphism effects

**Estimate:** 2-3 hours

---

### 🔵 Future Enhancements (Post-MVP)

#### 11. PWA Install Prompt Enhancement
**Current:** Basic browser prompt  
**Proposed:**
- [ ] Custom install banner with app preview
- [ ] Before/after install screenshots
- [ ] Feature highlights (offline, notifications, etc.)
- [ ] Dismiss and "Don't show again" options

**Estimate:** 3-4 hours

#### 12. Notification Feed Redesign
**Current:** Basic list  
**Proposed:**
- [ ] Group by date (Today, Yesterday, This Week, etc.)
- [ ] Add notification actions (Mark as read, Delete)
- [ ] Add notification filters (All, Unread, Important)
- [ ] Implement infinite scroll or pagination

**Estimate:** 4-6 hours

#### 13. Advanced Search & Filters
**Proposed:**
- [ ] Global search across Streamers, Videos, Settings
- [ ] Advanced filters with multiple criteria
- [ ] Search history and suggestions
- [ ] Keyboard shortcuts (Cmd+K / Ctrl+K)

**Estimate:** 6-8 hours

#### 14. Keyboard Shortcuts
**Proposed:**
- [ ] `?` - Show keyboard shortcuts help
- [ ] `n` - Create new streamer
- [ ] `/` - Focus search
- [ ] `Esc` - Close modals
- [ ] Arrow keys - Navigate lists

**Estimate:** 3-4 hours

#### 15. Performance Monitoring
**Task:**
- [ ] Add performance metrics tracking
- [ ] Implement Core Web Vitals monitoring
- [ ] Add bundle size tracking
- [ ] Monitor animation frame rates

**Estimate:** 4-5 hours

---

## 📊 Updated Status Summary

### Completed Issues: 34/59 (58%) ✅

**Session Breakdown:**
- Session 1-3: 16 issues
- Session 4: 1 issue (Last Stream Info)
- Session 5: 5 issues (VideoCard mobile, Settings consistency, Animation toggle, About links, Advanced tab)
- Session 6 Initial: 6 issues (PWA Panel, Sidebar, VideosView, StreamersView)
- Session 6 Extended: 6 issues (StreamerDetailView, HomeView, SettingsView, VideoPlayerView, SCSS Migration x2)

### Remaining Issues: 25 (42%)

**Priority Breakdown:**
- 🔴 High Priority: 1 (AdminView mobile tables)
- 🟡 Medium Priority: 4 (Spacing, Color, Border-radius, Animation audits)
- 🟢 Low Priority: 6 (Touch targets, iOS zoom, Accessibility, Theme audits)
- 🔵 Future: 5 (PWA, Notifications, Search, Keyboard, Performance)
- Original backlog: ~9 (from initial 59 issues)

### Estimated Remaining Work:
- **High Priority:** 2-3 hours
- **Medium Priority:** 9-13 hours
- **Low Priority:** 13-19 hours
- **Future Enhancements:** 20-27 hours
- **TOTAL:** ~44-62 hours

---

## 🎯 Next Session Recommendations

### Immediate (Next 2-3 Hours):
1. ✅ Complete AdminView mobile tables (1-2 hours)
2. Global spacing audit (1-2 hours)

### Short-term (Next Week):
1. Color & border-radius audits (4-6 hours)
2. Touch target & iOS zoom audits (3-4 hours)
3. Animation performance review (2-3 hours)

### Medium-term (Next Month):
1. Accessibility improvements (4-5 hours)
2. Theme audits (dark/light mode) (4-6 hours)
3. Start Future Enhancements (PWA, Notifications)

---

## 📝 Notes for Future Sessions

### SCSS System (CRITICAL - 11. Nov 2025)
**NEVER** use hard-coded `@media (max-width: XXXpx)` again!

**Mandatory Pattern:**
```scss
@use '@/styles/mixins' as m;

@include m.respond-below('sm') {  // < 640px
  .component { /* mobile styles */ }
}
```

**Pre-commit Checklist:**
- [ ] No `@media (max-width: XXXpx)` in diff
- [ ] All responsive styles use SCSS mixins
- [ ] Mixin import at top of `<style>` block
- [ ] Comments explain viewport size

### Design Tokens Priority Order:
1. **SCSS Breakpoints** → Mixins (DONE ✅)
2. **Spacing** → `var(--spacing-*)`
3. **Colors** → `var(--color-*)` or `.status-border-*`
4. **Border-radius** → `var(--border-radius-*)`
5. **Typography** → `var(--font-size-*)`, `var(--font-weight-*)`

### Files with Most Remaining Work:
1. `app/frontend/src/components/admin/AdminPanel.vue` (tables → cards)
2. Global spacing audit (all 50+ Vue files)
3. Global color audit (all Vue files)

---

**Last Updated:** 11. November 2025, 19:30 Uhr  
**Next Review:** Start of next coding session  
**Status:** SCSS Migration Complete ✅ | AdminView Tables In Progress ⏳
   - Commit: 1457e7ca

### Previously Verified as Complete (Session 3):
- ✅ Issue #12: Auto ON button (already uses btn-primary/btn-secondary)
- ✅ Issue #13: Search & Toggle icons (all present)
- ✅ Issue #14: VideosView button icons (all present)
- ✅ Issue #15: SubscriptionsView button icons (all present)

### Status After Session 5:
- **Total Issues:** 59 originally documented
- **Completed:** 24 issues (41%)
- **Remaining:** 35 issues (59%)

### Build Status:
- ✅ All builds successful (3.01s - 3.50s)
- ✅ Zero errors, zero warnings
- ✅ TypeScript type-checks passed
- ✅ PWA: 100 entries precached (~3129 KiB)

### Key Improvements This Session:
- **Mobile UX:** Touch-friendly targets throughout (44-72px)
- **Consistency:** Unified glassmorphism across all settings panels
- **Accessibility:** Animation toggle for motion-sensitive users
- **Responsive:** Optimized layouts for tablets (< 768px) and phones (< 480px)

### Files Modified This Session:
1. `app/frontend/src/components/cards/VideoCard.vue` - Mobile responsive CSS
2. `app/frontend/src/components/settings/NotificationSettingsPanel.vue` - Glassmorphism
3. `app/frontend/src/components/settings/PWAPanel.vue` - Glassmorphism
4. `app/frontend/src/components/settings/FavoritesSettingsPanel.vue` - Glassmorphism
5. `app/frontend/src/components/settings/LoggingPanel.vue` - Glassmorphism
6. `app/frontend/src/views/SettingsView.vue` - Animation toggle + About links
7. `app/frontend/src/styles/main.scss` - `.no-animations` global styles

### Remaining High-Priority Tasks:
1. **Issue #16:** Notifications Settings Table → Card Layout (3-4h)
2. **Issue #17:** Recording Settings Table → Card Layout (3-4h)
3. **Issue #18:** Network Settings Borders/Styling (1-2h)
4. **Issue #20:** Favorite Games Grid Responsive (1h)
5. **Issue #21:** PWA Panel Button Styling (1h)
6. **Issue #24:** Sidebar Active State Consistency (1h)

### Estimated Time Remaining: ~20-25 hours
- **Quick Wins:** ~3-4 hours (6 small tasks)
- **Medium Tasks:** ~10-12 hours (Settings panels, mobile layouts)
- **Bigger Tasks:** ~7-9 hours (Complex redesigns, new features)

---

## 📊 Session 6 Progress Update (11. Nov 2025 - Continuation)

### Tasks Verified as Already Complete:
1. ✅ **Favorite Games Grid** - Already has responsive breakpoints (640px, 1024px, 1440px)
2. ✅ **Notifications Table Mobile** - Already responsive (Session 3, commit 71fbb59b)
3. ✅ **Recording Settings Table Mobile** - Already responsive (Session 3, commit 71fbb59b)
4. ✅ **AddStreamerView** - Verified good styling: GlassCards, divider, mobile responsive < 640px
5. ✅ **Network Settings** - Tab does not exist, task not applicable

### Completed This Session:
1. ✅ **PWA Panel Button Styling** - Enhanced UX (commit 8a51f13f)
   - Removed inline style (margin-left) → .btn-spacing class
   - Increased icon size 16px → 18px
   - Added touch-friendly min-height (40px)
   - Enhanced hover states with translateY + box-shadow
   - Added active state for better touch feedback

### Status After Session 6:
- **Total Issues:** 59 originally documented
- **Completed:** 25 issues (42%)
- **Remaining:** 34 issues (58%)
- **Note:** Many "remaining" tasks were already complete but not documented

### Build Status:
- ✅ Build successful in 2.95s
- ✅ Zero errors, zero warnings
- ✅ TypeScript type-checks passed
- ✅ PWA: 100 entries precached (~3130 KiB)

### Key Findings:
- **Session 3 work was more comprehensive than documented:** Both Notification and Recording Settings tables already have complete mobile-responsive card layouts
- **AddStreamerView is production-ready:** No issues found, good glassmorphism and responsive design
- **Favorite Games Grid:** Already has 4 responsive breakpoints for all screen sizes

### Verified Complete (Not Previously Documented):
- ✅ All Settings panels have consistent glassmorphism (Session 5)
- ✅ All mobile responsive tables in Settings (Session 3)
- ✅ AddStreamerView light mode compatibility
- ✅ Favorite Games responsive grid

### Files Modified This Session:
1. `app/frontend/src/components/settings/PWAPanel.vue` - Button styling improvements
2. `docs/REMAINING_FRONTEND_TASKS.md` - Status updates for Sessions 4-6

### Remaining ACTUAL High-Priority Tasks:
After verification, these are the genuine remaining tasks:
1. **Sidebar Active State Consistency** (1h)
2. **VideosView Filters Mobile** (1-2h)
3. **StreamersView Search Mobile** (1h)
4. **Mobile Menu Improvements** (if any needed)
5. **General Polish & QA** (ongoing)

### Estimated Time Remaining: ~5-10 hours
- **Actual Quick Wins:** ~2-3 hours
- **Polish & Testing:** ~3-5 hours
- **Buffer for discoveries:** ~2 hours

**Note:** Original 20-25h estimate was based on incomplete verification. Most tasks were already done in Sessions 1-3.

---

**End of Document** 📄
