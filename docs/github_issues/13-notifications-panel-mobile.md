# Notifications Panel Mobile Responsive

## 🟢 Priority: MEDIUM
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 1-2 hours  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** MEDIUM - Notification UX on mobile

---

## 📝 Problem Description

### Current State: Notifications Too Compact for Touch

**Issues on Mobile (< 768px):**
- ❌ **Notification items too compact** - 60px height, need 72px+ for touch
- ❌ **Timestamps cut off** - Narrow layout truncates relative times ("2 hours ago...")
- ❌ **Clear/dismiss button too small** - 32px button hard to tap accurately
- ❌ **No swipe-to-dismiss** - Must tap tiny X button to dismiss
- ❌ **Icons misaligned** - Vertical alignment off on small screens

**User Impact:**
- Hard to read notification messages
- Can't see full timestamp
- Accidental dismissal (tap wrong area)
- No quick gesture to clear notifications
- Looks cramped and unprofessional

**Desktop Layout (Works Well):**
- Compact 60px items fit many notifications
- Hover states show interactivity
- Small dismiss buttons (32px) fine for mouse
- Full timestamps visible

**Mobile Layout (Current Problems):**
- Same 60px heights → Too small for touch
- Same button sizes → Too small for fingers
- No touch gestures → Must tap tiny buttons
- Timestamps wrap → "2 hours..." instead of "2 hours ago"

---

## 🎯 Requirements

### Notification Item Touch Standards

**Item Heights:**
- Desktop: 60px (current, fine for mouse)
- Mobile (< 768px): **72px minimum** (Apple HIG standard)
- Extra spacing for multi-line messages: **Auto-height with 72px minimum**

**Touch Target Sizes:**
- Dismiss button: **48x48px on mobile** (up from 32px)
- Icon area: **40x40px on mobile** (up from 32px)
- Full item tappable: Yes (tap anywhere to view details)

**Spacing:**
- Horizontal padding: 16px (up from 12px on mobile)
- Vertical gap between items: 8px
- Icon-to-text gap: 16px (up from 12px)

### Visual Feedback Requirements

**Touch Feedback:**
- **:active state** - Background darkens on tap
- **Swipe gesture** - Horizontal swipe reveals delete action
- **Delete confirmation** - Fade-out animation when dismissed

**Type Indicators:**
- **Border-left:** 3px colored border by type
  - Success: Green border
  - Error: Red border
  - Warning: Orange border
  - Info: Blue border
- **Icon:** Type-specific icon (✓, ✕, ⚠, ℹ)
- **Icon background:** Subtle colored background matching type

### Swipe-to-Dismiss Gesture (Mobile Only)

**Behavior:**
- Swipe left on notification item → Reveal delete button
- Swipe right → Same (bidirectional support)
- Threshold: 80px swipe distance to trigger
- Velocity detection: Fast swipe → Instant delete
- Cancel: Swipe back → Item returns to position

**Visual Feedback:**
- Red background revealed behind item during swipe
- Trash icon appears in revealed area
- Item follows finger with resistance effect
- Delete animation: Fade out + slide away (300ms)

---

## 📐 Notification Item Layout

### Desktop Layout (60px height)

```
┌─────────────────────────────────────────────┐
│ [Icon] Message text here...       [X]       │  ← 60px
│  32px  Timestamp: 2 hours ago      32px     │
└─────────────────────────────────────────────┘
```

### Mobile Layout (72px height)

```
┌──────────────────────────────────────────────┐
│ [Icon]  Message text here...           [X]  │  ← 72px min
│  40px   Timestamp: 2 hours ago         48px │
│         Full message visible                │
└──────────────────────────────────────────────┘
```

### Mobile Swipe Gesture

```
Swipe Left:
┌──────────────────────────────────────────────┐
│      [Message sliding left...]   [TRASH]    │
└──────────────────────────────────────────────┘
              Red background revealed

Swipe Right (cancel):
┌──────────────────────────────────────────────┐
│ [Icon]  Message returns to position...  [X] │
└──────────────────────────────────────────────┘
```

---

## 🎨 Design Requirements

### 1. Touch Target Sizing

**Minimum Sizes:**
- Item height: **72px on mobile** (60px desktop)
- Dismiss button: **48x48px on mobile** (32px desktop)
- Icon container: **40x40px on mobile** (32px desktop)
- Horizontal padding: **16px on mobile** (12px desktop)

**Text Sizing:**
- Message text: **16px font** (15px desktop)
- Timestamp: **14px font** (13px desktop)
- Icon size: **24px** (20px desktop)

### 2. Visual States

**Normal State:**
- Background: `var(--bg-secondary)`
- Border-radius: `var(--border-radius-md)`
- Border-left: 3px colored by type

**:hover (Desktop Only):**
- Background: `var(--bg-hover)` (subtle highlight)
- Cursor: Pointer
- Dismiss button more visible

**:active (Mobile Touch):**
- Background: `var(--bg-tertiary)` (darker)
- Instant feedback (0ms transition)
- Scale: 0.98 (subtle press effect)

**Swiping (Mobile):**
- Item follows finger with 0.5x resistance
- Red background revealed behind (danger color)
- Trash icon fades in as swipe progresses

### 3. Type-Specific Styling

**Success (Green):**
- Border-left: `3px solid var(--success-color)`
- Icon: Checkmark (✓)
- Icon background: `rgba(var(--success-rgb), 0.1)`

**Error (Red):**
- Border-left: `3px solid var(--danger-color)`
- Icon: X mark (✕)
- Icon background: `rgba(var(--danger-rgb), 0.1)`

**Warning (Orange):**
- Border-left: `3px solid var(--warning-color)`
- Icon: Warning triangle (⚠)
- Icon background: `rgba(var(--warning-rgb), 0.1)`

**Info (Blue):**
- Border-left: `3px solid var(--info-color)`
- Icon: Info circle (ℹ)
- Icon background: `rgba(var(--info-rgb), 0.1)`

### 4. Swipe Gesture Implementation

**Thresholds:**
- Minimum swipe distance: 80px
- Fast swipe velocity: 300px/s (instant dismiss)
- Cancel threshold: Swipe back 40px

**Animations:**
- Swipe follow: Instant (0ms) - follows finger
- Return animation: 300ms ease-out (if cancelled)
- Delete animation: 300ms ease-in (fade + slide)

---

## 📋 Implementation Scope

### Files to Modify

**Primary Component:**
- `app/frontend/src/components/NotificationPanel.vue` (or similar)
- `app/frontend/src/components/NotificationItem.vue` (if separate)

**What Needs Changing:**
1. **SCSS Responsive Styles** - Touch target sizing for mobile
2. **Item Markup** - Ensure icon, text, dismiss button layout
3. **Swipe Gesture Logic** - Touch event handlers (touchstart/touchmove/touchend)
4. **Dismiss Animation** - Fade-out and slide-away transition
5. **Type Indicators** - Border color and icon mapping

**Optional Enhancement:**
- Consider using Vue Swipe library for gesture handling
- Or implement native touch events with resistance logic

---

## ✅ Acceptance Criteria

### Touch Targets (Mobile < 768px)
- [ ] Notification items: 72px height minimum
- [ ] Dismiss buttons: 48x48px on mobile
- [ ] Icon containers: 40x40px on mobile
- [ ] Horizontal padding: 16px on mobile
- [ ] All elements easily tappable with thumb

### Text & Readability
- [ ] Message text: 16px font on mobile
- [ ] Timestamps: 14px font, no truncation
- [ ] Icons: 24px size on mobile
- [ ] High contrast text (readable in all conditions)
- [ ] Multi-line messages auto-expand height

### Visual Feedback
- [ ] :active state darkens background on tap
- [ ] Type indicators: 3px colored left border
- [ ] Icon backgrounds: 10% opacity of type color
- [ ] Smooth transitions (300ms ease)

### Swipe-to-Dismiss (Mobile Only)
- [ ] Swipe left/right 80px → Reveal delete action
- [ ] Fast swipe (300px/s) → Instant dismiss
- [ ] Red background with trash icon revealed
- [ ] Cancel swipe → Item returns smoothly
- [ ] Delete animation: Fade + slide (300ms)

### Desktop (≥ 768px)
- [ ] Layout unchanged (60px items)
- [ ] Hover states work correctly
- [ ] No swipe gestures (desktop-only dismiss button)

### Testing Checklist
- [ ] iPhone SE (375px) - Items readable
- [ ] iPhone 14 Pro (393px) - Swipe gestures smooth
- [ ] iPad (768px) → Desktop layout
- [ ] Tap dismiss button → Notification removed
- [ ] Swipe left → Trash icon appears
- [ ] Swipe right → Same behavior
- [ ] Fast swipe → Instant delete
- [ ] Cancel swipe → Item returns
- [ ] Multiple notifications → No overlap or flicker

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Touch targets (72px), type colors, swipe patterns
- `.github/instructions/frontend.instructions.md` - SCSS mixins, touch events

**Touch Gesture Libraries:**
- [Vue Use - useSwipe](https://vueuse.org/core/useSwipe/) - Lightweight swipe detection
- [Hammer.js](https://hammerjs.github.io/) - Advanced gesture library
- Native implementation: touchstart, touchmove, touchend events

**Related Issues:**
- Issue #12: Chapters Panel Mobile (similar list with touch targets)
- Issue #9: Video Player Controls (same touch target standards)
- Issue #11: Streamer Cards Spacing (similar card layout)

**Swipe Pattern Example:**
- iOS Mail app - Swipe to delete/archive email
- iOS Notifications - Swipe to dismiss notification
- Material Design - Swipe actions in lists

---

## 🎯 Solution

### Mobile-First Notification Design

**Desktop:**
- Compact list items
- Hover states
- Small icons

**Mobile:**
- Larger list items (64px+ height)
- Touch-friendly clear buttons
- Swipe-to-dismiss gestures
- Larger icons and text

---

## 📋 Implementation Tasks

### 1. Notification Item Layout (45 minutes)

```vue
<template>
  <div class="notification-item" :class="[`type-${notification.type}`]">
    <div class="notification-icon">
      <i :class="getIcon(notification.type)"></i>
    </div>
    
    <div class="notification-content">
      <p class="notification-message">{{ notification.message }}</p>
      <span class="notification-time">{{ formatTime(notification.timestamp) }}</span>
    </div>
    
    <button 
      class="notification-dismiss"
      @click.stop="$emit('dismiss', notification.id)"
      aria-label="Dismiss notification"
    >
      <i class="icon-close"></i>
    </button>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.notification-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: var(--border-radius-md);
  margin-bottom: 8px;
  
  // Desktop: Compact
  min-height: 60px;
  
  @include m.respond-below('md') {
    // Mobile: Larger, easier to tap
    min-height: 72px;
    padding: 16px;
    gap: 16px;
  }
  
  &.type-success {
    border-left: 3px solid var(--success-color);
  }
  
  &.type-error {
    border-left: 3px solid var(--danger-color);
  }
  
  &.type-warning {
    border-left: 3px solid var(--warning-color);
  }
  
  &.type-info {
    border-left: 3px solid var(--info-color);
  }
}
</style>
```

---

### 2. Icon & Typography Sizing (30 minutes)

```scss
.notification-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  flex-shrink: 0;
  
  i {
    font-size: 18px;
  }
  
  @include m.respond-below('md') {
    width: 40px;
    height: 40px;
    
    i {
      font-size: 22px;
    }
  }
}

.type-success .notification-icon {
  background: rgba(var(--success-rgb), 0.1);
  color: var(--success-color);
}

.type-error .notification-icon {
  background: rgba(var(--danger-rgb), 0.1);
  color: var(--danger-color);
}

.notification-content {
  flex: 1;
  min-width: 0; // Allow text truncation
  
  .notification-message {
    font-size: 14px;
    color: var(--text-primary);
    margin-bottom: 4px;
    line-height: 1.4;
    
    @include m.respond-below('md') {
      font-size: 16px;
    }
  }
  
  .notification-time {
    font-size: 12px;
    color: var(--text-tertiary);
    
    @include m.respond-below('md') {
      font-size: 13px;
    }
  }
}

.notification-dismiss {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: var(--bg-tertiary);
  border-radius: 50%;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
  
  i {
    font-size: 14px;
    color: var(--text-secondary);
  }
  
  &:hover {
    background: var(--bg-hover);
  }
  
  @include m.respond-below('md') {
    width: 44px;
    height: 44px;
    
    i {
      font-size: 18px;
    }
    
    &:active {
      background: var(--bg-hover);
    }
  }
}
```

---

### 3. Clear All Button (15 minutes)

```vue
<template>
  <div class="notifications-panel">
    <div class="panel-header">
      <h3>Notifications</h3>
      <button 
        class="btn btn-secondary btn-sm clear-all-btn"
        @click="$emit('clear-all')"
        :disabled="notifications.length === 0"
      >
        Clear All
      </button>
    </div>
    
    <div class="notifications-list">
      <!-- Notification items -->
    </div>
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
  
  h3 {
    font-size: 18px;
    font-weight: 600;
  }
  
  @include m.respond-below('md') {
    padding: 16px 20px;
    
    h3 {
      font-size: 20px;
    }
    
    .clear-all-btn {
      min-height: 40px;
      padding: 8px 16px;
      font-size: 14px;
    }
  }
}
```

---

### 4. Swipe-to-Dismiss Gesture (Optional - 30 minutes)

```vue
<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  notification: Notification
}>()

const emit = defineEmits<{
  dismiss: [id: number]
}>()

const startX = ref(0)
const currentX = ref(0)
const isDragging = ref(false)

const handleTouchStart = (e: TouchEvent) => {
  startX.value = e.touches[0].clientX
  isDragging.value = true
}

const handleTouchMove = (e: TouchEvent) => {
  if (!isDragging.value) return
  
  currentX.value = e.touches[0].clientX - startX.value
  
  // Only allow left swipe (negative values)
  if (currentX.value > 0) {
    currentX.value = 0
  }
}

const handleTouchEnd = () => {
  if (Math.abs(currentX.value) > 100) {
    // Swipe threshold reached - dismiss
    emit('dismiss', props.notification.id)
  }
  
  // Reset
  isDragging.value = false
  currentX.value = 0
}
</script>

<template>
  <div 
    class="notification-item"
    :style="{ transform: `translateX(${currentX}px)` }"
    @touchstart="handleTouchStart"
    @touchmove="handleTouchMove"
    @touchend="handleTouchEnd"
  >
    <!-- Notification content -->
    
    <!-- Swipe reveal button -->
    <div class="swipe-action" v-if="currentX < -50">
      <i class="icon-trash"></i>
      Dismiss
    </div>
  </div>
</template>

<style scoped lang="scss">
.notification-item {
  position: relative;
  transition: transform 0.2s ease;
  
  &:active {
    transition: none; // Disable during drag
  }
}

.swipe-action {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 100px;
  background: var(--danger-color);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  border-radius: 0 var(--border-radius-md) var(--border-radius-md) 0;
}
</style>
```

---

### 5. Empty State (10 minutes)

```vue
<template>
  <div class="notifications-list">
    <div v-if="notifications.length === 0" class="notifications-empty">
      <i class="icon-bell-off"></i>
      <p>No notifications</p>
    </div>
    
    <NotificationItem
      v-else
      v-for="notification in notifications"
      :key="notification.id"
      :notification="notification"
      @dismiss="handleDismiss"
    />
  </div>
</template>

<style scoped lang="scss">
.notifications-empty {
  padding: 60px 20px;
  text-align: center;
  color: var(--text-tertiary);
  
  i {
    font-size: 64px;
    margin-bottom: 16px;
    opacity: 0.3;
  }
  
  p {
    font-size: 16px;
  }
}
</style>
```

---

## 📂 Files to Modify

- `app/frontend/src/components/notifications/NotificationPanel.vue`
- `app/frontend/src/components/notifications/NotificationItem.vue`

---

## ✅ Acceptance Criteria

**Layout:**
- [ ] Notification items 72px height on mobile (60px desktop)
- [ ] Icon 40px on mobile (32px desktop)
- [ ] Dismiss button 44px on mobile (32px desktop)
- [ ] Proper spacing between items

**Typography:**
- [ ] Message 16px on mobile (14px desktop)
- [ ] Timestamp 13px on mobile (12px desktop)
- [ ] All text readable without zoom
- [ ] Text wraps properly

**Interaction:**
- [ ] Tap dismiss button → Notification removed
- [ ] Tap "Clear All" → All notifications removed
- [ ] Swipe left → Dismiss (optional)
- [ ] Visual feedback on tap

**Visual:**
- [ ] Type-based border colors (success, error, warning, info)
- [ ] Icons color-coded by type
- [ ] Empty state when no notifications
- [ ] Smooth animations

---

## 🧪 Testing Checklist

**Device Testing:**
- [ ] iPhone SE (375px)
- [ ] iPhone 12 (390px)
- [ ] Android (360px, 412px)
- [ ] iPad (768px)
- [ ] Desktop (1024px+)

**Interaction Testing:**
- [ ] Tap dismiss on single notification
- [ ] Tap "Clear All" button
- [ ] Swipe left to dismiss (if implemented)
- [ ] Multiple notifications scroll smoothly

**Visual Testing:**
- [ ] Success notification (green border)
- [ ] Error notification (red border)
- [ ] Warning notification (yellow border)
- [ ] Empty state displays correctly

**Edge Cases:**
- [ ] Very long message → Wraps properly
- [ ] 50+ notifications → Scroll performance OK
- [ ] Dismiss last notification → Empty state shows
- [ ] Rapid dismissals → No race conditions

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md`  
**Design:** `docs/DESIGN_SYSTEM.md` (Alert patterns)  
**Related:** `docs/REMAINING_FRONTEND_TASKS.md`

---

## 🤖 Copilot Instructions

**Context:**
Make notifications panel mobile-friendly with larger items, better typography, and touch-friendly dismiss buttons. Optional swipe-to-dismiss gesture for native mobile feel.

**Critical Patterns:**

1. **Touch-friendly sizing:**
   ```scss
   @include m.respond-below('md') {
     .notification-item { min-height: 72px; }
     .notification-dismiss { width: 44px; height: 44px; }
   }
   ```

2. **Type-based styling:**
   ```scss
   &.type-success { border-left: 3px solid var(--success-color); }
   ```

3. **Swipe gesture (optional):**
   ```typescript
   if (Math.abs(currentX.value) > 100) {
     emit('dismiss', notification.id)
   }
   ```

**Implementation Order:**
1. Update notification item layout and sizing
2. Improve icon and typography sizing
3. Enhance clear all button
4. Add swipe-to-dismiss (optional)
5. Add empty state

**Testing Strategy:**
1. Test on Safari iOS (touch events)
2. Verify dismiss button tap accuracy
3. Test swipe gesture on real device
4. Check with 1, 10, and 50+ notifications
5. Verify empty state

**Files to Read First:**
- `app/frontend/src/components/notifications/NotificationPanel.vue`
- `docs/DESIGN_SYSTEM.md` (alert/badge patterns)

**Success Criteria:**
Items 72px on mobile, dismiss button 44px, text 16px, swipe-to-dismiss works, empty state shown, type colors correct.

**Common Pitfalls:**
- ❌ Dismiss button too small
- ❌ Swipe gesture interfering with scroll
- ❌ Not testing on Safari iOS
- ❌ Missing empty state
- ❌ Icons not color-coded by type
