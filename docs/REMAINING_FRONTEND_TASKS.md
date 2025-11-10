# Remaining Frontend Tasks - Continuation Guide
**Date:** 10. November 2025  
**Status:** 🟡 In Progress  
**Session:** Day 1 Complete - 5/35 Issues Fixed

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
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH - Blocks mobile usability  
**Estimated Time:** 3-4 hours

**Problem:**
- Logout button disappears off right edge on mobile
- No way to access theme toggle on small screens
- Header too crowded on < 768px

**Current State:**
```vue
<!-- App.vue Header -->
<header class="app-header">
  <router-link to="/" class="app-logo">StreamVault</router-link>
  <div class="header-right">
    <BackgroundQueueMonitor />  <!-- + JOBS 0 -->
    <NotificationBell />
    <ThemeToggle />  <!-- Overflows -->
    <button @click="logout" class="logout-btn">Logout</button>  <!-- DISAPPEARS -->
  </div>
</header>
```

**Proposed Solution:**
```vue
<!-- Mobile (< 768px) -->
<header class="app-header">
  <button @click="toggleMobileMenu" class="hamburger-btn">
    <svg><use href="#icon-menu" /></svg>
  </button>
  <router-link to="/" class="app-logo">StreamVault</router-link>
  <BackgroundQueueMonitor />  <!-- Keep visible -->
</header>

<!-- Mobile Menu Overlay (Teleport to body) -->
<Teleport to="body">
  <div v-if="showMobileMenu" class="mobile-menu-overlay" @click.self="closeMobileMenu">
    <div class="mobile-menu">
      <button @click="closeMobileMenu" class="close-btn">×</button>
      <nav class="mobile-nav">
        <NotificationBell />
        <ThemeToggle />
        <button @click="logout" class="menu-logout-btn">
          <svg><use href="#icon-log-out" /></svg>
          Logout
        </button>
      </nav>
    </div>
  </div>
</Teleport>

<!-- Desktop (≥ 768px) - Keep current layout -->
```

**Files to Modify:**
1. `app/frontend/src/App.vue`
   - Add hamburger button (mobile only)
   - Add mobile menu overlay (Teleport)
   - Add responsive CSS (@media queries)
   - Add state: `const showMobileMenu = ref(false)`

2. **Optional:** Create `app/frontend/src/components/MobileMenu.vue`
   - Reusable mobile menu component
   - Cleaner separation of concerns

**Implementation Steps:**
1. Add hamburger icon to SVG sprite (if missing)
2. Add `showMobileMenu` state to App.vue
3. Add hamburger button (v-if="isMobile")
4. Create mobile menu overlay with Teleport
5. Add CSS transitions (slide-in from right)
6. Add click-outside handler
7. Test on mobile viewport (375px, 414px, 768px)

**Design Specs:**
- Hamburger: 44x44px touch target, top-left corner
- Menu: Slide in from right, 280px width
- Background: Glassmorphism with backdrop blur
- Animation: 300ms ease-out
- Close on: Outside click, item click, escape key

---

### Issue #8: Design System Colors (CRITICAL)
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH - Breaks design consistency  
**Estimated Time:** 1-2 hours

**Problem:**
Hardcoded colors in `SidebarNav.vue` break design system:

```scss
// WRONG: Hardcoded colors from previous fix
[data-theme="light"] & {
  background: #14b8a6;  // Hardcoded teal-500
  color: white;
  border-left: 4px solid #0d9488;  // Hardcoded teal-600
}
```

**Why This is Bad:**
- Design system uses CSS variables for theming
- Hardcoded values can't be changed globally
- Inconsistent with COMPLETE_DESIGN_OVERHAUL_SUMMARY.md
- Breaks if design colors change

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
**Status:** 🔴 NOT STARTED  
**Priority:** HIGH - Usability issue  
**Estimated Time:** 2-3 hours

**Problem:**
Multiple buttons in Settings view have white text on light backgrounds (invisible).

**Affected Components:**

**1. Subscription Management View**
File: `app/frontend/src/views/SubscriptionsView.vue` (or similar)

Buttons with issues:
- "Refresh" button
- "Resubscribe All" button - WHITE text (invisible in light mode)
- "Delete All" button - WHITE text (invisible in light mode)

**Current Code (BROKEN):**
```vue
<button class="btn-refresh">Refresh</button>  <!-- Looks different from others -->
<button class="btn-resubscribe">Resubscribe All</button>  <!-- White text -->
<button class="btn-delete-all">Delete All</button>  <!-- White text -->
```

**Fixed Code:**
```vue
<button class="btn btn-secondary">
  <svg class="icon"><use href="#icon-refresh" /></svg>
  Refresh
</button>
<button class="btn btn-primary">
  <svg class="icon"><use href="#icon-check-all" /></svg>
  Resubscribe All
</button>
<button class="btn btn-danger">
  <svg class="icon"><use href="#icon-trash" /></svg>
  Delete All
</button>
```

**CSS Classes Needed:**
```scss
// In _components.scss or similar
.btn {
  // Base button styles
  padding: var(--spacing-3) var(--spacing-5);
  border-radius: var(--radius-lg);
  font-weight: v.$font-medium;
  transition: all v.$duration-200 v.$ease-out;
  
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  
  .icon {
    width: 18px;
    height: 18px;
  }
}

.btn-secondary {
  background: var(--background-card);
  color: var(--text-primary);  // THEME-AWARE
  border: 1px solid var(--border-color);
  
  &:hover {
    background: var(--background-hover);
  }
}

.btn-primary {
  background: var(--primary-color);
  color: white;  // Always white on primary
  border: none;
  
  &:hover {
    background: var(--primary-600);
  }
}

.btn-danger {
  background: var(--danger-color);
  color: white;  // Always white on danger
  border: none;
  
  &:hover {
    background: var(--danger-600);
  }
}
```

**2. Settings Notification Tab**
File: `app/frontend/src/views/SettingsView.vue` (Notifications section)

Issues:
- Buttons not readable
- Buttons offset/misaligned
- Inconsistent borders

**3. Favorite Games Search**
File: `app/frontend/src/views/SettingsView.vue` (Favorite Games section)

Issue:
- Search input has black background in light mode

**Fix:**
```scss
.search-input {
  background: var(--background-card);  // NOT hardcoded black
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}
```

**Implementation Steps:**
1. Find all affected button classes
2. Replace hardcoded colors with CSS variables
3. Add proper button variants (primary, secondary, danger)
4. Test in both light and dark mode
5. Verify contrast ratios (WCAG AA: 4.5:1)

**Files to Search:**
```bash
grep -r "white.*text\|color: white\|color: #fff" app/frontend/src/views/SettingsView.vue
grep -r "background: black\|background: #000" app/frontend/src/views/SettingsView.vue
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

## 🟢 LOW PRIORITY / NICE TO HAVE

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

**Good luck! 🚀**
