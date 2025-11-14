# Watch View - Chapter Drawer Integration Mobile

## 🟡 Priority: HIGH
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 45-60 minutes  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** HIGH - Chapter navigation on mobile
**Dependencies:** ❌ **Requires Issue #12 (Chapters Panel Component) completed first**

---

## 📝 Problem Description

### Current State: Chapter List Not Mobile-Friendly

**Issues on Mobile (< 768px):**
- ❌ **Chapter list below fold** - Must scroll past video and info to see
- ❌ **Takes up vertical space** - Sidebar layout doesn't work on narrow screens
- ❌ **No quick access** - Can't navigate chapters without scrolling away from video
- ❌ **Desktop pattern on mobile** - Same sidebar, just smaller

**User Impact:**
- Can't see chapters while watching video
- Must scroll to chapter list → Lose video view
- Awkward navigation (video out of sight when browsing chapters)
- No quick chapter skipping

**Desktop Layout (Correct - Don't Change):**
- Chapter list in sidebar (always visible)
- Plenty of horizontal space
- Side-by-side with video

**Mobile Layout (Current Problems):**
- Same sidebar scaled down OR list below video
- Must scroll to access → Lose video view
- No overlay or drawer pattern

---

## 🎯 Requirements

### Mobile Behavior (< 768px)

**Chapter Access Pattern:**
- **Bottom drawer** (portrait mode) - Swipe up from bottom edge
- **Side drawer** (landscape mode) - Slide in from right edge
- **Default state:** Collapsed/hidden
- **Quick access:** Swipe gesture or tap button

**Bottom Drawer (Portrait):**
```
┌──────────────────────────┐
│   Video Player           │
│                          │
└──────────────────────────┘
┌──────────────────────────┐
│ [▲ Chapters (12)] ← Handle
└──────────────────────────┘
                ↑
         Swipe up to open
```

**Expanded State:**
```
┌──────────────────────────┐
│   Video Player (visible) │  ← Video stays visible
└──────────────────────────┘
┌──────────────────────────┐
│ [▼ Chapters (12)] ← Handle
├──────────────────────────┤
│  Chapter List (60% screen)
│  - Chapter 1: Intro      │
│  - Chapter 2: Gameplay   │
│  - Chapter 3: Outro      │
│  (scrollable)            │
└──────────────────────────┘
```

**Side Drawer (Landscape):**
```
┌────────────────────────────────┐
│                                │
│    Video Player (immersive)    │
│                                │
└────────────────────────────────┘
                           ↖
                    Tap video or swipe left
                    → Chapters slide from right
```

### Desktop Behavior (≥ 768px)

**No Changes Required:**
- Chapter list in sidebar (current behavior)
- Always visible
- No drawer pattern

---

## 🔗 **CRITICAL: Dependency on Issue #12**

### Why This Task Depends on #12

**Issue #12** creates the **ChapterPanel component** with:
- ✅ 72px touch-friendly chapter items
- ✅ Scroll indicators and auto-scroll
- ✅ Active chapter highlighting
- ✅ Touch feedback states

**This Task (#10C)** integrates that component:
- Wraps ChapterPanel in bottom/side drawer
- Adds swipe gesture handlers
- Positions drawer in WatchView layout
- Manages drawer open/closed state

**Execution Order:**
1. **First:** Issue #12 creates standalone ChapterPanel.vue component
2. **Then:** This task (#10C) adds drawer wrapper + swipe logic in WatchView.vue

**Why Sequential?**
- Both modify `WatchView.vue` → Would conflict if parallel
- This task needs ChapterPanel component to exist
- This task imports and uses `<ChapterPanel>` component

---

## 📐 Layout Architecture

### Portrait Mode - Bottom Drawer

```
Default State (Collapsed):
┌──────────────────────────┐
│   Video Player           │
│   (Full screen visible)  │
└──────────────────────────┘
┌──────────────────────────┐
│ ━━━ (handle bar)         │  ← 48px handle
│ Chapters (12)            │
└──────────────────────────┘  ← Fixed at bottom
          ↑
   Swipe up to expand

Expanded State (60vh):
┌──────────────────────────┐
│   Video Player (still    │
│   visible above drawer)  │
└──────────────────────────┘
┌──────────────────────────┐
│ ━━━ (handle bar)         │
│ Chapters (12)            │
├──────────────────────────┤
│ Chapter List             │  ← Takes 60% of viewport
│ (scrollable)             │
│ - Chapter 1              │
│ - Chapter 2              │
│ - Chapter 3...           │
└──────────────────────────┘
```

### Landscape Mode - Side Drawer

```
Default State (Hidden):
┌────────────────────────────────────┐
│                                    │
│    Video Player (immersive)        │
│    Tap to show overlay             │
└────────────────────────────────────┘

Expanded State (300px drawer):
┌──────────────────────┬─────────────┐
│                      │ Chapters    │
│   Video Player       │ ━━━ (12)    │
│   (70% width)        │ - Chapter 1 │
│                      │ - Chapter 2 │
│                      │ (scrollable)│
└──────────────────────┴─────────────┘
                       ↑
                300px side drawer
```

---

## 🎨 Design Requirements

### 1. Drawer Container

**Position:**
- **Portrait:** `position: fixed; bottom: 0;`
- **Landscape:** `position: fixed; right: 0;`
- **Z-index:** 1000 (above video, below modals)

**Dimensions:**
- **Portrait:** Full width, max 60vh height
- **Landscape:** 300px width, full height

**Background:**
- `var(--bg-primary)` with slight shadow
- Border-top (portrait) or border-left (landscape): `1px solid var(--border-color)`

### 2. Handle Bar (Portrait Only)

**Styling:**
- **Height:** 48px (touch-friendly)
- **Visual Handle:** 40px × 4px rounded bar (centered)
- **Color:** `var(--text-tertiary)` (subtle gray)
- **Text:** "Chapters (count)" centered below handle bar
- **Background:** `var(--bg-secondary)` (slightly darker)

### 3. Drawer States

**Collapsed (Portrait):**
```scss
.chapters-drawer {
  transform: translateY(calc(100% - 48px)); // Show only handle
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

**Expanded (Portrait):**
```scss
.chapters-drawer.open {
  transform: translateY(0); // Show full drawer
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.15);
}
```

**Hidden (Landscape Default):**
```scss
.chapters-drawer {
  transform: translateX(100%); // Off-screen right
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
```

**Visible (Landscape):**
```scss
.chapters-drawer.open {
  transform: translateX(0); // Slide in from right
  box-shadow: -4px 0 12px rgba(0, 0, 0, 0.15);
}
```

### 4. Swipe Gesture Behavior

**Portrait Swipe:**
- **Swipe up on handle** → Expand drawer
- **Swipe down on drawer** → Collapse drawer
- **Threshold:** 50px swipe distance to trigger
- **Velocity detection:** Fast swipe (> 300px/s) → Instant toggle

**Landscape Swipe:**
- **Swipe left on video** → Open drawer
- **Swipe right on drawer** → Close drawer
- **Tap outside drawer** → Close drawer (overlay dismiss)

### 5. Chapter Panel Integration

**Component Usage:**
```vue
<ChapterPanel
  :chapters="stream.chapters"
  :currentTime="videoCurrentTime"
  @chapter-click="handleChapterSeek"
/>
```

**Props Passed:**
- `chapters` - Array of chapter objects
- `currentTime` - Current video playback time (for active highlighting)

**Events Handled:**
- `@chapter-click` - Seek to chapter + close drawer

---

## 📋 Implementation Scope

### Files to Modify

**Primary File:**
- `app/frontend/src/views/WatchView.vue`

**What Needs Adding:**

1. **Template (Markup):**
   - Import `ChapterPanel` component (from Issue #12)
   - Add `.chapters-drawer` container
   - Add handle bar (portrait only)
   - Add `<ChapterPanel>` inside drawer
   - Add `v-if="isMobile"` for drawer (desktop uses sidebar)

2. **Script (Logic):**
   - Add `const isChaptersOpen = ref(false)` (drawer state)
   - Add `toggleChapters()` method
   - Add `handleChapterSeek(chapter)` method (seek + close)
   - Add swipe gesture handlers (touchstart/touchmove/touchend)
   - Add orientation detection (`isLandscape` ref)

3. **Style (SCSS):**
   - Add `.chapters-drawer` positioning (fixed bottom/right)
   - Add `.drawer-handle` styling (portrait only)
   - Add transform transitions (slide in/out)
   - Add mobile breakpoint `@include m.respond-below('md')`
   - Add orientation query `@media (orientation: landscape)`

**What NOT to Change:**
- ❌ Video container (Issue #10A already handled)
- ❌ Info panel (Issue #10B already handled)
- ❌ ChapterPanel component (Issue #12 creates it)
- ❌ Desktop sidebar layout (≥ 768px unchanged)

---

## ✅ Acceptance Criteria

### Portrait Mode (< 768px)
- [ ] Bottom drawer visible with handle bar
- [ ] Default state: Collapsed (only handle showing)
- [ ] Swipe up on handle → Drawer expands to 60vh
- [ ] Swipe down on drawer → Drawer collapses to handle
- [ ] Tap handle → Toggle drawer open/closed
- [ ] Chapter count displayed on handle: "Chapters (12)"
- [ ] Drawer shadow visible when expanded

### Landscape Mode (< 768px, horizontal)
- [ ] Side drawer hidden by default (off-screen right)
- [ ] Tap video or swipe left → Drawer slides in from right
- [ ] Drawer width: 300px from right edge
- [ ] Tap outside drawer → Drawer closes
- [ ] Swipe right on drawer → Drawer closes
- [ ] No handle bar (landscape uses side drawer pattern)

### Chapter Interaction
- [ ] Tap chapter item → Seeks video to timestamp
- [ ] After seek → Drawer closes automatically
- [ ] Active chapter highlighted in list
- [ ] Smooth scroll to active chapter (from Issue #12)
- [ ] Touch feedback on chapter items (from Issue #12)

### Desktop (≥ 768px)
- [ ] Drawer not rendered (v-if="isMobile" false)
- [ ] Sidebar layout unchanged (current behavior)
- [ ] No swipe gestures (desktop-only mouse interactions)

### Animation & Polish
- [ ] Drawer slides smoothly (300ms cubic-bezier)
- [ ] No layout shift when opening/closing
- [ ] Handle bar visible indicator (easy to grab)
- [ ] Shadow on drawer when open (depth perception)
- [ ] Video continues playing during drawer interaction

### Testing Checklist
- [ ] iPhone SE portrait (375px) - Bottom drawer
- [ ] iPhone 14 Pro portrait (393px) - Bottom drawer
- [ ] iPhone 14 Pro landscape (852px) - Side drawer
- [ ] Swipe up/down on handle → Drawer toggles
- [ ] Fast swipe → Instant toggle (velocity detection)
- [ ] Tap chapter → Seeks and closes drawer
- [ ] Rotate device → Drawer pattern changes (bottom ↔ side)
- [ ] iPad (768px) → No drawer (desktop sidebar)

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Drawer patterns, swipe gestures
- `.github/instructions/frontend.instructions.md` - Mobile patterns

**Swipe Gesture Libraries:**
- [Vue Use - useSwipe](https://vueuse.org/core/useSwipe/) - Lightweight swipe detection
- [Hammer.js](https://hammerjs.github.io/) - Advanced gestures
- Native: `touchstart`, `touchmove`, `touchend` events

**Native Swipe Implementation:**
```typescript
let touchStartY = 0
let touchStartX = 0

const handleTouchStart = (e: TouchEvent) => {
  touchStartY = e.touches[0].clientY
  touchStartX = e.touches[0].clientX
}

const handleTouchMove = (e: TouchEvent) => {
  const touchY = e.touches[0].clientY
  const deltaY = touchStartY - touchY
  
  if (deltaY > 50) { // Swipe up
    isChaptersOpen.value = true
  } else if (deltaY < -50) { // Swipe down
    isChaptersOpen.value = false
  }
}
```

**Related Issues:**
- **Issue #10A:** Watch View - Video Layout (video container - completed first)
- **Issue #10B:** Watch View - Info Panel (collapsible panel - completed second)
- **Issue #12:** Chapters Panel Mobile (ChapterPanel component - **DEPENDENCY - must complete before this**)

**Related Components:**
- `app/frontend/src/components/ChapterPanel.vue` - Created by Issue #12 (imported here)
- `app/frontend/src/views/WatchView.vue` - Parent container (modified here)

---

## 🚀 Implementation Guide

### Step 1: Import ChapterPanel Component (5 min)
```vue
<script setup lang="ts">
import ChapterPanel from '@/components/ChapterPanel.vue' // From Issue #12
import { ref, computed } from 'vue'

const isChaptersOpen = ref(false)
const isMobile = ref(false)
const isLandscape = ref(false)

const toggleChapters = () => {
  isChaptersOpen.value = !isChaptersOpen.value
}

const handleChapterSeek = (chapter: any) => {
  // Emit seek event to VideoPlayer
  emit('seek', chapter.start_time)
  
  // Close drawer after seeking
  isChaptersOpen.value = false
}
</script>
```

### Step 2: Add Drawer Markup (15 min)
```vue
<template>
  <div class="watch-view">
    <!-- Video + Info sections (from #10A, #10B) -->
    
    <!-- Desktop: Sidebar (existing) -->
    <aside v-if="!isMobile" class="chapters-sidebar">
      <ChapterPanel :chapters="stream.chapters" />
    </aside>
    
    <!-- Mobile: Bottom/Side Drawer -->
    <div
      v-if="isMobile"
      class="chapters-drawer"
      :class="{
        open: isChaptersOpen,
        landscape: isLandscape
      }"
    >
      <!-- Portrait: Handle Bar -->
      <div v-if="!isLandscape" class="drawer-handle" @click="toggleChapters">
        <div class="handle-bar"></div>
        <span>Chapters ({{ stream.chapters?.length || 0 }})</span>
      </div>
      
      <!-- Chapter List -->
      <div class="drawer-content">
        <ChapterPanel
          :chapters="stream.chapters"
          :currentTime="videoCurrentTime"
          @chapter-click="handleChapterSeek"
        />
      </div>
    </div>
  </div>
</template>
```

### Step 3: Add Drawer Styles (20 min)
```scss
@use '@/styles/mixins' as m;

@include m.respond-below('md') {
  .chapters-drawer {
    position: fixed;
    background: var(--bg-primary);
    z-index: 1000;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    
    // Portrait: Bottom drawer
    bottom: 0;
    left: 0;
    right: 0;
    max-height: 60vh;
    border-top: 1px solid var(--border-color);
    transform: translateY(calc(100% - 48px)); // Show handle only
    
    &.open {
      transform: translateY(0);
      box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.15);
    }
    
    // Landscape: Side drawer
    &.landscape {
      bottom: 0;
      right: 0;
      left: auto;
      width: 300px;
      height: 100vh;
      max-height: none;
      border-top: none;
      border-left: 1px solid var(--border-color);
      transform: translateX(100%); // Off-screen right
      
      &.open {
        transform: translateX(0);
        box-shadow: -4px 0 12px rgba(0, 0, 0, 0.15);
      }
      
      .drawer-handle {
        display: none; // No handle in landscape
      }
    }
    
    .drawer-handle {
      padding: 12px;
      text-align: center;
      background: var(--bg-secondary);
      cursor: pointer;
      user-select: none;
      
      .handle-bar {
        width: 40px;
        height: 4px;
        background: var(--text-tertiary);
        border-radius: 2px;
        margin: 0 auto 8px;
      }
      
      span {
        font-size: 14px;
        color: var(--text-secondary);
        font-weight: 500;
      }
    }
    
    .drawer-content {
      overflow-y: auto;
      max-height: calc(60vh - 48px); // Subtract handle height
      padding: 16px;
      
      .landscape & {
        max-height: 100vh;
      }
    }
  }
}
```

### Step 4: Add Swipe Gestures (15 min)
```typescript
// Optional: Use VueUse for easier implementation
import { useSwipe } from '@vueuse/core'

// Or native implementation:
const handleDrawerSwipe = (element: HTMLElement) => {
  let startY = 0
  
  element.addEventListener('touchstart', (e) => {
    startY = e.touches[0].clientY
  })
  
  element.addEventListener('touchend', (e) => {
    const endY = e.changedTouches[0].clientY
    const deltaY = startY - endY
    
    if (Math.abs(deltaY) > 50) {
      if (deltaY > 0) { // Swipe up
        isChaptersOpen.value = true
      } else { // Swipe down
        isChaptersOpen.value = false
      }
    }
  })
}

onMounted(() => {
  const drawer = document.querySelector('.chapters-drawer')
  if (drawer) handleDrawerSwipe(drawer as HTMLElement)
})
```

### Step 5: Test Interactions (10 min)
1. Portrait mode: Swipe up → Drawer expands
2. Tap handle → Toggles drawer
3. Tap chapter → Seeks and closes
4. Landscape mode: Swipe from right → Drawer opens
5. Tap outside → Drawer closes

---

## ⚠️ Common Pitfalls to Avoid

1. **❌ Don't start before Issue #12 complete**
   - ChapterPanel component must exist first
   - Would cause import errors

2. **❌ Don't modify ChapterPanel component**
   - Issue #12 owns that component
   - Only import and use it here

3. **❌ Don't forget orientation detection**
   - Portrait vs landscape need different drawer patterns
   - Use media query + JS detection

4. **❌ Don't cover entire screen**
   - Portrait: Max 60vh (keep video visible)
   - Landscape: 300px width (leave room for video)

5. **❌ Don't forget desktop check**
   - Add `v-if="isMobile"` to drawer
   - Desktop still uses sidebar

---

## 🎯 Success Criteria

**Task Complete When:**
- ✅ ChapterPanel imported from Issue #12
- ✅ Bottom drawer works in portrait
- ✅ Side drawer works in landscape
- ✅ Swipe gestures functional
- ✅ Seeking closes drawer automatically
- ✅ Desktop layout unchanged

**Ready for Production:**
- ✅ All 3 Watch View sub-tasks (#10A, #10B, #10C) complete
- ✅ Mobile watch experience fully optimized
- ✅ Tests passing on iPhone/Android

---

## 📊 Estimated Breakdown

- **Import component:** 5 minutes
- **Drawer markup:** 15 minutes (handle + content)
- **Drawer styles:** 20 minutes (portrait + landscape)
- **Swipe gestures:** 15 minutes (touch handlers)
- **Testing:** 10 minutes (all orientations)

**Total:** 45-60 minutes

---

## 🤖 Agent Recommendation

**Primary Agent:** `mobile-specialist`  
**Backup Agent:** `feature-builder`

**Why mobile-specialist:**
- Drawer pattern expertise
- Swipe gesture handling
- Orientation detection experience

**Copilot Command:**
```bash
@copilot with agent mobile-specialist: Integrate ChapterPanel into WatchView with bottom drawer (portrait) and side drawer (landscape), add swipe gestures
```
