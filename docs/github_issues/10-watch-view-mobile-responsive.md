# Watch View Mobile Layout Optimization

## 🟡 Priority: HIGH
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 3-4 hours  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** HIGH - Core viewing experience on mobile

---

## 📝 Problem Description

### Current State: Video Layout Not Mobile-Optimized

**Issues on Mobile (< 768px):**
- ❌ **Video player aspect ratio wasteful** - Doesn't use full screen width
- ❌ **Info panel takes too much space** - Always expanded, pushes content down
- ❌ **Chapter list hard to navigate** - Cramped vertical space
- ❌ **Controls compete with device UI** - System bars overlap player
- ❌ **Landscape mode not immersive** - Same layout as portrait

**User Impact:**
- Tiny video player on small screens
- Must scroll to see stream info/chapters
- Awkward one-handed navigation
- Accidental navigation when trying to tap controls
- No immersive landscape video experience

**Desktop Layout (Works Well):**
- 16:9 video with max-width constraint (1280px)
- Info panel visible alongside video
- Chapter list in sidebar
- Plenty of screen real estate

**Mobile Layout (Current Problems):**
- Same desktop layout scaled down
- Info panel visible by default → video pushed up
- Chapter list below fold → must scroll
- Landscape mode unchanged → small video

---

## 🎯 Requirements

### Portrait Mode (< 768px, vertical orientation)
**Video Player:**
- Full viewport width (100vw, no margins)
- 16:9 aspect ratio maintained
- No max-width constraint on mobile

**Info Panel:**
- Collapsible by default (starts closed)
- Toggle button: "Show Info" / "Hide Info"
- Smooth expand/collapse animation (300ms)
- Keep video always visible while expanding

**Chapter List:**
- Sticky bottom panel (swipe up to open)
- Quick access without leaving video
- OR: Move to hamburger menu on mobile

### Landscape Mode (< 768px, horizontal orientation)
**Immersive Video:**
- Video fills screen height (100vh)
- Hide info panel automatically
- Hide chapter list by default
- System UI overlays video (not pushes)

**Quick Access Controls:**
- Tap video → Show overlay with chapters
- Side drawer for chapter navigation (slide from right)
- Back button returns to portrait/exits fullscreen

---

## 📐 Layout Architecture

### Portrait Mode Layout

```
┌──────────────────────────┐
│   Video Player (100vw)   │  ← Full width, 16:9
│     [Playing Video]      │
│                          │
└──────────────────────────┘
┌──────────────────────────┐
│ [▼ Show Info]  (Button) │  ← Toggle collapsed state
└──────────────────────────┘
┌──────────────────────────┐
│  Stream Info (Hidden)    │  ← Only visible when expanded
│  - Title                 │
│  - Streamer              │
│  - Category              │
└──────────────────────────┘
┌──────────────────────────┐
│ [▲ Chapters]   (Button)  │  ← Sticky bottom panel
└──────────────────────────┘
```

### Landscape Mode Layout

```
┌────────────────────────────────────────┐
│                                        │
│         Video Player (100vh)          │  ← Fills screen
│                                        │
│         [Overlay Controls]            │  ← On tap
│                                        │
└────────────────────────────────────────┘

Tap → Chapters drawer slides from right edge
```

---

## 🎨 Design Requirements

### 1. Responsive Breakpoints
- **Mobile:** `< 768px` (match app-wide breakpoint)
- **Portrait:** `orientation: portrait`
- **Landscape:** `orientation: landscape` + `< 768px`

### 2. Collapsible Panel Behavior
**Default State:**
- Mobile: Info panel **collapsed** (hidden)
- Desktop: Info panel **expanded** (visible)

**Toggle Animation:**
- Smooth height transition (300ms ease)
- Button icon rotates (chevron up ↔ down)
- Button text changes: "Show Info" ↔ "Hide Info"

**Visual Feedback:**
- Button with subtle background
- Icon + text centered
- Full-width button for easy tapping

### 3. Landscape Immersion
**What to Hide:**
- Info panel (completely hidden)
- Navigation header
- Footer elements
- Chapter list (access via overlay)

**What to Show:**
- Video player (100vh height)
- Overlay controls (on tap, 5s timeout)
- System UI overlays (not inline)

### 4. Chapter Access on Mobile
**Option A: Sticky Bottom Panel**
- Swipe up from bottom → Opens chapter drawer
- Swipe down → Closes drawer
- Semi-transparent overlay when open

**Option B: Hamburger Menu**
- Move chapters to menu in top-right
- Tap → Sidebar slides in from right
- Consistent with app navigation

---

## 📋 Implementation Scope

### Files to Modify

**Primary View:**
- `app/frontend/src/views/WatchView.vue`

**What Needs Changing:**
1. **Responsive SCSS** - Breakpoints for mobile/landscape
2. **Video Container** - Full-width on mobile, aspect-ratio handling
3. **Info Panel Component** - Add collapse/expand logic
4. **Chapter List Layout** - Sticky panel or menu integration
5. **State Management** - Track `isInfoCollapsed` (mobile only)

---

## ✅ Acceptance Criteria

### Portrait Mode (< 768px)
- [ ] Video player uses full viewport width (100vw)
- [ ] Video maintains 16:9 aspect ratio
- [ ] Info panel collapsed by default
- [ ] "Show Info" button visible below video
- [ ] Button toggles panel with smooth animation
- [ ] Chapter list accessible (sticky panel or menu)

### Landscape Mode (< 768px, horizontal)
- [ ] Video fills screen height (100vh)
- [ ] Info panel hidden automatically
- [ ] Navigation header hidden
- [ ] Chapters accessible via overlay/drawer
- [ ] Tap video shows/hides overlay controls
- [ ] Back button exits immersive mode

### Desktop (≥ 768px)
- [ ] Layout unchanged (current design preserved)
- [ ] Info panel always visible
- [ ] Chapter list in sidebar
- [ ] No collapse toggle visible

### Interaction & Polish
- [ ] One-handed navigation easy
- [ ] No accidental taps on system UI
- [ ] Smooth transitions (300ms)
- [ ] Consistent with app design language
- [ ] Works with video player controls (Issue #9)

### Testing Checklist
- [ ] iPhone SE portrait (375px width)
- [ ] iPhone 14 Pro portrait (393px width)
- [ ] iPhone 14 Pro landscape (852px width)
- [ ] iPad portrait (768px) → Should use desktop layout
- [ ] Rotate device mid-playback → Layout adapts
- [ ] Toggle info panel multiple times → No flicker
- [ ] Open chapters while video playing → No pause/lag

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Mobile breakpoints, responsive patterns
- `.github/instructions/frontend.instructions.md` - SCSS mixins, mobile-first

**Related Components:**
- `app/frontend/src/components/VideoPlayer.vue` - Video playback
- `app/frontend/src/components/ChapterPanel.vue` (if exists) - Chapter navigation

**Related Issues:**
- Issue #9: Video Player Controls Mobile (control sizing)
- Issue #12: Chapters Panel Mobile (chapter list touch targets)
- Issue #4: Settings Tables Mobile (similar collapsible pattern)

**Responsive Patterns:**
```scss
// Mobile breakpoint mixin
@include m.respond-below('md') { /* < 768px */ }

// Orientation detection
@media (orientation: landscape) { /* Horizontal */ }
@media (orientation: portrait) { /* Vertical */ }
```

---

## 🎯 Solution

### Mobile-First Watch Layout

**Portrait Mode:**
- Full-width video player
- Collapsible info panel (default closed)
- Sticky chapter list (swipe up)
- Minimal UI chrome

**Landscape Mode:**
- Immersive video (hide non-essential UI)
- Overlay controls
- Quick access to chapters (side drawer)

---

## 📋 Implementation Tasks

### 1. Video Player Aspect Ratio (1 hour)

```scss
@use '@/styles/mixins' as m;

.video-container {
  // Desktop: 16:9 with max-width
  max-width: 1280px;
  aspect-ratio: 16/9;
  margin: 0 auto;
  
  @include m.respond-below('md') {
    // Mobile: Full viewport width
    max-width: 100%;
    width: 100vw;
    margin: 0;
    
    // Portrait: Standard video ratio
    aspect-ratio: 16/9;
    
    // Landscape: Fill screen height
    @media (orientation: landscape) {
      height: 100vh;
      aspect-ratio: auto;
    }
  }
}
```

---

### 2. Collapsible Info Panel (1 hour)

```vue
<template>
  <div class="watch-view">
    <div class="video-section">
      <VideoPlayer :stream="stream" />
    </div>
    
    <!-- Mobile: Collapsible info -->
    <div 
      class="info-section"
      :class="{ 'collapsed': isInfoCollapsed }"
    >
      <button 
        v-if="isMobile"
        class="collapse-toggle"
        @click="isInfoCollapsed = !isInfoCollapsed"
      >
        <i :class="isInfoCollapsed ? 'icon-chevron-up' : 'icon-chevron-down'"></i>
        {{ isInfoCollapsed ? 'Show Info' : 'Hide Info' }}
      </button>
      
      <div class="info-content" v-show="!isInfoCollapsed || !isMobile">
        <h1>{{ stream.title }}</h1>
        <p>{{ stream.streamer.display_name }}</p>
        <p>{{ stream.category_name }}</p>
        <!-- More info -->
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const isMobile = ref(false)
const isInfoCollapsed = ref(true) // Default closed on mobile

onMounted(() => {
  isMobile.value = window.innerWidth < 768
  
  window.addEventListener('resize', () => {
    isMobile.value = window.innerWidth < 768
  })
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.info-section {
  transition: max-height 0.3s ease;
  
  @include m.respond-below('md') {
    &.collapsed {
      .info-content {
        display: none;
      }
    }
    
    .collapse-toggle {
      width: 100%;
      padding: 12px;
      background: var(--bg-secondary);
      border: none;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      cursor: pointer;
      font-size: 14px;
      color: var(--text-primary);
      
      &:active {
        background: var(--bg-tertiary);
      }
    }
  }
}
</style>
```

---

### 3. Chapter Navigation Mobile (1 hour)

```vue
<template>
  <div class="chapters-section">
    <!-- Desktop: Sidebar -->
    <aside v-if="!isMobile" class="chapters-sidebar">
      <ChapterList :chapters="chapters" />
    </aside>
    
    <!-- Mobile: Bottom drawer -->
    <div v-else class="chapters-drawer" :class="{ 'open': isChaptersOpen }">
      <button class="drawer-handle" @click="toggleChapters">
        <div class="handle-bar"></div>
        <span>Chapters ({{ chapters.length }})</span>
      </button>
      
      <div class="drawer-content">
        <ChapterList :chapters="chapters" @chapter-click="closeChapters" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const isChaptersOpen = ref(false)

const toggleChapters = () => {
  isChaptersOpen.value = !isChaptersOpen.value
}

const closeChapters = () => {
  isChaptersOpen.value = false
}
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

@include m.respond-below('md') {
  .chapters-drawer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--bg-primary);
    border-top: 1px solid var(--border-color);
    transform: translateY(calc(100% - 48px)); // Show only handle
    transition: transform 0.3s ease;
    z-index: 1000;
    max-height: 60vh;
    
    &.open {
      transform: translateY(0); // Show full drawer
      box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.2);
    }
    
    .drawer-handle {
      width: 100%;
      padding: 12px;
      background: var(--bg-secondary);
      border: none;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      
      .handle-bar {
        width: 40px;
        height: 4px;
        background: var(--text-tertiary);
        border-radius: 2px;
      }
    }
    
    .drawer-content {
      overflow-y: auto;
      max-height: calc(60vh - 48px);
      padding: 16px;
    }
  }
}
</style>
```

---

### 4. Landscape Mode Optimization (30 minutes)

```scss
@media (orientation: landscape) and (max-width: 896px) {
  .watch-view {
    // Hide header/footer in landscape
    .app-header,
    .app-footer {
      display: none;
    }
    
    .video-container {
      height: 100vh;
      width: 100vw;
    }
    
    // Overlay info on video
    .info-section {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      background: linear-gradient(to top, rgba(0,0,0,0.9), transparent);
      padding: 20px;
      z-index: 100;
      
      // Auto-hide after 3s
      animation: fadeOut 0.3s ease 3s forwards;
    }
  }
  
  @keyframes fadeOut {
    to { opacity: 0; pointer-events: none; }
  }
}
```

---

## 📂 Files to Modify

- `app/frontend/src/views/WatchView.vue`
- `app/frontend/src/components/video/VideoPlayer.vue`
- `app/frontend/src/components/chapters/ChapterList.vue`

---

## ✅ Acceptance Criteria

**Video Player:**
- [ ] Full-width on mobile (no side padding)
- [ ] Maintains 16:9 aspect ratio (portrait)
- [ ] Fills screen in landscape mode
- [ ] No letterboxing issues

**Info Panel:**
- [ ] Default collapsed on mobile
- [ ] Smooth expand/collapse animation
- [ ] Touch-friendly toggle button (48px height)
- [ ] Always visible on desktop

**Chapter Navigation:**
- [ ] Bottom drawer on mobile
- [ ] Swipe gesture to open/close
- [ ] Shows chapter count on handle
- [ ] Max 60vh height (doesn't cover entire screen)
- [ ] Tapping chapter closes drawer and seeks

**Landscape Mode:**
- [ ] Immersive video (full viewport)
- [ ] Header/footer hidden
- [ ] Info overlays video with auto-hide
- [ ] Back button accessible

**Performance:**
- [ ] Smooth animations (60fps)
- [ ] No layout shift when toggling panels
- [ ] Video playback not interrupted

---

## 🧪 Testing Checklist

**Device Testing:**
- [ ] iPhone SE portrait (375px)
- [ ] iPhone 12 portrait (390px)
- [ ] iPhone 12 landscape (844px × 390px)
- [ ] Android portrait (360px, 412px)
- [ ] Android landscape (various)
- [ ] iPad portrait (768px)

**Interaction Testing:**
- [ ] Tap info toggle → Panel expands/collapses
- [ ] Swipe up on chapter handle → Drawer opens
- [ ] Tap chapter → Seeks and closes drawer
- [ ] Rotate to landscape → UI adjusts
- [ ] Play video in landscape → Immersive mode
- [ ] Back button works in landscape

**Edge Cases:**
- [ ] Very long stream title → Text wraps properly
- [ ] Many chapters (50+) → Drawer scrollable
- [ ] No chapters → Drawer handle hidden
- [ ] Slow network → Video loads smoothly

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md`  
**Related:** `docs/REMAINING_FRONTEND_TASKS.md`  
**Design:** `docs/DESIGN_SYSTEM.md`

---

## 🤖 Copilot Instructions

**Context:**
Optimize Watch View for mobile devices with collapsible info panel, bottom chapter drawer, and landscape immersive mode. Current layout wastes screen space and makes navigation difficult on phones.

**Critical Patterns:**

1. **Collapsible panel:**
   ```vue
   <div :class="{ collapsed: isCollapsed }">
   ```

2. **Bottom drawer:**
   ```scss
   transform: translateY(calc(100% - 48px)); // Handle only
   &.open { transform: translateY(0); } // Full drawer
   ```

3. **Landscape detection:**
   ```scss
   @media (orientation: landscape) and (max-width: 896px) {
     // Immersive mode
   }
   ```

4. **Touch-friendly:**
   ```scss
   .toggle-btn { min-height: 48px; }
   ```

**Implementation Order:**
1. Video player aspect ratio fixes
2. Collapsible info panel with toggle
3. Bottom drawer for chapters
4. Landscape mode optimization
5. Test on real devices

**Testing Strategy:**
1. Test on Safari iOS (primary target)
2. Verify smooth animations
3. Test landscape rotation
4. Verify video playback not interrupted
5. Test with real content (long titles, many chapters)

**Files to Read First:**
- `app/frontend/src/views/WatchView.vue` (current layout)
- `docs/DESIGN_SYSTEM.md` (animation patterns)
- `.github/instructions/frontend.instructions.md` (mobile patterns)

**Success Criteria:**
Info collapsed by default on mobile, chapter drawer on bottom, landscape immersive mode, smooth animations, touch-friendly controls.

**Common Pitfalls:**
- ❌ Not testing landscape orientation
- ❌ Drawer covering entire screen
- ❌ Info panel animation janky
- ❌ Forgetting to hide header/footer in landscape
- ❌ Not testing on Safari iOS
