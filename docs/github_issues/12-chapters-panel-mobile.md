# Chapters Panel Mobile Responsive

## 🟢 Priority: MEDIUM
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 2-3 hours  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** MEDIUM - Chapter navigation on mobile

---

## 📝 Problem Description

### Current State: Chapters Panel Not Touch-Optimized

**Issues on Mobile (< 768px):**
- ❌ **Chapter items too small** - 60px height, need 72px+ for touch
- ❌ **Timestamps hard to read** - Small font, low contrast
- ❌ **No visual tap feedback** - Unclear if tap registered
- ❌ **Active chapter indicator subtle** - Hard to see current position
- ❌ **Scroll indicator missing** - Can't tell if more chapters below
- ❌ **Panel takes too much space** - Always visible, covers content

**User Impact:**
- Difficult to navigate to specific chapter
- Accidental chapter skips (tap wrong item)
- Can't tell which chapter is playing
- Unclear if there are more chapters
- Must scroll away from video to see chapters

**Desktop Layout (Works Well):**
- Sidebar with chapter list (always visible)
- 60px item height (fine for mouse)
- Hover states show interactivity
- Compact layout fits many chapters

**Mobile Layout (Current Problems):**
- Same sidebar scaled down → Too narrow
- Same item heights → Too small for touch
- Hover states don't work on touch → No feedback
- Panel position → Covers video or pushes content

---

## 🎯 Requirements

### Chapter Item Touch Standards

**Item Heights:**
- Desktop: 60px (current, fine for mouse)
- Mobile (< 768px): **72px minimum** (Apple HIG, Material Design)
- Active item: **Larger touch area** with prominent indicator

**Item Spacing:**
- Vertical gap: 4px between items
- Horizontal padding: 16px (up from 12px on mobile)
- Thumbnail-to-text gap: 16px (up from 12px)

### Visual Feedback Requirements

**Touch Feedback:**
- **:active state** - Background darkens immediately on tap
- **Ripple effect** - Optional Material Design ripple animation
- **Haptic feedback** - Vibration on tap (if browser supports)

**Active Chapter Indicator:**
- **Border:** 4px left border (primary color) - desktop uses 3px
- **Background:** Primary color with 10% opacity
- **Icon:** Play icon on right side (25px size)
- **Animation:** Smooth transition when changing chapters

**Scroll Indicators:**
- **Fade at top/bottom** - Gradient showing more content
- **Scroll position indicator** - Progress bar showing position in list
- **Bounce effect** - iOS-style bounce at scroll limits

### Mobile Panel Behavior (Integration with Issue #10)

**Desktop (≥ 768px):**
- Sidebar always visible
- Current behavior unchanged

**Mobile Portrait (< 768px):**
- **Bottom drawer** - Swipe up from bottom to open
- **Collapsed by default** - Only shows when requested
- **Peek mode** - Show first 2-3 chapters when collapsed
- **Full mode** - Swipe up to see all chapters (takes 50% of screen)

**Mobile Landscape (< 768px, horizontal):**
- **Side drawer** - Slides in from right edge
- **Overlay mode** - Transparent overlay behind drawer
- **Quick access** - Tap video → Show chapters drawer
- **Dismiss** - Tap outside drawer or swipe away

---

## 📐 Chapter Item Layout

### Desktop Layout (60px height)

```
┌──────────────────────────────────────┐
│ [Thumb] 00:15:30 │ Chapter Title    │  ← 60px height
│  48x48          │ Subtitle         │
└──────────────────────────────────────┘
```

### Mobile Layout (72px height)

```
┌─────────────────────────────────────────┐
│ [Thumbnail] 00:15:30                    │  ← 72px height
│   64x64     Chapter Title               │
│             Subtitle or Category     [▶]│  ← Play icon
└─────────────────────────────────────────┘
     ^          ^                      ^
  Thumb 64px   Text readable      Active indicator
```

### Active Chapter (Mobile)

```
┌─────────────────────────────────────────┐
│█[Thumb] 00:15:30  Currently Playing  [▶]│  ← 4px border
│█ 64x64  Chapter Title               25px│
│█        Background: primary-10%         │
└─────────────────────────────────────────┘
```

---

## 🎨 Design Requirements

### 1. Touch Target Sizing

**Minimum Sizes:**
- Chapter item height: **72px on mobile** (60px desktop)
- Thumbnail size: **64x64px on mobile** (48x48px desktop)
- Horizontal padding: **16px on mobile** (12px desktop)
- Vertical item gap: **4px** (same on all devices)

**Text Sizing:**
- Timestamp: **16px font** (14px desktop)
- Chapter title: **16px font** (15px desktop)
- Subtitle/category: **14px font** (13px desktop)

### 2. Visual Feedback States

**Normal State:**
- Background: Transparent
- Border: None
- Text: Normal color

**:hover (Desktop Only):**
- Background: `var(--bg-hover)` (subtle gray)
- Cursor: Pointer
- Transition: 200ms ease

**:active (Mobile Touch):**
- Background: `var(--bg-tertiary)` (darker gray)
- Transition: Instant (0ms) for immediate feedback
- Scale: 0.98 (subtle press effect)

**Active Chapter:**
- Background: `rgba(var(--primary-rgb), 0.1)` (10% primary color)
- Border-left: `4px solid var(--primary-color)` (mobile), `3px` (desktop)
- Icon: Play icon (▶) on right, 25px size
- Font-weight: Bold for title

### 3. Scroll Behavior

**Scroll Indicators:**
- **Top fade:** 20px gradient (transparent → background color)
- **Bottom fade:** 20px gradient (background → transparent)
- **Progress bar:** Thin (2px) indicator showing scroll position

**Auto-Scroll:**
- When active chapter changes, scroll to keep it centered
- Smooth scroll animation (300ms ease)
- Don't auto-scroll if user is manually scrolling

**Swipe Gestures (Mobile):**
- Swipe up: Expand drawer to full height (50% screen)
- Swipe down: Collapse drawer to peek mode
- Velocity detection: Fast swipe → Full open/close
- Bounce: iOS-style overscroll bounce

---

## 📋 Implementation Scope

### Files to Modify

**Primary Component:**
- `app/frontend/src/components/ChapterPanel.vue` (or similar name)
- `app/frontend/src/components/ChapterItem.vue` (if separate component)

**Integration with Watch View:**
- `app/frontend/src/views/WatchView.vue` - Panel positioning (bottom drawer on mobile)

**What Needs Changing:**
1. **SCSS Responsive Styles** - Touch target sizing, visual feedback
2. **Chapter Item Markup** - Ensure thumbnail, text, icon layout
3. **Active State Logic** - Track current chapter, update indicator
4. **Scroll Indicators** - Fade gradients, auto-scroll logic
5. **Mobile Drawer** - Bottom/side drawer behavior (coordinate with Issue #10)

---

## ✅ Acceptance Criteria

### Touch Targets (Mobile < 768px)
- [ ] Chapter items: 72px height minimum
- [ ] Thumbnails: 64x64px on mobile
- [ ] Horizontal padding: 16px on mobile
- [ ] Vertical gap: 4px between items
- [ ] All items easily tappable with thumb

### Visual Feedback
- [ ] :active state background darkens on tap
- [ ] Active chapter has 4px left border (primary color)
- [ ] Active chapter background: 10% primary color
- [ ] Play icon (▶) visible on active chapter
- [ ] Smooth transition when changing chapters (300ms)

### Text Readability
- [ ] Timestamps: 16px font on mobile
- [ ] Chapter titles: 16px font on mobile
- [ ] High contrast text (readable in all conditions)
- [ ] No text truncation for short titles
- [ ] Ellipsis for long titles with tooltip

### Scroll Behavior
- [ ] Top/bottom fade gradients visible when scrolling
- [ ] Auto-scroll keeps active chapter centered
- [ ] Smooth scroll animation (300ms ease)
- [ ] Bounce effect at scroll limits (iOS-style)
- [ ] Scroll position indicator (progress bar)

### Mobile Panel Behavior (Integration)
- [ ] Portrait: Bottom drawer, swipe up to open
- [ ] Landscape: Side drawer, slides from right
- [ ] Collapsed by default (doesn't cover video)
- [ ] Swipe gestures work smoothly
- [ ] Tap outside closes drawer

### Desktop (≥ 768px)
- [ ] Layout unchanged (sidebar, 60px items)
- [ ] Hover states work correctly
- [ ] No mobile drawer behavior

### Testing Checklist
- [ ] iPhone SE portrait (375px) - Bottom drawer
- [ ] iPhone 14 Pro portrait (393px) - Bottom drawer
- [ ] iPhone 14 Pro landscape (852px) - Side drawer
- [ ] iPad (768px) → Desktop layout
- [ ] Tap chapter → Seeks correctly
- [ ] Active chapter indicator updates
- [ ] Auto-scroll keeps chapter centered
- [ ] Swipe gestures smooth and responsive

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Touch targets (72px mobile), visual feedback patterns
- `.github/instructions/frontend.instructions.md` - SCSS mixins, state management

**Touch Target Guidelines:**
- [Apple HIG - Touch Targets](https://developer.apple.com/design/human-interface-guidelines/inputs/touch/)
- [Material Design - Touch Targets](https://m3.material.io/foundations/interaction/gestures/touch-targets)

**Related Issues:**
- Issue #10: Watch View Mobile (chapter panel positioning - bottom/side drawer)
- Issue #9: Video Player Controls (same touch target standards)
- Issue #13: Notifications Panel (similar list with touch targets)

**Swipe Gesture Libraries:**
- Consider using Vue Swipe library for drawer behavior
- Or implement with native touch events (touchstart/touchmove/touchend)

---

## 🎯 Solution

### Mobile-Optimized Chapter Navigation

**Desktop:**
- Sidebar with chapter list
- Hover states
- Compact layout

**Mobile:**
- Bottom drawer (implemented in Watch View task)
- Larger touch targets (56px height)
- Clear active indicator
- Swipeable

---

## 📋 Implementation Tasks

### 1. Chapter Item Touch Targets (1 hour)

```vue
<template>
  <div class="chapter-list">
    <button
      v-for="chapter in chapters"
      :key="chapter.id"
      class="chapter-item"
      :class="{ active: isActive(chapter) }"
      @click="$emit('seek', chapter.start_time)"
    >
      <div class="chapter-thumbnail" v-if="chapter.thumbnail_url">
        <img :src="chapter.thumbnail_url" :alt="chapter.title" />
      </div>
      
      <div class="chapter-info">
        <span class="chapter-time">{{ formatTime(chapter.start_time) }}</span>
        <span class="chapter-title">{{ chapter.title }}</span>
      </div>
      
      <div class="chapter-indicator" v-if="isActive(chapter)">
        <i class="icon-play"></i>
      </div>
    </button>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.chapter-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: background 0.2s;
  
  // Desktop: Compact
  min-height: 60px;
  
  &:hover {
    background: var(--bg-hover);
  }
  
  &.active {
    background: rgba(var(--primary-rgb), 0.1);
    border-left: 3px solid var(--primary-color);
  }
  
  @include m.respond-below('md') {
    // Mobile: Larger touch targets
    min-height: 72px;
    padding: 12px 16px;
    gap: 16px;
    
    // Active state feedback
    &:active {
      background: var(--bg-tertiary);
    }
    
    &.active {
      border-left-width: 4px;
    }
  }
}
</style>
```

---

### 2. Typography & Readability (30 minutes)

```scss
.chapter-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0; // Allow text truncation
  
  .chapter-time {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
    
    @include m.respond-below('md') {
      font-size: 14px; // Larger on mobile
    }
  }
  
  .chapter-title {
    font-size: 14px;
    color: var(--text-primary);
    
    // Truncate long titles
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    
    @include m.respond-below('md') {
      font-size: 16px; // Larger, more readable
      
      // Allow 2 lines on mobile
      white-space: normal;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
    }
  }
}

.chapter-thumbnail {
  width: 80px;
  height: 45px;
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
  background: var(--bg-tertiary);
  
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  
  @include m.respond-below('md') {
    width: 96px;
    height: 54px; // Larger thumbnails on mobile
  }
}
```

---

### 3. Active Chapter Indicator (30 minutes)

```scss
.chapter-indicator {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-color);
  flex-shrink: 0;
  
  i {
    font-size: 16px;
  }
  
  @include m.respond-below('md') {
    width: 40px;
    height: 40px;
    
    i {
      font-size: 20px;
    }
  }
}
```

---

### 4. Scroll Indicator (30 minutes)

```vue
<template>
  <div class="chapter-list-container">
    <div 
      class="chapter-list"
      @scroll="handleScroll"
      ref="chapterListRef"
    >
      <!-- Chapter items -->
    </div>
    
    <!-- Scroll indicators -->
    <div v-if="showTopShadow" class="scroll-shadow top"></div>
    <div v-if="showBottomShadow" class="scroll-shadow bottom"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const chapterListRef = ref<HTMLElement | null>(null)
const showTopShadow = ref(false)
const showBottomShadow = ref(false)

const handleScroll = (e: Event) => {
  const el = e.target as HTMLElement
  
  showTopShadow.value = el.scrollTop > 10
  showBottomShadow.value = el.scrollTop < (el.scrollHeight - el.clientHeight - 10)
}

onMounted(() => {
  // Check initial scroll state
  if (chapterListRef.value) {
    const el = chapterListRef.value
    showBottomShadow.value = el.scrollHeight > el.clientHeight
  }
})
</script>

<style scoped lang="scss">
.chapter-list-container {
  position: relative;
  
  .chapter-list {
    overflow-y: auto;
    max-height: 100%;
  }
  
  .scroll-shadow {
    position: absolute;
    left: 0;
    right: 0;
    height: 20px;
    pointer-events: none;
    z-index: 10;
    
    &.top {
      top: 0;
      background: linear-gradient(
        to bottom,
        var(--bg-primary),
        transparent
      );
    }
    
    &.bottom {
      bottom: 0;
      background: linear-gradient(
        to top,
        var(--bg-primary),
        transparent
      );
    }
  }
}
</style>
```

---

### 5. Empty State & Loading (20 minutes)

```vue
<template>
  <div class="chapter-list">
    <!-- Loading state -->
    <div v-if="loading" class="chapter-loading">
      <div class="skeleton-item" v-for="i in 5" :key="i">
        <div class="skeleton-thumbnail"></div>
        <div class="skeleton-text"></div>
      </div>
    </div>
    
    <!-- Empty state -->
    <div v-else-if="chapters.length === 0" class="chapter-empty">
      <i class="icon-list"></i>
      <p>No chapters available</p>
    </div>
    
    <!-- Chapter items -->
    <button v-else v-for="chapter in chapters" ...>
      <!-- Chapter content -->
    </button>
  </div>
</template>

<style scoped lang="scss">
.chapter-empty {
  padding: 40px 20px;
  text-align: center;
  color: var(--text-tertiary);
  
  i {
    font-size: 48px;
    margin-bottom: 12px;
    opacity: 0.5;
  }
  
  p {
    font-size: 14px;
  }
}

.skeleton-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  
  .skeleton-thumbnail {
    width: 80px;
    height: 45px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  .skeleton-text {
    flex: 1;
    height: 45px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    animation: pulse 1.5s ease-in-out infinite;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
```

---

## 📂 Files to Modify

- `app/frontend/src/components/chapters/ChapterList.vue`
- `app/frontend/src/views/WatchView.vue` (integration)

---

## ✅ Acceptance Criteria

**Touch Targets:**
- [ ] Chapter items 72px height on mobile (60px desktop)
- [ ] Full-width tappable area
- [ ] No accidental skips
- [ ] Active state visual feedback

**Typography:**
- [ ] Time 14px on mobile (12px desktop)
- [ ] Title 16px on mobile, allows 2 lines
- [ ] All text readable without zoom
- [ ] Proper truncation with ellipsis

**Visual Indicators:**
- [ ] Active chapter clearly marked (border + background)
- [ ] Scroll shadows show more content above/below
- [ ] Thumbnail 96×54px on mobile (80×45px desktop)
- [ ] Play icon on active chapter

**Interaction:**
- [ ] Tap chapter → Seeks to timestamp
- [ ] Smooth scroll
- [ ] Visual feedback on tap (active state)
- [ ] Works in bottom drawer on mobile

**States:**
- [ ] Loading skeleton shown while fetching
- [ ] Empty state when no chapters
- [ ] Active chapter updates as video plays
- [ ] Scroll position maintained after seek

---

## 🧪 Testing Checklist

**Device Testing:**
- [ ] iPhone SE (375px)
- [ ] iPhone 12 (390px)
- [ ] Android (360px, 412px)
- [ ] iPad (768px)
- [ ] Desktop (1024px+)

**Interaction Testing:**
- [ ] Tap first chapter → Seeks to start
- [ ] Tap middle chapter → Seeks correctly
- [ ] Scroll to bottom → Shadow appears at top
- [ ] Active chapter updates during playback
- [ ] Tap same chapter again → No issues

**Visual Testing:**
- [ ] Thumbnails load correctly
- [ ] Text doesn't overflow
- [ ] Active indicator visible
- [ ] Scroll shadows smooth
- [ ] Loading skeleton looks good

**Edge Cases:**
- [ ] 1 chapter → No scroll needed
- [ ] 100+ chapters → Scroll performance OK
- [ ] Very long chapter title → Truncates properly
- [ ] No thumbnails → Layout still works
- [ ] Chapter at 0:00 → Shows correctly

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md`  
**Design:** `docs/DESIGN_SYSTEM.md`  
**Related:** Issue #10 (Watch View Mobile)

---

## 🤖 Copilot Instructions

**Context:**
Make chapters panel mobile-friendly with larger touch targets, better typography, scroll indicators, and clear active state. Current implementation has small tap areas and poor readability on mobile.

**Critical Patterns:**

1. **Touch-friendly items:**
   ```scss
   .chapter-item {
     min-height: 72px; // Mobile
     padding: 12px 16px;
   }
   ```

2. **Multi-line title truncation:**
   ```scss
   white-space: normal;
   -webkit-line-clamp: 2;
   -webkit-box-orient: vertical;
   ```

3. **Scroll shadows:**
   ```typescript
   showTopShadow.value = el.scrollTop > 10
   showBottomShadow.value = el.scrollTop < (el.scrollHeight - el.clientHeight - 10)
   ```

4. **Active state:**
   ```scss
   &.active {
     background: rgba(var(--primary-rgb), 0.1);
     border-left: 4px solid var(--primary-color);
   }
   ```

**Implementation Order:**
1. Increase touch target sizes
2. Improve typography and truncation
3. Add active chapter indicator
4. Implement scroll shadows
5. Add loading/empty states

**Testing Strategy:**
1. Test with 1, 10, and 100+ chapters
2. Verify active chapter updates during playback
3. Test touch accuracy on iPhone SE
4. Check scroll shadow appearance
5. Verify thumbnail loading

**Files to Read First:**
- `app/frontend/src/components/chapters/ChapterList.vue`
- `docs/DESIGN_SYSTEM.md` (skeleton patterns)
- Issue #10 template (bottom drawer integration)

**Success Criteria:**
Chapter items 72px on mobile, text 16px, active indicator clear, scroll shadows work, loading/empty states, works in bottom drawer.

**Common Pitfalls:**
- ❌ Touch targets < 60px
- ❌ Not showing scroll indicators
- ❌ Active chapter not updating
- ❌ Text overflow on long titles
- ❌ Not testing with many chapters
