# Global Design System Consistency Audit & Fixes

## 🔴 Priority: CRITICAL
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 6-8 hours  
**Sprint:** Sprint 3: Design Polish  
**Impact:** CRITICAL - Brand consistency, professional appearance

---

## 📝 Problem Description

### Current State: Inconsistent Design Throughout Application

**Critical Issues Identified:**

#### 1. **Light Mode Broken in Multiple Places**
- ❌ Settings tables completely white background (no contrast)
- ❌ Notifications checkboxes dark in light mode
- ❌ Bell notification count unreadable (white text on light background)
- ❌ Various elements don't respect theme properly

#### 2. **Button Styles Inconsistent**
- ❌ Notification settings buttons: Different hover effect, different design
- ❌ Recording settings buttons: Not using global button classes
- ❌ "Enable All" / "Disable All" buttons: Own custom styling
- ❌ Action buttons (On/Off toggles): Mixed designs

#### 3. **Card/Panel Designs Mixed**
- ❌ Notification settings panel: Different card design than others
- ❌ Recording settings panel: Different from notification panel
- ❌ Streamer cards: Different styling than settings cards
- ❌ No consistent `.card` class usage

#### 4. **Form Elements Not Standardized**
- ❌ Checkboxes: Multiple designs (dark in light mode, different sizes)
- ❌ Dropdowns: Different border colors (black outline but gray border)
- ❌ Inputs: Inconsistent padding, font sizes
- ❌ Select elements: Sharp vs blurred rendering

#### 5. **Navigation/Sidebar Inconsistencies**
- ❌ Main sidebar (Streamers/Videos/Subs/Settings): Different design than Settings sidebar
- ❌ Settings sidebar: Own styling, not matching main navigation
- ❌ Hover states: Text turns white in buttons (wrong)
- ❌ Active states: Different indicators

#### 6. **Icon Issues**
- ❌ Settings sidebar: Missing icons (Notifications, Recording, Proxy, etc.)
- ❌ Top-right icons (Jobs, Bell, Theme, Logout): Different designs each
- ❌ Bell notification badge: Unreadable in light mode

#### 7. **Table/List Inconsistencies**
- ❌ Recording settings: Explainer texts break layout (no tooltips)
- ❌ Notification settings: Different table design
- ❌ Column headers: Inconsistent spacing, alignment
- ❌ Table cells: Different padding across tables

#### 8. **Filter/View Controls**
- ❌ Grid/List toggle buttons: Blurry rendering, unequal sizes
- ❌ "All/Live/Offline" filter badges: Different font weights/colors
- ❌ Filter buttons: Inconsistent hover states

#### 9. **Action Menus (Three Dots)**
- ❌ Dropdown menu: Black dots but gray outline
- ❌ Menu items: Not using global hover states
- ❌ Inconsistent positioning

#### 10. **Typography Inconsistencies**
- ❌ Font weights different across sections
- ❌ Font sizes not following scale
- ❌ Line heights inconsistent
- ❌ Text colors not using CSS variables

---

## 🎯 Requirements

### Design System Enforcement

**ALL components MUST use:**
1. **Global CSS Variables** from `_variables.scss`
2. **Global Utility Classes** from `_utilities.scss`
3. **Global Button Classes** (`.btn`, `.btn-primary`, `.btn-secondary`)
4. **Global Form Classes** (`.form-group`, `.form-input`, `.checkbox`)
5. **Global Card Classes** (`.card`, `.card-elevated`)

### Theme Support

**BOTH light and dark themes MUST:**
- Use CSS variables for colors (no hardcoded hex values)
- Have readable text contrast (WCAG AA minimum)
- Properly style all interactive elements
- Show clear hover/active/focus states

---

## 📋 Detailed Issues & Fixes

### Issue Group 1: Light Mode Fixes (HIGH PRIORITY)

#### 1.1 Settings Tables Light Mode
**Problem:** White background, no contrast, unreadable
**Location:** 
- `NotificationSettingsPanel.vue`
- `RecordingSettingsPanel.vue`
- `StreamerNotificationsTable.vue`

**Fix Required:**
```scss
// ❌ WRONG: Hardcoded background
.settings-table {
  background: #ffffff; // Only works in light mode
}

// ✅ CORRECT: Use CSS variable
.settings-table {
  background: var(--bg-secondary); // Works in both themes
  border: 1px solid var(--border-color);
}
```

**Acceptance Criteria:**
- [ ] Table background uses `var(--bg-secondary)`
- [ ] Table borders use `var(--border-color)`
- [ ] Text uses `var(--text-primary)` / `var(--text-secondary)`
- [ ] Readable in BOTH light and dark mode

---

#### 1.2 Checkboxes Light Mode
**Problem:** Checkboxes dark in light mode, can't see state
**Location:** `NotificationSettingsPanel.vue`

**Fix Required:**
```scss
// ❌ WRONG: Custom checkbox styling
input[type="checkbox"] {
  background: #2d2d35; // Always dark
  border: 1px solid #3d3d45;
}

// ✅ CORRECT: Use global checkbox class
<input type="checkbox" class="checkbox" />

// From _utilities.scss:
.checkbox {
  background: var(--input-bg);
  border: 1px solid var(--border-color);
  
  &:checked {
    background: var(--primary-color);
  }
}
```

**Acceptance Criteria:**
- [ ] All checkboxes use `.checkbox` class
- [ ] Visible in light mode (light background)
- [ ] Visible in dark mode (dark background)
- [ ] Checked state clearly distinguishable

---

#### 1.3 Bell Notification Badge Light Mode
**Problem:** White text on light background (unreadable)
**Location:** `AppHeader.vue` or `TopNavigation.vue`

**Fix Required:**
```scss
// ❌ WRONG: Always white text
.notification-badge {
  background: var(--danger-color);
  color: #ffffff; // Unreadable in light mode if badge is light
}

// ✅ CORRECT: Contrast-aware text
.notification-badge {
  background: var(--danger-color);
  color: var(--text-on-danger); // White on red (readable in both themes)
}
```

**Acceptance Criteria:**
- [ ] Badge uses `var(--danger-color)` background
- [ ] Text uses `var(--text-on-danger)` or `#ffffff`
- [ ] Readable in light and dark mode
- [ ] Badge positioned correctly

---

### Issue Group 2: Button Consistency (HIGH PRIORITY)

#### 2.1 Notification Settings Buttons
**Problem:** Different hover effect, different design than other buttons
**Location:** `NotificationSettingsPanel.vue`

**Fix Required:**
```vue
<!-- ❌ WRONG: Custom button styling -->
<button class="save-button">Save Settings</button>
<style>
.save-button {
  background: #00bfa5;
  color: white;
  padding: 12px 24px;
  /* Custom hover */
}
</style>

<!-- ✅ CORRECT: Use global button class -->
<button class="btn btn-primary">Save Settings</button>
<!-- No custom styles needed! -->
```

**Affected Buttons:**
- Save Settings
- Test Notification
- Test WebSocket
- Enable All / Disable All

**Acceptance Criteria:**
- [ ] All buttons use `.btn` base class
- [ ] Primary actions use `.btn-primary`
- [ ] Secondary actions use `.btn-secondary`
- [ ] Danger actions use `.btn-danger`
- [ ] Hover states consistent globally

---

#### 2.2 Recording Settings Buttons
**Problem:** Not using global button design
**Location:** `RecordingSettingsPanel.vue`, `StreamerRecordingSettings.vue`

**Affected Buttons:**
- Enable All / Disable All
- Quality dropdowns
- Custom filename inputs

**Acceptance Criteria:**
- [ ] "Enable All" uses `.btn .btn-secondary`
- [ ] "Disable All" uses `.btn .btn-secondary`
- [ ] On/Off toggles use `.toggle-switch` component
- [ ] Consistent spacing (8px gap between buttons)

---

#### 2.3 Action Buttons (On/Off Toggles)
**Problem:** Mixed toggle switch designs
**Location:** Streamer tables, notification tables

**Fix Required:**
```vue
<!-- ❌ WRONG: Multiple toggle designs -->
<button @click="toggle">{{ enabled ? 'On' : 'Off' }}</button>

<!-- ✅ CORRECT: Use ToggleSwitch component -->
<ToggleSwitch v-model="enabled" />
```

**Acceptance Criteria:**
- [ ] All On/Off toggles use `<ToggleSwitch>` component
- [ ] Consistent size (48px width)
- [ ] Smooth animation (300ms transition)
- [ ] Clear on/off states (color + position)

---

### Issue Group 3: Card/Panel Consistency (MEDIUM PRIORITY)

#### 3.1 Settings Panels Card Design
**Problem:** Each settings panel (Notifications, Recording, Proxy) has different card styling

**Fix Required:**
```scss
// ❌ WRONG: Custom card for each panel
.notification-settings {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.recording-settings {
  background: var(--bg-tertiary); // Different!
  border-radius: 8px; // Different!
  padding: 20px; // Different!
  box-shadow: 0 4px 12px rgba(0,0,0,0.2); // Different!
}

// ✅ CORRECT: Use global .card class
.notification-settings,
.recording-settings,
.proxy-settings {
  @extend .card; // Or add class="card" in template
}
```

**Acceptance Criteria:**
- [ ] All settings panels use `.card` class
- [ ] Consistent padding (24px)
- [ ] Consistent border-radius (12px)
- [ ] Consistent shadow (elevation-2)
- [ ] All panels look identical in structure

---

### Issue Group 4: Form Elements (MEDIUM PRIORITY)

#### 4.1 Dropdown/Select Styling
**Problem:** Black outline but gray border, inconsistent
**Location:** Recording settings quality dropdowns, filter dropdowns

**Fix Required:**
```scss
// ❌ WRONG: Mixed borders
select {
  border: 1px solid #000000; // Black
  outline: 2px solid #cccccc; // Gray - confusing!
}

// ✅ CORRECT: Use global form-select class
<select class="form-select">
  <option>Best Available</option>
</select>

// From _utilities.scss:
.form-select {
  border: 1px solid var(--border-color);
  background: var(--input-bg);
  
  &:focus {
    border-color: var(--primary-color);
    outline: none; // Remove default outline
    box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.1);
  }
}
```

**Acceptance Criteria:**
- [ ] All `<select>` elements use `.form-select` class
- [ ] Border color: `var(--border-color)`
- [ ] Focus state: Primary color outline
- [ ] Sharp rendering (no blur)

---

#### 4.2 Recording Settings Explainer Texts
**Problem:** Long texts break layout, need tooltips
**Location:** `RecordingSettingsPanel.vue` - Column headers

**Current:**
```
RECORD | QUALITY | CUSTOM FILENAME
Enable/disable | Select recording | Optional custom
recording for | quality (defaults | filename template
this streamer  | to global setting | for this streamer
               | if empty)        |
```

**Fix Required:**
```vue
<!-- ❌ WRONG: Text in header (breaks layout) -->
<th>
  QUALITY<br>
  <small>Select recording quality...</small>
</th>

<!-- ✅ CORRECT: Tooltip on hover -->
<th>
  QUALITY 
  <IconTooltip text="Select recording quality (defaults to global setting if empty)" />
</th>
```

**Acceptance Criteria:**
- [ ] All explainer texts moved to tooltips
- [ ] Headers only show label + icon
- [ ] Tooltip appears on hover (300ms delay)
- [ ] Tooltip readable (max-width 200px, wraps)

---

### Issue Group 5: Navigation Consistency (HIGH PRIORITY)

#### 5.1 Main Sidebar vs Settings Sidebar
**Problem:** Two different sidebar designs
**Location:** 
- Main: `Sidebar.vue` (Streamers, Videos, Subs, Settings)
- Settings: `SettingsSidebar.vue` (Notifications, Recording, etc.)

**Unify Design:**
```scss
// Both sidebars should use same structure:
.sidebar {
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  
  .sidebar-item {
    padding: 12px 16px;
    border-radius: 8px;
    transition: background 0.2s ease;
    
    &:hover {
      background: var(--bg-hover);
    }
    
    &.active {
      background: var(--bg-active);
      color: var(--primary-color);
    }
  }
}
```

**Acceptance Criteria:**
- [ ] Both sidebars use identical styling
- [ ] Same hover states (background changes, text stays same color)
- [ ] Same active states (primary color + background)
- [ ] Same spacing (12px padding, 8px margin)
- [ ] Icons present in both

---

#### 5.2 Settings Sidebar Missing Icons
**Problem:** Settings sidebar has no icons (Notifications, Recording, Proxy, etc.)
**Location:** `SettingsSidebar.vue`

**Add Icons:**
```vue
<template>
  <div class="settings-sidebar">
    <RouterLink to="/settings/notifications" class="sidebar-item">
      <i class="icon-bell"></i> <!-- ADD ICON -->
      <span>Notifications</span>
    </RouterLink>
    
    <RouterLink to="/settings/recording" class="sidebar-item">
      <i class="icon-video"></i> <!-- ADD ICON -->
      <span>Recording</span>
    </RouterLink>
    
    <RouterLink to="/settings/proxy" class="sidebar-item">
      <i class="icon-network"></i> <!-- ADD ICON -->
      <span>Proxy Management</span>
    </RouterLink>
    
    <!-- ... etc -->
  </div>
</template>
```

**Icons Needed:**
- Notifications → Bell icon
- Recording → Video/Camera icon
- Proxy Management → Network/Globe icon
- Favorite Games → Star icon
- Appearance → Palette/Theme icon
- PWA & Mobile → Mobile icon
- Advanced → Settings/Gear icon (REMOVE - see 5.3)
- About → Info icon

**Acceptance Criteria:**
- [ ] All sidebar items have icons
- [ ] Icons 20px size, 8px margin-right
- [ ] Icons use `var(--text-secondary)` color
- [ ] Active item icon uses `var(--primary-color)`

---

#### 5.3 Remove Advanced Tab
**Problem:** Advanced tab not needed
**Location:** `SettingsSidebar.vue`, `SettingsView.vue`

**Fix Required:**
```vue
<!-- ❌ REMOVE THIS: -->
<RouterLink to="/settings/advanced">Advanced</RouterLink>

<!-- Also remove route and view file -->
```

**Acceptance Criteria:**
- [ ] Advanced tab removed from sidebar
- [ ] Route `/settings/advanced` removed
- [ ] `AdvancedSettingsView.vue` deleted (if exists)

---

#### 5.4 Sidebar Hover Text Color
**Problem:** Hover makes text white in buttons (wrong)
**Location:** Both sidebars

**Fix Required:**
```scss
// ❌ WRONG: Text changes color on hover
.sidebar-item:hover {
  background: var(--bg-hover);
  color: #ffffff; // Wrong!
}

// ✅ CORRECT: Only background changes
.sidebar-item:hover {
  background: var(--bg-hover);
  // Text color stays var(--text-primary)
}

.sidebar-item.active {
  background: var(--bg-active);
  color: var(--primary-color); // Only active items change text color
}
```

**Acceptance Criteria:**
- [ ] Hover only changes background
- [ ] Text color remains `var(--text-primary)` on hover
- [ ] Only active items have `var(--primary-color)` text

---

### Issue Group 6: Top Navigation Icons (MEDIUM PRIORITY)

#### 6.1 Top-Right Icons Inconsistent
**Problem:** Jobs, Bell, Theme, Logout buttons all different designs
**Location:** `AppHeader.vue` or `TopNavigation.vue`

**Unify Design:**
```vue
<template>
  <div class="top-nav-actions">
    <!-- All buttons should use same structure -->
    <button class="icon-button" title="Jobs">
      <i class="icon-briefcase"></i>
      <span v-if="jobCount > 0" class="badge">{{ jobCount }}</span>
    </button>
    
    <button class="icon-button" title="Notifications">
      <i class="icon-bell"></i>
      <span v-if="notificationCount > 0" class="badge badge-danger">{{ notificationCount }}</span>
    </button>
    
    <button class="icon-button" title="Toggle Theme">
      <i :class="isDark ? 'icon-sun' : 'icon-moon'"></i>
    </button>
    
    <button class="btn btn-danger" @click="logout">Logout</button>
  </div>
</template>

<style scoped>
.icon-button {
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: transparent;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s ease;
  
  &:hover {
    background: var(--bg-hover);
  }
  
  .badge {
    position: absolute;
    top: 4px;
    right: 4px;
    min-width: 18px;
    height: 18px;
    border-radius: 9px;
    background: var(--danger-color);
    color: #ffffff;
    font-size: 11px;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
</style>
```

**Acceptance Criteria:**
- [ ] All icon buttons same size (40x40px)
- [ ] Same hover state (background change)
- [ ] Badges positioned consistently
- [ ] Badge readable in light mode (white text on red)

---

### Issue Group 7: Filter & View Controls (LOW PRIORITY)

#### 7.1 Grid/List Toggle Buttons
**Problem:** Blurry rendering, unequal sizes
**Location:** `StreamersView.vue` (top-right toggle)

**Fix Required:**
```vue
<template>
  <div class="view-toggle">
    <button
      class="toggle-button"
      :class="{ active: viewMode === 'grid' }"
      @click="viewMode = 'grid'"
      aria-label="Grid view"
    >
      <i class="icon-grid"></i>
    </button>
    <button
      class="toggle-button"
      :class="{ active: viewMode === 'list' }"
      @click="viewMode = 'list'"
      aria-label="List view"
    >
      <i class="icon-list"></i>
    </button>
  </div>
</template>

<style scoped>
.view-toggle {
  display: flex;
  gap: 4px;
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 4px;
}

.toggle-button {
  width: 36px; // Equal sizes
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s ease;
  
  i {
    font-size: 18px;
    color: var(--text-secondary);
  }
  
  &:hover {
    background: var(--bg-hover);
  }
  
  &.active {
    background: var(--primary-color);
    
    i {
      color: #ffffff;
    }
  }
}
</style>
```

**Acceptance Criteria:**
- [ ] Both buttons exactly 36x36px
- [ ] Sharp icon rendering (not blurry)
- [ ] Active state clear (primary color background)
- [ ] Smooth transitions

---

#### 7.2 Filter Badges (All/Live/Offline)
**Problem:** Different font weights, colors inconsistent
**Location:** `StreamersView.vue` filter badges

**Fix Required:**
```scss
// ❌ WRONG: Mixed styles
.filter-badge {
  font-weight: 500; // Some use 400, some 600
  color: var(--text-primary); // Some hardcode colors
}

// ✅ CORRECT: Consistent badge styling
.filter-badge {
  padding: 8px 16px;
  border-radius: 20px;
  background: var(--bg-secondary);
  font-weight: 500; // Consistent
  font-size: 14px;
  color: var(--text-secondary);
  border: 1px solid transparent;
  transition: all 0.2s ease;
  
  &:hover {
    background: var(--bg-hover);
  }
  
  &.active {
    background: var(--primary-color);
    color: #ffffff;
    border-color: var(--primary-color);
  }
  
  .count {
    margin-left: 6px;
    font-weight: 600;
  }
}
```

**Acceptance Criteria:**
- [ ] All badges same font-weight (500)
- [ ] All badges same font-size (14px)
- [ ] Count badges font-weight 600
- [ ] Active badge clearly distinguishable

---

### Issue Group 8: Action Menus (THREE DOTS) (LOW PRIORITY)

#### 8.1 Dropdown Menu Styling
**Problem:** Black dots but gray outline, inconsistent
**Location:** Streamer cards, stream cards (action menus)

**Fix Required:**
```vue
<template>
  <div class="dropdown">
    <button class="dropdown-trigger" @click="toggleMenu">
      <i class="icon-more-vertical"></i>
    </button>
    
    <div v-if="isOpen" class="dropdown-menu">
      <button class="dropdown-item">Edit</button>
      <button class="dropdown-item">Force Record</button>
      <button class="dropdown-item dropdown-item-danger">Delete</button>
    </div>
  </div>
</template>

<style scoped>
.dropdown-trigger {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid var(--border-color); // Consistent border
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  
  i {
    color: var(--text-secondary); // Gray dots
  }
  
  &:hover {
    background: var(--bg-hover);
  }
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  min-width: 160px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  
  .dropdown-item {
    width: 100%;
    padding: 10px 16px;
    text-align: left;
    background: none;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    transition: background 0.2s ease;
    
    &:hover {
      background: var(--bg-hover);
    }
    
    &.dropdown-item-danger {
      color: var(--danger-color);
      
      &:hover {
        background: rgba(var(--danger-rgb), 0.1);
      }
    }
  }
}
</style>
```

**Acceptance Criteria:**
- [ ] Trigger button: Gray border (not black)
- [ ] Icon color: `var(--text-secondary)` (gray)
- [ ] Menu items: Global hover state
- [ ] Danger items: Red text + red background on hover

---

## 📂 Files to Audit & Modify

### High Priority Files (Fix First)

**Settings Pages:**
- `app/frontend/src/views/SettingsView.vue`
- `app/frontend/src/components/settings/NotificationSettingsPanel.vue`
- `app/frontend/src/components/settings/RecordingSettingsPanel.vue`
- `app/frontend/src/components/settings/StreamerNotificationsTable.vue`
- `app/frontend/src/components/settings/StreamerRecordingSettings.vue`
- `app/frontend/src/components/settings/SettingsSidebar.vue`

**Navigation:**
- `app/frontend/src/components/Sidebar.vue`
- `app/frontend/src/components/AppHeader.vue` (or `TopNavigation.vue`)

**Global Styles:**
- `app/frontend/src/styles/main.scss` (theme variables)
- `app/frontend/src/styles/_utilities.scss` (utility classes)
- `app/frontend/src/styles/_variables.scss` (CSS variables)

### Medium Priority Files

**Streamer Management:**
- `app/frontend/src/views/StreamersView.vue`
- `app/frontend/src/components/StreamerCard.vue`

**Stream History:**
- `app/frontend/src/views/VideosView.vue`
- `app/frontend/src/components/StreamCard.vue`

### Low Priority Files

**Proxy Management:**
- `app/frontend/src/views/ProxyManagementView.vue`
- `app/frontend/src/components/ProxyCard.vue`

---

## ✅ Acceptance Criteria

### Global Requirements
- [ ] **ALL** components use CSS variables (no hardcoded colors)
- [ ] **ALL** buttons use global `.btn` classes
- [ ] **ALL** forms use global `.form-*` classes
- [ ] **ALL** cards use global `.card` class
- [ ] **BOTH** themes work perfectly (light + dark)

### Light Mode Requirements
- [ ] All text readable (min contrast ratio 4.5:1)
- [ ] All backgrounds use `var(--bg-*)` variables
- [ ] All borders use `var(--border-color)`
- [ ] Checkboxes visible (light background)
- [ ] Notification badge readable

### Dark Mode Requirements
- [ ] All text readable (min contrast ratio 4.5:1)
- [ ] No elements "disappear" (black on black)
- [ ] Hover states visible
- [ ] Focus states visible

### Button Consistency
- [ ] All buttons same height (40px default)
- [ ] All primary buttons use `.btn-primary`
- [ ] All secondary buttons use `.btn-secondary`
- [ ] All danger buttons use `.btn-danger`
- [ ] Hover states consistent globally

### Card Consistency
- [ ] All cards same border-radius (12px)
- [ ] All cards same padding (24px)
- [ ] All cards same shadow (elevation-2)
- [ ] All cards use `var(--bg-secondary)` background

### Navigation Consistency
- [ ] Both sidebars identical styling
- [ ] All sidebar items have icons
- [ ] Hover only changes background (not text color)
- [ ] Active state uses primary color

### Form Consistency
- [ ] All inputs use `.form-input` class
- [ ] All selects use `.form-select` class
- [ ] All checkboxes use `.checkbox` class
- [ ] All labels use `.form-label` class

### Typography Consistency
- [ ] Font weights follow scale (400, 500, 600, 700)
- [ ] Font sizes follow scale (12px, 14px, 16px, 18px, 20px, 24px)
- [ ] Line heights consistent (1.5 for body, 1.2 for headings)
- [ ] All text uses `var(--text-primary)` or `var(--text-secondary)`

---

## 🧪 Testing Checklist

### Theme Testing
- [ ] Switch to light mode → All elements visible and readable
- [ ] Switch to dark mode → All elements visible and readable
- [ ] Toggle theme 10x → No flicker or broken styles

### Component Testing
- [ ] Open each settings page → All consistent styling
- [ ] Hover all buttons → Same hover effect everywhere
- [ ] Click all dropdowns → Same styling everywhere
- [ ] Check all tables → Same styling everywhere
- [ ] Check all cards → Same styling everywhere

### Responsive Testing
- [ ] Desktop (1920px) → All elements properly sized
- [ ] Laptop (1440px) → No layout breaks
- [ ] Tablet (768px) → Proper responsive behavior
- [ ] Mobile (375px) → All elements accessible

### Browser Testing
- [ ] Chrome → Perfect rendering
- [ ] Firefox → Perfect rendering
- [ ] Safari → Perfect rendering
- [ ] Edge → Perfect rendering

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Complete component reference
- `.github/instructions/frontend.instructions.md` - SCSS patterns

**Global Styles:**
- `_variables.scss` - All CSS variables
- `_utilities.scss` - All utility classes (buttons, cards, forms)
- `_mixins.scss` - Reusable SCSS mixins

**Component Patterns:**
- Button patterns: `.btn`, `.btn-primary`, `.btn-secondary`
- Card patterns: `.card`, `.card-elevated`
- Form patterns: `.form-group`, `.form-input`, `.form-select`
- Badge patterns: `.badge`, `.badge-success`, `.badge-danger`

---

## 📊 Estimated Breakdown

### Phase 1: Light Mode Fixes (2 hours)
- Settings tables background
- Checkboxes styling
- Bell notification badge
- Text contrast issues

### Phase 2: Button Consistency (2 hours)
- Replace all custom buttons with global classes
- Notification settings buttons
- Recording settings buttons
- Action buttons (On/Off toggles)

### Phase 3: Navigation Consistency (1.5 hours)
- Unify sidebar designs
- Add missing icons
- Fix hover states
- Remove Advanced tab

### Phase 4: Form Consistency (1.5 hours)
- Standardize dropdowns
- Move explainer texts to tooltips
- Standardize checkboxes
- Standardize inputs

### Phase 5: Card & Panel Consistency (1 hour)
- Apply `.card` class globally
- Unify padding and spacing
- Consistent shadows

### Phase 6: Testing & Polish (1 hour)
- Test both themes
- Test all browsers
- Fix edge cases
- Final QA

**Total:** 6-8 hours

---

## 🎯 Success Criteria

**Task Complete When:**
- ✅ Light mode 100% usable (no white-on-white)
- ✅ Dark mode 100% usable (no black-on-black)
- ✅ All buttons use global classes
- ✅ All cards use global classes
- ✅ All forms use global classes
- ✅ Both sidebars identical design
- ✅ All icons present
- ✅ No custom styling (except component-specific)

**Production Ready:**
- ✅ Pass WCAG AA contrast requirements
- ✅ Pass cross-browser testing
- ✅ Pass responsive testing
- ✅ User testing confirms consistency

---

## 🤖 Agent Recommendation

**Primary Agent:** `refactor-specialist`  
**Backup Agent:** `feature-builder`

**Why refactor-specialist:**
- Global CSS refactoring expertise
- Design system enforcement
- Code quality improvements
- Systematic approach to consistency

**Copilot Command:**
```bash
@copilot with agent refactor-specialist: Audit all components and enforce global design system consistency (CSS variables, utility classes, button classes, card classes)
```

---

## 🚨 Critical Reminders

1. **DO NOT** create new custom styles
2. **ALWAYS** use CSS variables from `_variables.scss`
3. **ALWAYS** use utility classes from `_utilities.scss`
4. **TEST** in both light and dark mode
5. **VERIFY** WCAG contrast ratios

This is a **systematic cleanup** - touch EVERY component to ensure consistency!
