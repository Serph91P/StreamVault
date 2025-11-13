# Settings Tables Mobile Responsive

## 🟡 Priority: HIGH
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 6-8 hours  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** HIGH - 50%+ of users on mobile, settings currently unusable

---

## 📝 Problem Description

### Current State (Mobile Broken)

**Issue:** Settings pages use desktop-only table layouts that break on mobile devices.

**Affected Settings Panels:**
1. **Notification Settings** - Apprise URLs table
2. **Recording Settings** - Quality/format configuration table
3. **Proxy Settings** - Proxy list management (when implemented)
4. **General Settings** - Various form grids and tables
5. **Cleanup Settings** - Policy configuration tables

**User Experience on Mobile (< 768px):**
- ❌ Tables overflow horizontally → requires scrolling
- ❌ Text too small to read (8-10px effective)
- ❌ Touch targets too small (< 44px) → hard to tap buttons
- ❌ Form fields don't stack vertically
- ❌ Action buttons cramped together
- ❌ No clear visual hierarchy
- ❌ Unusable for configuration on phones/tablets

**Example: Notification Settings Table (Mobile)**
```
┌─────────────────────────────────────┐
│ [Tiny Text] [URL] [Tiny Button] ... │ ← Overflows screen
└─────────────────────────────────────┘
     ↑ Requires horizontal scrolling
     ↑ Touch targets ~20px (too small)
```

**Impact:**
- Users **cannot configure** StreamVault on mobile devices
- Must switch to desktop to change settings
- Poor onboarding experience for mobile users
- Violates PWA mobile-first principles

---

## 🎯 Requirements

### Responsive Transformation Pattern

**Desktop (≥ 768px):** Traditional table layout
**Mobile (< 768px):** Card-based layout with stacked fields

### Design Goals

1. **Touch-Friendly Targets**
   - All buttons minimum 44x44px
   - Adequate spacing between interactive elements (16px min)
   - Large tap areas for checkboxes/toggles

2. **Readable Text**
   - Minimum 16px font size (prevents iOS zoom)
   - Clear visual hierarchy
   - Labels above fields (not beside)

3. **Card Transformations**
   - Each table row becomes a card
   - Fields stack vertically
   - Clear visual separation between cards
   - Glassmorphism design system applied

4. **No Horizontal Scrolling**
   - All content fits screen width
   - Long URLs wrap or truncate with ellipsis
   - Forms adapt to narrow viewports

5. **Consistent Patterns**
   - Reuse existing mobile transformation patterns
   - Follow Design System guidelines
   - Match HomeView/StreamersView card styles

---

## 📋 Components Requiring Updates

### 1. NotificationSettingsPanel
**File:** `app/frontend/src/components/settings/NotificationSettingsPanel.vue`

**Current Issues:**
- Apprise URLs table with 3 columns (Service, URL, Actions)
- No mobile transformation
- Delete buttons too small
- URLs overflow on small screens

**Requirements:**
- Transform table rows → cards on mobile
- Stack fields vertically: Service name → URL → Actions
- Increase delete button size to 48px height
- Truncate long URLs with ellipsis
- Add clear visual separation between cards

---

### 2. RecordingSettingsPanel
**File:** `app/frontend/src/components/settings/RecordingSettingsPanel.vue`

**Current Issues:**
- Quality/format dropdown too narrow on mobile
- Codec selection table not responsive
- Save button small and hard to tap

**Requirements:**
- Full-width form fields on mobile
- Larger dropdowns (48px height)
- Save button spans full width on mobile
- Clear labels above each field

---

### 3. GeneralSettingsPanel
**File:** `app/frontend/src/components/settings/GeneralSettingsPanel.vue`

**Current Issues:**
- Form grid layout breaks on narrow screens
- Input fields cramped
- No vertical stacking

**Requirements:**
- Single column layout on mobile
- Full-width inputs
- Adequate spacing between fields (16px)
- Large toggle switches (44px touch target)

---

### 4. CleanupSettingsPanel
**File:** `app/frontend/src/components/settings/CleanupSettingsPanel.vue`

**Current Issues:**
- Cleanup policy table not responsive
- Number inputs too small
- Checkbox targets tiny

**Requirements:**
- Transform table → cards on mobile
- Larger input fields
- Clear checkbox labels with large tap areas

---

## 🎨 Design System Integration

### Mobile Breakpoint Mixin

Use existing SCSS breakpoint mixins from Design System:

```scss
@use '@/styles/mixins' as m;

// Apply mobile styles below 768px
@include m.respond-below('md') {
  // Mobile transformations here
}
```

### Card Transformation Pattern

**Desktop:** Traditional table
**Mobile:** Stacked cards with labels

Pattern to follow (from HomeView/StreamersView):

```vue
<table class="settings-table">
  <thead>
    <!-- Desktop headers -->
  </thead>
  <tbody>
    <tr v-for="item in items" :key="item.id" class="mobile-card">
      <td data-label="Label 1">{{ item.field1 }}</td>
      <td data-label="Label 2">{{ item.field2 }}</td>
      <td data-label="Actions">
        <button class="btn btn-danger">Delete</button>
      </td>
    </tr>
  </tbody>
</table>
```

### Touch Target Standards

- **Minimum:** 44x44px (Apple HIG / Android Material)
- **Recommended:** 48x48px
- **Spacing:** 16px minimum between interactive elements

### Typography

- **Body text:** 16px minimum (prevents iOS auto-zoom)
- **Labels:** 14px minimum, semibold
- **Buttons:** 16px minimum

---

## ✅ Acceptance Criteria

### Functional Requirements
- [ ] All settings tables transform to cards on mobile (< 768px)
- [ ] No horizontal scrolling on any settings page
- [ ] All buttons minimum 44x44px on mobile
- [ ] Form fields full-width on mobile
- [ ] Long URLs truncate with ellipsis
- [ ] Clear visual hierarchy maintained

### Visual Requirements
- [ ] Matches Design System glassmorphism style
- [ ] Consistent card spacing (16px)
- [ ] Clear labels above each field
- [ ] Adequate padding within cards (16px)
- [ ] Smooth animations when resizing

### Testing Checklist
- [ ] Test on iPhone SE (375px width)
- [ ] Test on iPhone 14 Pro (393px width)
- [ ] Test on iPad (768px width)
- [ ] Test on desktop (1920px width)
- [ ] Test landscape orientation on phones
- [ ] Verify touch targets with pointer device
- [ ] Test form submission works correctly
- [ ] Test delete actions work on mobile
- [ ] Verify no layout shifts on load
- [ ] Check dark/light theme compatibility

---

## 📖 References

**Design System Documentation:**
- `docs/DESIGN_SYSTEM.md` - Mobile-first patterns, breakpoints, touch targets
- `.github/instructions/frontend.instructions.md` - SCSS mixin usage

**Existing Mobile Patterns:**
- `app/frontend/src/views/HomeView.vue` - Stream cards on mobile
- `app/frontend/src/views/StreamersView.vue` - Streamer cards on mobile
- `app/frontend/src/views/VideosView.vue` - Video cards on mobile

**Related Tasks:**
- Issue #9: Video Player Controls Mobile
- Issue #10: Watch View Mobile Responsive
- Issue #11: Streamer Cards Mobile Spacing
  .mobile-cards {
    display: block;
    
    thead { display: none; }
    tbody { display: block; }
    
    .mobile-card {
      display: block;
      margin-bottom: 16px;
      padding: 16px;
      background: var(--bg-secondary);
      border-radius: var(--border-radius-md);
      border: 1px solid var(--border-color);
    }
    
    td {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border: none;
      
      &::before {
        content: attr(data-label);
        font-weight: 600;
        color: var(--text-secondary);
        margin-right: 8px;
      }
      
      &.url-cell {
        flex-direction: column;
        word-break: break-all;
        
        &::before {
          margin-bottom: 4px;
        }
      }
      
      &[data-label="Actions"] {
        justify-content: flex-end;
        margin-top: 8px;
        
        &::before {
          display: none;
        }
        
        button {
          width: 100%;
          min-height: 48px;
        }
      }
    }
  }
}
</style>
```

---

### 2. RecordingSettingsPanel (2-3 hours)

**File:** `app/frontend/src/components/settings/RecordingSettingsPanel.vue`

**Changes:**
- Stack quality/format selections vertically
- Transform settings grid → single column
- Increase input sizes (16px font for iOS)
- Touch-friendly toggles

**Form Grid Transformation:**
```scss
.settings-form {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  
  @include m.respond-below('md') {
    grid-template-columns: 1fr;  // Stack on mobile
    
    .form-input {
      font-size: 16px !important;  // iOS zoom prevention
      min-height: 48px;
    }
    
    .form-label {
      font-size: 14px;
      margin-bottom: 8px;
    }
  }
}
```

---

### 3. General Touch Target Optimization (1-2 hours)

**All Settings Components:**

```scss
// Apply to ALL settings panels
@include m.respond-below('md') {
  // Buttons
  .btn {
    min-height: 48px;
    padding: 12px 16px;
    font-size: 16px;
  }
  
  // Inputs
  input, select, textarea {
    min-height: 48px;
    font-size: 16px !important;  // iOS zoom prevention
    padding: 12px;
  }
  
  // Toggles/Switches
  .toggle-switch {
    min-width: 48px;
    min-height: 28px;
  }
  
  // Radio/Checkbox
  input[type="radio"],
  input[type="checkbox"] {
    min-width: 24px;
    min-height: 24px;
  }
  
  // Labels (larger touch area)
  label {
    padding: 8px 0;
    cursor: pointer;
  }
}
```

---

### 4. Form Actions (1 hour)

**Pattern for Save/Cancel buttons:**

```vue
<template>
  <div class="form-actions">
    <button type="submit" class="btn btn-primary">Save Changes</button>
    <button type="button" class="btn btn-secondary" @click="cancel">Cancel</button>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  
  @include m.respond-below('md') {
    flex-direction: column;  // Stack vertically
    
    .btn {
      width: 100%;
      min-height: 48px;
    }
  }
}
</style>
```

---

## 📂 Files to Modify

- `app/frontend/src/components/settings/NotificationSettingsPanel.vue`
- `app/frontend/src/components/settings/RecordingSettingsPanel.vue`
- `app/frontend/src/components/settings/GeneralSettingsPanel.vue`
- `app/frontend/src/views/SettingsView.vue` (if needed)

---

## ✅ Acceptance Criteria

**NotificationSettingsPanel:**
- [ ] Apprise URLs table transforms to cards < 768px
- [ ] Each card shows service, URL, actions stacked
- [ ] Delete button full-width, 48px height
- [ ] URL text wraps properly (no horizontal scroll)
- [ ] `data-label` attributes on all `<td>` elements

**RecordingSettingsPanel:**
- [ ] Quality/format grid stacks to single column < 768px
- [ ] All inputs 48px height minimum
- [ ] Inputs 16px font size (iOS zoom prevention)
- [ ] Form labels 14px, clear spacing
- [ ] Save/Cancel buttons stack vertically, full width

**Touch Targets:**
- [ ] All buttons minimum 48px height
- [ ] All inputs minimum 48px height
- [ ] Touch areas comfortable (not cramped)
- [ ] No accidental touches (proper spacing)

**General:**
- [ ] No horizontal scrolling on any screen size
- [ ] All text readable (14px+ font size)
- [ ] Proper spacing between elements (12px+)
- [ ] Consistent with Design System patterns

---

## 🧪 Testing Checklist

**Device Testing:**
- [ ] iPhone SE (375px) - Smallest common
- [ ] iPhone 12/13/14 (390px)
- [ ] Android (360px, 412px)
- [ ] iPad portrait (768px) - Breakpoint
- [ ] Desktop (1024px+)

**Specific Tests:**
- [ ] Add Apprise URL → Card displays correctly
- [ ] Delete URL from card → Works on mobile
- [ ] Change recording quality → Dropdown usable
- [ ] Save settings → Success message visible
- [ ] Form validation → Error messages readable
- [ ] Long URLs → Wrap without overflow

**Browser Testing:**
- [ ] Safari iOS (CRITICAL - 50% mobile traffic)
- [ ] Chrome Android
- [ ] Firefox Android

---

## 📖 Documentation

**Primary:** `docs/DESIGN_SYSTEM.md` (Table → Card Pattern)  
**Reference:** `.github/instructions/frontend.instructions.md` (Mobile-First section)  
**Master List:** `docs/MASTER_TASK_LIST.md` (Task #5)

---

## 🤖 Copilot Instructions

**Context:**
Make Settings panels mobile-friendly using table→card transformation pattern. This is a high-priority UX improvement affecting 50%+ of users.

**Critical Patterns:**
1. **Table → Card Transformation:**
   ```scss
   @include m.respond-below('md') {
     table { display: block; }
     .mobile-card { /* card styling */ }
     td::before { content: attr(data-label); }
   }
   ```

2. **iOS Zoom Prevention:**
   ```scss
   input, select {
     font-size: 16px !important;  // CRITICAL
   }
   ```

3. **Touch Targets:**
   ```scss
   button, input {
     min-height: 48px;  // 44px minimum
   }
   ```

4. **Vertical Stacking:**
   ```scss
   .form-actions {
     @include m.respond-below('md') {
       flex-direction: column;
     }
   }
   ```

**Breakpoint:**
- Use `@include m.respond-below('md')` for < 768px
- This is the critical mobile/tablet cutoff

**Design System:**
- Use global `.btn`, `.form-input`, `.card` classes
- Don't create custom CSS for existing patterns
- Check `DESIGN_SYSTEM.md` before writing CSS

**Testing Strategy:**
1. Test on real device or simulator
2. Check Safari iOS (most important)
3. Verify no horizontal scroll
4. Test touch interactions
5. Verify 16px inputs (iOS zoom test)

**Files to Read First:**
- `docs/DESIGN_SYSTEM.md` (Table → Card pattern)
- `.github/instructions/frontend.instructions.md` (Mobile section)
- Existing mobile-responsive components for reference

**Success Criteria:**
All settings panels usable on mobile, no horizontal scroll, touch targets 48px+, iOS zoom prevented, cards display properly.

**Common Pitfalls:**
- ❌ Forgetting `data-label` attributes
- ❌ Input font-size < 16px (iOS will zoom)
- ❌ Touch targets < 44px
- ❌ Not testing on Safari iOS
- ❌ Using custom CSS instead of Design System classes
