# Watch View - Video Layout Mobile Optimization

## 🟡 Priority: HIGH
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 30-45 minutes  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** HIGH - Core viewing experience on mobile
**Dependencies:** None (can run in parallel)

---

## 📝 Problem Description

### Current State: Video Player Not Mobile-Optimized

**Issues on Mobile (< 768px):**
- ❌ **Video doesn't use full screen width** - Has desktop margins/max-width
- ❌ **Aspect ratio wasteful** - Letterboxing on portrait orientation
- ❌ **Landscape mode not immersive** - Same 16:9 constraint, doesn't fill screen

**User Impact:**
- Tiny video player on small screens (unnecessary side margins)
- Black bars on portrait (video should use full width)
- Landscape mode feels cramped (should be immersive fullscreen)

**Desktop Layout (Correct - Don't Change):**
- 16:9 video with max-width constraint (1280px)
- Centered with margins
- Plenty of screen real estate

**Mobile Layout (Current Problems):**
- Same desktop layout scaled down
- max-width constraint wasted on narrow screens
- Portrait: Could use full viewport width
- Landscape: Could fill viewport height

---

## 🎯 Requirements

### Portrait Mode (< 768px, vertical orientation)
**Video Container:**
- **Width:** Full viewport width (100vw, no margins)
- **Aspect Ratio:** 16:9 maintained
- **Max-Width:** Remove constraint on mobile (100% not 1280px)
- **Centering:** No horizontal centering needed (already full-width)

### Landscape Mode (< 768px, horizontal orientation)
**Video Container:**
- **Height:** Fill viewport height (100vh)
- **Aspect Ratio:** Auto (let browser calculate based on height)
- **Behavior:** Immersive fullscreen video experience
- **System UI:** Overlays video (doesn't push it)

### Desktop (≥ 768px)
**No Changes Required:**
- Keep current 1280px max-width
- Keep current aspect-ratio: 16/9
- Keep centered layout

---

## 📐 Layout Architecture

### Portrait Mode (Mobile < 768px)

```
Before:
┌─────────────────────────────┐
│ [Margin]                     │
│  ┌───────────────────┐       │  ← Wasted space
│  │   Video Player    │       │
│  │   (max-width)     │       │
│  └───────────────────┘       │
│ [Margin]                     │
└─────────────────────────────┘

After:
┌─────────────────────────────┐
│    Video Player (100vw)     │  ← Full width
│    Aspect ratio: 16:9       │
│                             │
└─────────────────────────────┘
```

### Landscape Mode (Mobile < 768px)

```
Before:
┌────────────────────────────────┐
│  [Video with 16:9 constraint] │  ← Small video
│  [Black bars top/bottom]      │
└────────────────────────────────┘

After:
┌────────────────────────────────┐
│                                │
│    Video fills screen (100vh)  │  ← Immersive
│                                │
└────────────────────────────────┘
```

---

## 🎨 Design Requirements

### 1. Responsive Breakpoints
- **Mobile:** `< 768px` (standard app breakpoint)
- **Portrait Detection:** `orientation: portrait`
- **Landscape Detection:** `orientation: landscape`

### 2. Video Container Styling

**Desktop (≥ 768px):**
```scss
.video-container {
  max-width: 1280px;  // Keep existing
  aspect-ratio: 16/9; // Keep existing
  margin: 0 auto;     // Keep existing
}
```

**Mobile Portrait (< 768px):**
```scss
@include m.respond-below('md') {
  .video-container {
    max-width: 100%;   // Remove constraint
    width: 100vw;      // Full viewport width
    margin: 0;         // Remove centering
    aspect-ratio: 16/9; // Maintain ratio
  }
}
```

**Mobile Landscape (< 768px + horizontal):**
```scss
@media (orientation: landscape) and (max-width: 767px) {
  .video-container {
    height: 100vh;     // Fill screen height
    aspect-ratio: auto; // Let browser calculate
    width: auto;       // Calculated from height
  }
}
```

### 3. Video Element Behavior
- **object-fit:** `contain` (no cropping, letterbox if needed)
- **background:** `#000` (black letterbox bars)
- **display:** `block` (remove inline spacing)

---

## 📋 Implementation Scope

### Files to Modify

**Primary File:**
- `app/frontend/src/views/WatchView.vue`

**Section to Modify:**
- `.video-container` or `.video-section` SCSS styles
- Only the container div wrapping `<VideoPlayer>` component

**What Needs Changing:**
1. **Add mobile breakpoint** - `@include m.respond-below('md')`
2. **Remove max-width** - Set to 100% on mobile
3. **Add full-width** - Set width to 100vw on mobile
4. **Remove margins** - Set to 0 on mobile
5. **Add landscape override** - Media query for orientation
6. **Set height in landscape** - 100vh for immersive mode

**What NOT to Change:**
- ❌ VideoPlayer component itself (Issue #9 handles controls)
- ❌ Info panel section (Issue #10B handles collapsible panel)
- ❌ Chapter drawer (Issue #10C handles drawer)
- ❌ Desktop styles (≥ 768px unchanged)

---

## ✅ Acceptance Criteria

### Portrait Mode (< 768px)
- [ ] Video uses full viewport width (100vw)
- [ ] No horizontal margins or padding
- [ ] Aspect ratio maintained at 16:9
- [ ] No horizontal scrollbar
- [ ] Video centered vertically if shorter than viewport

### Landscape Mode (< 768px, horizontal)
- [ ] Video fills screen height (100vh)
- [ ] Aspect ratio auto-calculated from height
- [ ] No black bars (or minimal if aspect ratio differs)
- [ ] Immersive fullscreen experience

### Desktop (≥ 768px)
- [ ] Layout unchanged (1280px max-width preserved)
- [ ] Centered with margins preserved
- [ ] Aspect ratio 16:9 preserved

### Responsive Behavior
- [ ] Rotate device portrait → landscape → Layout adapts smoothly
- [ ] Resize browser window → Transitions smoothly
- [ ] No layout shift or jump when rotating
- [ ] Video continues playing during rotation

### Visual Quality
- [ ] No pixelation or stretching
- [ ] Black letterbox bars if aspect ratio differs
- [ ] No white bars or gaps around video
- [ ] Video scales smoothly (no jagged edges)

### Testing Checklist
- [ ] iPhone SE portrait (375px width) - Full width
- [ ] iPhone 14 Pro portrait (393px width) - Full width
- [ ] iPhone 14 Pro landscape (852px width) - Full height
- [ ] iPad portrait (768px) → Desktop layout (unchanged)
- [ ] Rotate device mid-playback → No pause or glitch
- [ ] Test with 16:9 video (standard)
- [ ] Test with 21:9 video (ultrawide) - Letterbox OK

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Mobile breakpoints, responsive patterns
- `.github/instructions/frontend.instructions.md` - SCSS mixins

**Breakpoint Mixin:**
```scss
@use '@/styles/mixins' as m;

@include m.respond-below('md') {
  // Mobile styles (< 768px)
}
```

**Orientation Detection:**
```scss
@media (orientation: landscape) {
  // Horizontal orientation
}

@media (orientation: portrait) {
  // Vertical orientation
}
```

**Related Issues:**
- Issue #9: Video Player Controls Mobile (button sizing - separate concern)
- Issue #10B: Watch View - Info Panel (collapsible panel - next task)
- Issue #10C: Watch View - Chapter Drawer (drawer positioning - depends on #12)

**Related Components:**
- `app/frontend/src/components/VideoPlayer.vue` - Video playback component (don't modify)
- `app/frontend/src/views/WatchView.vue` - Parent layout (modify container only)

---

## 🚀 Implementation Guide

### Step 1: Locate Video Container (5 min)
1. Open `app/frontend/src/views/WatchView.vue`
2. Find `.video-container` or `.video-section` class
3. Identify the div wrapping `<VideoPlayer>` component

### Step 2: Add Mobile Breakpoint (10 min)
```scss
.video-container {
  // Desktop styles (keep existing)
  max-width: 1280px;
  aspect-ratio: 16/9;
  margin: 0 auto;
  
  // Mobile portrait: Full-width
  @include m.respond-below('md') {
    max-width: 100%;
    width: 100vw;
    margin: 0;
    aspect-ratio: 16/9; // Keep 16:9 for portrait
  }
}
```

### Step 3: Add Landscape Override (10 min)
```scss
.video-container {
  // ... existing styles ...
  
  // Mobile landscape: Immersive fullscreen
  @media (orientation: landscape) and (max-width: 767px) {
    height: 100vh;
    aspect-ratio: auto; // Let browser calculate from height
    width: auto;
  }
}
```

### Step 4: Test Responsiveness (10 min)
1. Open browser DevTools (F12)
2. Toggle device toolbar (Ctrl+Shift+M)
3. Test iPhone SE (375px portrait)
4. Rotate to landscape (667px × 375px)
5. Verify video fills screen in both orientations

### Step 5: Edge Case Testing (5 min)
- Test mid-playback rotation (video shouldn't restart)
- Test with long video title (layout shouldn't break)
- Test on iPad (768px → Should use desktop layout)

---

## ⚠️ Common Pitfalls to Avoid

1. **❌ Don't modify VideoPlayer component**
   - Only change container div in WatchView.vue
   - Player controls handled by Issue #9

2. **❌ Don't change desktop layout**
   - Keep max-width: 1280px for ≥ 768px
   - Only apply changes inside mobile breakpoint

3. **❌ Don't forget orientation media query**
   - Landscape needs separate treatment
   - Portrait and landscape have different requirements

4. **❌ Don't use viewport units for desktop**
   - 100vw causes horizontal scrollbar on some browsers
   - Only use 100vw inside mobile breakpoint

5. **❌ Don't touch info panel or chapters**
   - This task is ONLY video container layout
   - Info panel = Issue #10B
   - Chapter drawer = Issue #10C

---

## 🎯 Success Criteria

**Task Complete When:**
- ✅ Video uses full screen width on mobile portrait
- ✅ Video fills screen height on mobile landscape
- ✅ Desktop layout unchanged (≥ 768px)
- ✅ Smooth rotation transitions
- ✅ No layout shift or jump
- ✅ Tested on iPhone/Android simulators

**Ready for Next Task (#10B):**
- ✅ Video container layout optimized
- ✅ No conflicts with other WatchView sections
- ✅ Commit merged to develop branch

---

## 📊 Estimated Breakdown

- **Analysis:** 5 minutes (locate video container)
- **Implementation:** 20 minutes (SCSS breakpoints)
- **Testing:** 15 minutes (portrait, landscape, desktop)
- **Edge Cases:** 5 minutes (rotation, iPad boundary)

**Total:** 30-45 minutes

---

## 🤖 Agent Recommendation

**Primary Agent:** `mobile-specialist`  
**Backup Agent:** `feature-builder`

**Why mobile-specialist:**
- Responsive design patterns
- Mobile breakpoint expertise
- Orientation handling experience

**Copilot Command:**
```bash
@copilot with agent mobile-specialist: Optimize video container for mobile full-width portrait and immersive landscape mode
```
