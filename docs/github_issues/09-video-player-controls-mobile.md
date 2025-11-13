# Video Player Controls Mobile Responsive

## 🟡 Priority: HIGH
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 2-3 hours  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** HIGH - Core playback functionality on mobile devices

---

## 📝 Problem Description

### Current State: Video Controls Not Touch-Optimized

**Issues on Mobile (< 768px):**
- ❌ **Play/pause button too small** - 36px (need 48px minimum)
- ❌ **Volume slider difficult to use** - Thin slider hard to drag with finger
- ❌ **Progress bar scrubbing imprecise** - Narrow progress bar, small thumb
- ❌ **Fullscreen button cramped** - Buttons too close together
- ❌ **Control overlay timing wrong** - Disappears too quickly after touch

**User Impact:**
- Users miss play/pause button frequently
- Volume adjustment frustrating (overshoots target)
- Can't precisely seek to timestamp
- Accidental button presses
- Controls vanish while trying to use them

---

## 🎯 Requirements

### Touch Target Standards

**Apple Human Interface Guidelines & Material Design:**
- Minimum touch target: **44x44px**
- Recommended: **48x48px**
- Spacing between targets: **8px minimum**

### Current vs Required Sizes

| Control | Desktop | Mobile (Current) | Mobile (Required) |
|---------|---------|------------------|-------------------|
| Play/Pause | 36px | 36px | **56px** (primary) |
| Other Buttons | 36px | 36px | **48px** |
| Progress Bar Height | 4px | 4px | **12px** |
| Progress Thumb | 12px | 12px | **24px** |
| Button Spacing | 8px | 8px | **16px** |

---

## 🎨 Design Requirements

### 1. Button Sizing
- **Play/Pause button:** 56x56px on mobile (primary control, largest)
- **Secondary buttons:** 48x48px (volume, fullscreen, chapters, settings)
- **Icon size:** Scale up 1.5x on mobile
- **Button spacing:** 16px between controls

### 2. Progress Bar Enhancement
- **Height:** 12px on mobile (from 4px)
- **Thumb size:** 24x24px with 2px white border
- **Tap area:** 48px vertical (invisible extended hit area)
- **Scrubbing feedback:** Show timestamp tooltip on touch

### 3. Control Overlay Behavior
- **Show duration:** 5 seconds (from 3 seconds) after touch
- **Keep visible:** While finger is down
- **Fade transition:** Smooth 300ms fade
- **Tap anywhere:** Show controls if hidden

### 4. Simplified Mobile Layout
**Hide on mobile (< 768px):**
- Quality/speed selectors (move to overflow menu)
- Detailed timestamp display (keep simple M:SS)

**Keep visible:**
- Play/pause (center, large)
- Volume toggle (left)
- Fullscreen (right)
- Progress bar (bottom, prominent)

---

## 📋 Implementation Scope

### Files to Modify

**Primary Component:**
- `app/frontend/src/components/VideoPlayer.vue` or `app/frontend/src/components/video/VideoPlayer.vue`

**What Needs Changing:**
1. **SCSS Responsive Styles** - Add mobile breakpoint overrides
2. **Touch Event Handlers** - Extend overlay visibility on touch
3. **Progress Bar Component** - Larger thumb, wider tap area
4. **Button Markup** - Ensure proper spacing and sizing

---

## ✅ Acceptance Criteria

### Functional Requirements
- [ ] All control buttons minimum 48x48px on mobile (< 768px)
- [ ] Play/pause button 56x56px on mobile
- [ ] Progress bar height 12px on mobile
- [ ] Progress bar thumb 24x24px on mobile
- [ ] Button spacing 16px minimum on mobile
- [ ] Controls stay visible 5 seconds after touch
- [ ] Tapping video shows/hides controls correctly

### Visual Requirements
- [ ] Icons scale appropriately (readable at larger sizes)
- [ ] Buttons don't overlap or appear cramped
- [ ] Progress bar visually prominent
- [ ] Smooth transitions when showing/hiding controls
- [ ] Consistent with app's glassmorphism design

### Touch Interaction
- [ ] All buttons easily tappable with thumb
- [ ] No accidental button presses
- [ ] Progress bar scrubbing accurate
- [ ] Volume adjustment smooth
- [ ] Fullscreen toggle reliable

### Testing Checklist
- [ ] Test on iPhone SE (375px width) - smallest target
- [ ] Test on iPhone 14 Pro (393px width)
- [ ] Test on iPad (768px width)
- [ ] Test in portrait and landscape orientations
- [ ] Verify touch targets with pointer device
- [ ] Test rapid play/pause tapping
- [ ] Test progress bar scrubbing precision
- [ ] Verify controls don't disappear while adjusting

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Touch target standards, mobile breakpoints
- `.github/instructions/frontend.instructions.md` - SCSS patterns, responsive design

**Similar Components:**
- `app/frontend/src/views/WatchView.vue` - Video page layout
- Mobile breakpoint mixin: `@include m.respond-below('md')`

**Touch Guidelines:**
- [Apple HIG Touch Targets](https://developer.apple.com/design/human-interface-guidelines/inputs/touch/)
- [Material Design Touch Targets](https://m3.material.io/foundations/interaction/gestures/touch-targets)

**Related Issues:**
- Issue #10: Watch View Mobile Responsive (overall layout)
- Issue #12: Chapters Panel Mobile (chapter navigation)
- Issue #4: Settings Tables Mobile (similar touch target fixes)

---

## 🎯 Solution

### Touch-Optimized Player Controls

1. **Larger Touch Targets** - 48px+ buttons
2. **Better Scrubbing** - Wider progress bar with larger thumb
3. **Touch-Aware Overlay** - Stay visible longer after touch
4. **Simplified Mobile Layout** - Hide less-used controls

---

## 📋 Implementation Tasks

### 1. Increase Button Sizes (1 hour)

**File:** `app/frontend/src/components/video/VideoPlayer.vue`

```scss
@use '@/styles/mixins' as m;

.player-controls {
  .control-btn {
    // Desktop: 36px
    width: 36px;
    height: 36px;
    
    @include m.respond-below('md') {
      // Mobile: 48px (touch-friendly)
      width: 48px;
      height: 48px;
      font-size: 24px;  // Larger icons
    }
  }
  
  .play-pause-btn {
    // Primary control - extra large
    width: 48px;
    height: 48px;
    
    @include m.respond-below('md') {
      width: 56px;
      height: 56px;
      font-size: 28px;
    }
  }
}
```

---

### 2. Improve Progress Bar (30 minutes)

```scss
.progress-bar {
  height: 8px;  // Desktop
  
  @include m.respond-below('md') {
    height: 12px;  // Thicker on mobile
    margin: 12px 0;  // More spacing
  }
  
  .progress-thumb {
    width: 16px;
    height: 16px;
    
    @include m.respond-below('md') {
      width: 24px;  // Larger thumb for touch
      height: 24px;
      border: 2px solid white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
  }
}
```

---

### 3. Touch-Aware Overlay (45 minutes)

**Update JavaScript Logic:**

```typescript
const isTouchDevice = ref(false)
const controlsVisible = ref(true)
const hideControlsTimeout = ref<number | null>(null)

// Detect touch device
onMounted(() => {
  isTouchDevice.value = 'ontouchstart' in window || navigator.maxTouchPoints > 0
})

// Show controls with longer timeout on touch
const showControls = () => {
  controlsVisible.value = true
  
  if (hideControlsTimeout.value) {
    clearTimeout(hideControlsTimeout.value)
  }
  
  // Longer delay for touch devices
  const delay = isTouchDevice.value ? 5000 : 3000
  
  hideControlsTimeout.value = setTimeout(() => {
    if (!playerPaused.value) {
      controlsVisible.value = false
    }
  }, delay)
}

// Keep controls visible while interacting
const handleTouch = () => {
  showControls()
}
```

**Template:**
```vue
<div 
  class="video-player"
  @click="showControls"
  @touchstart="handleTouch"
  @mousemove="showControls"
>
  <!-- Video element -->
  
  <div 
    v-show="controlsVisible || playerPaused"
    class="controls-overlay"
  >
    <!-- Controls -->
  </div>
</div>
```

---

### 4. Simplified Mobile Layout (45 minutes)

```vue
<template>
  <div class="player-controls">
    <!-- Left Controls -->
    <div class="controls-left">
      <button class="control-btn play-pause-btn" @click="togglePlayPause">
        <i :class="playerPaused ? 'icon-play' : 'icon-pause'"></i>
      </button>
      
      <!-- Desktop: Show volume -->
      <div v-if="!isMobile" class="volume-control">
        <button class="control-btn" @click="toggleMute">
          <i :class="volumeIcon"></i>
        </button>
        <input type="range" v-model="volume" min="0" max="100" />
      </div>
    </div>
    
    <!-- Center: Time (always visible) -->
    <div class="controls-center">
      <span class="time-display">{{ currentTime }} / {{ duration }}</span>
    </div>
    
    <!-- Right Controls -->
    <div class="controls-right">
      <!-- Mobile: Only fullscreen + settings -->
      <template v-if="isMobile">
        <button class="control-btn" @click="toggleFullscreen">
          <i class="icon-fullscreen"></i>
        </button>
      </template>
      
      <!-- Desktop: All controls -->
      <template v-else>
        <button class="control-btn" @click="togglePip">
          <i class="icon-pip"></i>
        </button>
        <button class="control-btn" @click="toggleTheater">
          <i class="icon-theater"></i>
        </button>
        <button class="control-btn" @click="openSettings">
          <i class="icon-settings"></i>
        </button>
        <button class="control-btn" @click="toggleFullscreen">
          <i class="icon-fullscreen"></i>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const isMobile = ref(false)

onMounted(() => {
  isMobile.value = window.innerWidth < 768
  
  window.addEventListener('resize', () => {
    isMobile.value = window.innerWidth < 768
  })
})
</script>
```

---

## 📂 Files to Modify

- `app/frontend/src/components/video/VideoPlayer.vue`
- `app/frontend/src/styles/_video-player.scss` (if separate)

---

## ✅ Acceptance Criteria

**Touch Targets:**
- [ ] All buttons minimum 48px × 48px on mobile
- [ ] Play/pause button 56px × 56px (primary control)
- [ ] Progress bar 12px height on mobile
- [ ] Progress thumb 24px (easy to grab)

**Overlay Behavior:**
- [ ] Controls show on tap
- [ ] Controls stay visible 5s on touch devices (3s desktop)
- [ ] Controls stay visible while paused
- [ ] Controls fade smoothly

**Mobile Layout:**
- [ ] Volume control hidden on mobile (use device volume)
- [ ] Only essential controls shown (play, fullscreen, time)
- [ ] Controls don't overlap video
- [ ] Layout works in portrait and landscape

**Interaction:**
- [ ] Play/pause tap works every time
- [ ] Progress bar scrubbing accurate
- [ ] Fullscreen button works
- [ ] No accidental control triggers
- [ ] Double-tap doesn't zoom (CSS touch-action)

---

## 🧪 Testing Checklist

**Device Testing:**
- [ ] iPhone SE (375px portrait)
- [ ] iPhone 12/13/14 (390px portrait, 844px landscape)
- [ ] Android (360px, 412px)
- [ ] iPad portrait (768px)
- [ ] Desktop (1024px+)

**Interaction Testing:**
- [ ] Tap play/pause → Toggles reliably
- [ ] Tap progress bar → Seeks to position
- [ ] Drag progress thumb → Smooth scrubbing
- [ ] Tap fullscreen → Enters fullscreen mode
- [ ] Tap while playing → Shows controls for 5s
- [ ] Pause → Controls stay visible
- [ ] Resume → Controls auto-hide after 5s

**Edge Cases:**
- [ ] Very short video (< 1 minute) → Controls still work
- [ ] Very long video (> 2 hours) → Time display correct
- [ ] Fullscreen + rotate → Controls adjust
- [ ] Interrupted video → Controls responsive

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md`  
**Related:** `docs/REMAINING_FRONTEND_TASKS.md`  
**Design:** `docs/DESIGN_SYSTEM.md` (Touch target guidelines)

---

## 🤖 Copilot Instructions

**Context:**
Make video player controls touch-friendly for mobile devices. Current controls have small buttons and difficult-to-use scrubbing, making video playback frustrating on phones.

**Critical Patterns:**
1. **Touch target sizing:**
   ```scss
   @include m.respond-below('md') {
     .control-btn {
       width: 48px;
       height: 48px;
       font-size: 24px;
     }
   }
   ```

2. **Touch-aware overlay:**
   ```typescript
   const isTouchDevice = 'ontouchstart' in window
   const delay = isTouchDevice ? 5000 : 3000
   ```

3. **Simplified mobile layout:**
   ```vue
   <template v-if="isMobile">
     <!-- Only essential controls -->
   </template>
   ```

4. **Prevent zoom on double-tap:**
   ```css
   .video-player {
     touch-action: manipulation;  /* Disable double-tap zoom */
   }
   ```

**Implementation Order:**
1. Increase button sizes (mobile breakpoint)
2. Improve progress bar thickness and thumb size
3. Add touch detection and longer overlay timeout
4. Simplify controls layout for mobile
5. Test on real devices

**Testing Strategy:**
1. Test on Safari iOS (most important for mobile)
2. Verify touch targets with Chrome DevTools touch emulation
3. Test in landscape and portrait
4. Verify no double-tap zoom interference
5. Test with real fingers (not mouse/stylus)

**Files to Read First:**
- `app/frontend/src/components/video/VideoPlayer.vue` (current implementation)
- `docs/DESIGN_SYSTEM.md` (touch target guidelines - 44px minimum)
- `.github/instructions/frontend.instructions.md` (mobile patterns)

**Success Criteria:**
All controls 48px+ on mobile, progress bar easy to scrub, overlay stays visible 5s on touch, simplified layout, works on Safari iOS.

**Common Pitfalls:**
- ❌ Not testing on real iOS device (Safari behavior differs)
- ❌ Touch targets < 44px (Apple HIG minimum)
- ❌ Not disabling double-tap zoom
- ❌ Controls auto-hide too quickly on touch
- ❌ Not detecting touch device correctly
- ❌ Forgetting landscape orientation testing
