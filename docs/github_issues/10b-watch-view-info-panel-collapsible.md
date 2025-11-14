# Watch View - Collapsible Info Panel Mobile

## 🟡 Priority: HIGH
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 30-45 minutes  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** HIGH - Screen space optimization on mobile
**Dependencies:** None (can run in parallel with #10A)

---

## 📝 Problem Description

### Current State: Info Panel Always Visible on Mobile

**Issues on Mobile (< 768px):**
- ❌ **Info panel always expanded** - Takes up 30-40% of screen
- ❌ **Video pushed up** - Info panel below video reduces visible content
- ❌ **Must scroll to see more** - Chapters/comments below fold
- ❌ **No way to hide** - Panel permanently visible

**User Impact:**
- Small video player (panel steals screen space)
- Must scroll constantly to navigate
- Can't focus on video alone
- Awkward one-handed usage (need to scroll frequently)

**Desktop Layout (Correct - Don't Change):**
- Info panel always visible alongside video
- Plenty of horizontal space
- No need to collapse

**Mobile Layout (Current Problems):**
- Info panel below video, always expanded
- Takes 200-300px vertical space
- No collapse option → wasted screen space

---

## 🎯 Requirements

### Mobile Behavior (< 768px)

**Default State:**
- Info panel **collapsed** (hidden) on page load
- Only toggle button visible: "Show Info" / "Hide Info"
- Video and chapter list visible → maximize screen for content

**Toggle Button:**
- Full-width button between video and content
- Icon + text: "▼ Show Info" / "▲ Hide Info"
- Minimum height: 48px (touch-friendly)
- Clear visual indicator (chevron icon rotates)

**Expanded State:**
- Smooth animation (300ms ease-in-out)
- Info panel slides down below toggle button
- Button text changes: "Hide Info"
- Chevron icon rotates 180° (points up)

**Collapsed State:**
- Info panel hidden (display: none or max-height: 0)
- Button text: "Show Info"
- Chevron points down

### Desktop Behavior (≥ 768px)

**No Changes Required:**
- Info panel always visible (no toggle button)
- Current layout preserved
- No collapsible behavior

---

## 📐 Layout Architecture

### Mobile Portrait (< 768px)

```
┌──────────────────────────┐
│   Video Player (100vw)   │
└──────────────────────────┘
┌──────────────────────────┐
│ [▼ Show Info]  (Button) │  ← Toggle (48px height)
└──────────────────────────┘
┌──────────────────────────┐
│  (Info Panel Hidden)     │  ← Default collapsed
└──────────────────────────┘
┌──────────────────────────┐
│  Chapter List / Comments │  ← More visible content
└──────────────────────────┘

After Tap:
┌──────────────────────────┐
│   Video Player (100vw)   │
└──────────────────────────┘
┌──────────────────────────┐
│ [▲ Hide Info]  (Button) │  ← Chevron rotated
└──────────────────────────┘
┌──────────────────────────┐
│  Stream Info (Visible)   │  ← Expanded
│  - Title                 │
│  - Streamer              │
│  - Category              │
│  - Duration, viewers     │
└──────────────────────────┘
```

---

## 🎨 Design Requirements

### 1. Toggle Button Styling

**Layout:**
- **Width:** 100% (full width between sections)
- **Height:** 48px minimum (touch-friendly)
- **Padding:** 12px vertical
- **Display:** flex, centered content

**Visual Style:**
- **Background:** `var(--bg-secondary)` (subtle gray)
- **Border:** 1px solid `var(--border-color)` (top and bottom)
- **Text Color:** `var(--text-primary)`
- **Font Size:** 14px
- **Gap:** 8px between icon and text

**States:**
- **Normal:** Subtle background
- **:active (touch):** Darker background `var(--bg-tertiary)`
- **Transition:** Background 150ms ease

### 2. Icon Behavior

**Chevron Icon:**
- **Size:** 16px (readable)
- **Rotation:** 0deg (collapsed) → 180deg (expanded)
- **Transition:** transform 300ms ease (smooth rotation)
- **Position:** Left of text

**Icon Mapping:**
- Collapsed: `icon-chevron-down` or `▼`
- Expanded: `icon-chevron-up` or `▲` (OR rotate down icon 180°)

### 3. Panel Animation

**Expand Animation:**
```scss
transition: max-height 300ms ease-in-out;

// Collapsed state
&.collapsed {
  max-height: 0;
  overflow: hidden;
  opacity: 0; // Optional fade
}

// Expanded state
&.expanded {
  max-height: 500px; // Or auto with JS height calculation
  opacity: 1;
}
```

**Considerations:**
- Use `max-height` (not `height`) for smooth animation
- Add `overflow: hidden` to prevent content clipping
- Optional: Add `opacity` transition for fade effect

### 4. Responsive Breakpoint

**Mobile (< 768px):**
- Toggle button visible
- Panel collapsible with animation

**Desktop (≥ 768px):**
- Toggle button hidden (display: none)
- Panel always visible (no collapsed class)

---

## 📋 Implementation Scope

### Files to Modify

**Primary File:**
- `app/frontend/src/views/WatchView.vue`

**Section to Modify:**
- `.info-section` or `.stream-info-panel` markup + styles
- Add toggle button before info content
- Add state management for `isInfoCollapsed`

**What Needs Changing:**

1. **Template (Markup):**
   - Add toggle button above info content
   - Add `v-if="isMobile"` to button (hide on desktop)
   - Add `:class="{ collapsed: isInfoCollapsed }"` to panel
   - Add `v-show="!isInfoCollapsed || !isMobile"` to content

2. **Script (Logic):**
   - Add `const isInfoCollapsed = ref(true)` (default closed)
   - Add `const isMobile = ref(false)` (detect viewport width)
   - Add `toggleInfo()` method
   - Add `onMounted()` to detect initial screen size
   - Add resize listener (optional, for live resizing)

3. **Style (SCSS):**
   - Add `.collapse-toggle` button styles
   - Add `.info-section.collapsed` styles (max-height: 0)
   - Add icon rotation transition
   - Add mobile breakpoint `@include m.respond-below('md')`

**What NOT to Change:**
- ❌ Video container (Issue #10A handles video layout)
- ❌ Chapter drawer (Issue #10C handles drawer)
- ❌ Desktop info panel layout (≥ 768px unchanged)
- ❌ Info panel content structure (title, streamer, category)

---

## ✅ Acceptance Criteria

### Functional Requirements
- [ ] Info panel collapsed by default on mobile (< 768px)
- [ ] Toggle button visible below video on mobile
- [ ] Tap button → Panel expands with smooth animation
- [ ] Tap again → Panel collapses with smooth animation
- [ ] Chevron icon rotates 180° when toggling
- [ ] Button text changes: "Show Info" ↔ "Hide Info"

### Visual Requirements
- [ ] Button height: 48px minimum (touch-friendly)
- [ ] Button full-width between sections
- [ ] Smooth animation: 300ms ease-in-out
- [ ] No content clipping during animation
- [ ] Icon rotation smooth (not instant)
- [ ] Background darkens on :active (touch feedback)

### Desktop Behavior (≥ 768px)
- [ ] Toggle button hidden (not rendered)
- [ ] Info panel always visible (no collapsed state)
- [ ] No animation or collapsible behavior
- [ ] Current layout unchanged

### Edge Cases
- [ ] Toggle multiple times quickly → No animation stutter
- [ ] Resize window from mobile to desktop → Button disappears
- [ ] Resize from desktop to mobile → Button appears, panel collapsed
- [ ] Very long titles → Text wraps, doesn't break layout
- [ ] Empty info fields → Panel still renders correctly

### Testing Checklist
- [ ] iPhone SE portrait (375px) - Button visible, panel collapsed
- [ ] iPhone 14 Pro portrait (393px) - Same behavior
- [ ] iPad portrait (768px) → Desktop layout (no button)
- [ ] Tap toggle 10x rapidly → No flicker or break
- [ ] Rotate device mid-expanded → State preserved
- [ ] Browser zoom 200% → Button still tappable

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Button patterns, animations
- `.github/instructions/frontend.instructions.md` - Vue patterns

**Similar Patterns:**
- Settings tables collapsible sections (Issue #4)
- Accordion components in design system

**Vue Composition API:**
```typescript
import { ref, onMounted, onUnmounted } from 'vue'

const isInfoCollapsed = ref(true)
const isMobile = ref(false)

const toggleInfo = () => {
  isInfoCollapsed.value = !isInfoCollapsed.value
}

onMounted(() => {
  const checkMobile = () => {
    isMobile.value = window.innerWidth < 768
  }
  
  checkMobile()
  window.addEventListener('resize', checkMobile)
  
  onUnmounted(() => {
    window.removeEventListener('resize', checkMobile)
  })
})
```

**SCSS Animation Pattern:**
```scss
.info-section {
  transition: max-height 0.3s ease-in-out;
  
  @include m.respond-below('md') {
    &.collapsed {
      max-height: 0;
      overflow: hidden;
    }
    
    .collapse-toggle {
      // Button styles
      
      i {
        transition: transform 0.3s ease;
      }
      
      &.expanded i {
        transform: rotate(180deg);
      }
    }
  }
}
```

**Related Issues:**
- Issue #10A: Watch View - Video Layout (video container - separate concern)
- Issue #10C: Watch View - Chapter Drawer (drawer positioning - next task)
- Issue #4: Settings Tables Mobile (similar collapsible pattern)

---

## 🚀 Implementation Guide

### Step 1: Add State Management (10 min)
```typescript
// In <script setup>
import { ref, onMounted } from 'vue'

const isInfoCollapsed = ref(true) // Default closed
const isMobile = ref(false)

const toggleInfo = () => {
  isInfoCollapsed.value = !isInfoCollapsed.value
}

onMounted(() => {
  isMobile.value = window.innerWidth < 768
  
  window.addEventListener('resize', () => {
    isMobile.value = window.innerWidth < 768
  })
})
```

### Step 2: Add Toggle Button (10 min)
```vue
<template>
  <div class="info-section" :class="{ collapsed: isInfoCollapsed }">
    <!-- Toggle button (mobile only) -->
    <button
      v-if="isMobile"
      class="collapse-toggle"
      @click="toggleInfo"
      :aria-expanded="!isInfoCollapsed"
    >
      <i :class="isInfoCollapsed ? 'icon-chevron-down' : 'icon-chevron-up'"></i>
      <span>{{ isInfoCollapsed ? 'Show Info' : 'Hide Info' }}</span>
    </button>
    
    <!-- Info content -->
    <div class="info-content" v-show="!isInfoCollapsed || !isMobile">
      <h1>{{ stream.title }}</h1>
      <p>{{ stream.streamer.display_name }}</p>
      <!-- ... existing content ... -->
    </div>
  </div>
</template>
```

### Step 3: Add SCSS Styles (15 min)
```scss
@use '@/styles/mixins' as m;

.info-section {
  @include m.respond-below('md') {
    .collapse-toggle {
      width: 100%;
      min-height: 48px;
      padding: 12px;
      background: var(--bg-secondary);
      border: none;
      border-top: 1px solid var(--border-color);
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      cursor: pointer;
      font-size: 14px;
      color: var(--text-primary);
      transition: background 0.15s ease;
      
      &:active {
        background: var(--bg-tertiary);
      }
      
      i {
        font-size: 16px;
        transition: transform 0.3s ease;
      }
    }
    
    &.collapsed {
      .info-content {
        max-height: 0;
        overflow: hidden;
        opacity: 0;
        transition: max-height 0.3s ease-in-out, opacity 0.3s ease;
      }
    }
    
    &:not(.collapsed) {
      .info-content {
        max-height: 500px;
        opacity: 1;
        transition: max-height 0.3s ease-in-out, opacity 0.3s ease;
      }
    }
  }
}
```

### Step 4: Test Responsiveness (10 min)
1. Open DevTools, toggle device toolbar
2. Test iPhone SE (375px) - Button visible
3. Tap button → Panel expands smoothly
4. Tap again → Panel collapses smoothly
5. Resize to iPad (768px) → Button disappears, panel visible

---

## ⚠️ Common Pitfalls to Avoid

1. **❌ Don't use `height` for animation**
   - Use `max-height` for smooth transitions
   - `height: auto` doesn't animate

2. **❌ Don't forget `overflow: hidden`**
   - Content will clip during animation without it

3. **❌ Don't hardcode button visibility**
   - Use `v-if="isMobile"` instead of CSS `display: none`
   - Prevents unnecessary rendering on desktop

4. **❌ Don't forget touch feedback**
   - Add `:active` state for immediate visual response

5. **❌ Don't modify video or chapters**
   - This task is ONLY info panel collapsible behavior
   - Video = Issue #10A, Chapters = Issue #10C

---

## 🎯 Success Criteria

**Task Complete When:**
- ✅ Panel collapsed by default on mobile
- ✅ Toggle button functional with smooth animation
- ✅ Icon rotates, text changes on toggle
- ✅ Desktop layout unchanged (no toggle button)
- ✅ No animation stutter or flicker
- ✅ Touch-friendly (48px button)

**Ready for Next Task (#10C):**
- ✅ Info panel collapsible working
- ✅ No conflicts with video or chapter sections
- ✅ Commit merged to develop branch

---

## 📊 Estimated Breakdown

- **State management:** 10 minutes (refs, toggle function)
- **Template markup:** 10 minutes (button + v-show logic)
- **SCSS styling:** 15 minutes (button + animation)
- **Testing:** 10 minutes (mobile, desktop, toggle behavior)

**Total:** 30-45 minutes

---

## 🤖 Agent Recommendation

**Primary Agent:** `mobile-specialist`  
**Backup Agent:** `feature-builder`

**Why mobile-specialist:**
- Mobile UX patterns expertise
- Collapsible panel experience
- Touch interaction knowledge

**Copilot Command:**
```bash
@copilot with agent mobile-specialist: Add collapsible info panel to WatchView with toggle button, default collapsed on mobile
```
