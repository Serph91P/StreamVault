# Streamer Cards Mobile Spacing & Touch Targets

## 🟢 Priority: MEDIUM
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 1-2 hours  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** MEDIUM - Visual polish and usability

---

## 📝 Problem Description

### Current State: Cards Too Cramped on Mobile

**Issues on Mobile (< 768px):**
- ❌ **Cards too cramped** - Insufficient padding inside cards
- ❌ **Touch targets overlap** - Delete button near card edge, easy misclick
- ❌ **Grid gap too small** - Cards appear to touch each other (< 12px gap)
- ❌ **Text truncation aggressive** - Titles cut off too early
- ❌ **Action buttons too small** - 36px buttons hard to tap accurately

**User Impact:**
- Accidental clicks on wrong streamer
- Delete button too close to card → Accidental deletes
- Cluttered, unprofessional appearance
- Difficult to read streamer names
- Frustrating to tap small action buttons

**Desktop Layout (Works Well):**
- 3-column grid with 20px gap
- 16px card padding
- 36px action buttons (fine for mouse)
- Plenty of space around elements

**Mobile Layout (Current Problems):**
- Same 3-column layout scaled down → Cards tiny
- Same 20px gap → Excessive on small screens
- Same button sizes → Too small for touch
- Text truncation unchanged → Cuts off sooner on narrow cards

---

## 🎯 Requirements

### Grid Layout Responsive Behavior

**Desktop (≥ 992px):**
- 3 columns (auto-fill with 300px minimum)
- 20px gap between cards
- Cards expand to fill available space

**Tablet (768px - 991px):**
- 2 columns (auto-fill with 250px minimum)
- 16px gap between cards
- Balanced layout for medium screens

**Mobile (< 768px):**
- 2 columns on larger phones (> 375px width)
- 1 column on small phones (≤ 375px width)
- 12px gap between cards (more compact on mobile)
- Full-width cards on single-column layout

### Card Spacing Requirements

**Internal Card Padding:**
- Keep 16px on all screen sizes (standard card padding)

**Element Spacing (Inside Cards):**
- Card header margin-bottom: 12px (more breathing room)
- Card body margin-bottom: 12px
- Card footer margin-top: 16px with 1px top border

**Touch Target Sizes:**
- Action buttons: **48x48px minimum** on mobile
- Delete button: **Separate from card edge** (8px minimum margin)
- Status badges: **32px height minimum** (readable, tappable)

---

## 🎨 Design Requirements

### 1. Responsive Grid Columns

**Breakpoints:**
- **Large (≥ 992px):** 3 columns, 20px gap
- **Medium (768-991px):** 2 columns, 16px gap
- **Small (376-767px):** 2 columns, 12px gap
- **Extra Small (≤ 375px):** 1 column, 12px gap

**Grid Behavior:**
- Use `auto-fill` with `minmax()` for flexible columns
- Graceful degradation (3 → 2 → 1 columns)
- Gap reduces as screen size decreases

### 2. Touch-Friendly Actions

**Button Sizing on Mobile:**
- Primary actions (Watch, Force Record): 48x48px
- Secondary actions (Edit, Delete): 48x48px
- Icon size scales up (20px → 24px on mobile)

**Button Spacing:**
- 8px gap between buttons
- 8px margin from card edges
- Prevent overlap with card content

**Delete Button Safety:**
- Positioned with safe margin from card edge
- Prominent warning color (red)
- Confirmation dialog before deletion

### 3. Text Readability

**Title Truncation:**
- Desktop: 2 lines (ellipsis after 2nd line)
- Mobile: 2 lines (but wider cards → more text visible)
- Tooltip shows full title on hover/long-press

**Streamer Name:**
- Always visible (no truncation)
- Bold font weight for emphasis
- Adequate font size (16px minimum)

---

## 📋 Implementation Scope

### Files to Modify

**Primary Component:**
- `app/frontend/src/components/StreamerCard.vue` (likely location)
- OR `app/frontend/src/views/StreamersView.vue` (grid container)

**What Needs Changing:**
1. **SCSS Grid Layout** - Responsive columns with breakpoints
2. **Card Internal Spacing** - Margin/padding adjustments
3. **Action Button Sizing** - Mobile touch target overrides
4. **Text Truncation** - Line-clamp with tooltip

**Design System Integration:**
- Use `@include m.respond-below('md')` for mobile breakpoints
- Use `@include m.respond-below('lg')` for tablet breakpoints
- Use existing CSS variables for spacing (`--spacing-*`)

---

## ✅ Acceptance Criteria

### Grid Layout
- [ ] Desktop: 3 columns with 20px gap
- [ ] Tablet: 2 columns with 16px gap
- [ ] Mobile (> 375px): 2 columns with 12px gap
- [ ] Mobile (≤ 375px): 1 column with 12px gap
- [ ] Grid adapts smoothly on window resize

### Card Spacing
- [ ] Card padding: 16px on all screen sizes
- [ ] Internal element spacing: 12px vertical margins
- [ ] Footer separator: 16px top margin + 1px border
- [ ] No elements overlap or appear cramped

### Touch Targets (Mobile < 768px)
- [ ] All action buttons: 48x48px minimum
- [ ] Delete button: 8px margin from card edge
- [ ] Status badges: 32px height minimum
- [ ] Icons: 24px size (up from 20px)
- [ ] Button gap: 8px spacing

### Text & Readability
- [ ] Titles: 2-line truncation with ellipsis
- [ ] Streamer names: No truncation, bold
- [ ] Tooltip shows full title on long-press (mobile)
- [ ] Font sizes readable on small screens

### Visual Polish
- [ ] Cards don't appear to touch each other
- [ ] Balanced white space around elements
- [ ] Professional appearance on all screen sizes
- [ ] Consistent with app design system

### Testing Checklist
- [ ] iPhone SE (375px width) - 1 column layout
- [ ] iPhone 14 Pro (393px width) - 2 column layout
- [ ] iPad (768px width) - 2 column layout
- [ ] Desktop (1280px width) - 3 column layout
- [ ] Resize browser → Columns adjust correctly
- [ ] Tap action buttons → No accidental misclicks
- [ ] Tap near delete button → Doesn't trigger accidentally
- [ ] Long titles → Tooltip appears on long-press

---

## 📖 References

**Design System:**
- `docs/DESIGN_SYSTEM.md` - Grid patterns, touch targets, spacing scale
- `.github/instructions/frontend.instructions.md` - SCSS breakpoints, responsive mixins

**CSS Grid Patterns:**
```scss
// Example from design system (DO NOT COPY CODE)
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(XYZpx, 1fr));
  gap: var(--spacing-*);
}
```

**Breakpoint Mixins:**
```scss
// Available breakpoints (reference only)
@include m.respond-below('md')  // < 768px (mobile)
@include m.respond-below('lg')  // < 992px (tablet)
```

**Related Issues:**
- Issue #4: Settings Tables Mobile (similar touch target fixes)
- Issue #9: Video Player Controls (same touch target standards)
- Issue #14: Add Streamer Modal (input field spacing)

---

## 🎯 Solution

### Optimal Mobile Card Spacing

**Desktop:**
- Grid: 3 columns, 20px gap
- Card padding: 16px
- Touch targets: 36px

**Mobile:**
- Grid: 1-2 columns, 16px gap
- Card padding: 16px
- Touch targets: 48px
- Larger text

---

## 📋 Implementation Tasks

### 1. Grid Layout Optimization (30 minutes)

```scss
@use '@/styles/mixins' as m;

.streamers-grid {
  display: grid;
  gap: 20px;
  
  // Desktop: 3 columns
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  
  @include m.respond-below('lg') {
    // Tablet: 2 columns
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 16px;
  }
  
  @include m.respond-below('md') {
    // Mobile: 1 column on very small screens, 2 on larger phones
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
    
    // Extra small phones: Force 1 column
    @media (max-width: 375px) {
      grid-template-columns: 1fr;
    }
  }
}
```

---

### 2. Card Padding & Spacing (20 minutes)

```scss
.streamer-card {
  padding: 16px;
  border-radius: var(--border-radius-lg);
  background: var(--bg-secondary);
  
  @include m.respond-below('md') {
    // Mobile: Same padding but adjust internal spacing
    padding: 16px;
    
    .card-header {
      margin-bottom: 12px; // More breathing room
    }
    
    .card-body {
      margin-bottom: 12px;
    }
    
    .card-footer {
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid var(--border-color);
    }
  }
}
```

---

### 3. Touch Target Optimization (30 minutes)

```scss
.streamer-card {
  .action-buttons {
    display: flex;
    gap: 8px;
    
    .btn {
      // Desktop: 36px
      min-height: 36px;
      padding: 8px 12px;
      
      @include m.respond-below('md') {
        // Mobile: 48px (Apple HIG minimum 44px)
        min-height: 48px;
        padding: 12px 16px;
        font-size: 16px; // Prevent iOS zoom
        
        // Full width on small screens
        @media (max-width: 375px) {
          flex: 1;
        }
      }
    }
  }
  
  .delete-btn {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 32px;
    height: 32px;
    
    @include m.respond-below('md') {
      // Larger and more spaced on mobile
      width: 40px;
      height: 40px;
      top: 12px;
      right: 12px;
      
      // Larger touch area with padding trick
      padding: 8px;
      margin: -8px;
    }
  }
}
```

---

### 4. Text Sizing & Truncation (20 minutes)

```scss
.streamer-card {
  .streamer-name {
    font-size: 18px;
    font-weight: 600;
    
    @include m.respond-below('md') {
      font-size: 20px; // Larger on mobile
      margin-bottom: 8px;
    }
  }
  
  .stream-title {
    font-size: 14px;
    line-height: 1.4;
    
    // Truncate to 2 lines
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    
    @include m.respond-below('md') {
      font-size: 15px; // Slightly larger
      -webkit-line-clamp: 3; // Allow 3 lines on mobile
    }
  }
  
  .category-name {
    font-size: 13px;
    color: var(--text-secondary);
    
    @include m.respond-below('md') {
      font-size: 14px;
    }
  }
}
```

---

### 5. Status Badge Spacing (10 minutes)

```scss
.status-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
  
  @include m.respond-below('md') {
    // Larger and more prominent
    padding: 6px 12px;
    font-size: 12px;
    top: 16px;
    left: 16px;
  }
  
  &.live {
    background: rgba(255, 0, 0, 0.1);
    color: #ff0000;
    border: 1px solid rgba(255, 0, 0, 0.3);
  }
}
```

---

## 📂 Files to Modify

- `app/frontend/src/components/StreamerCard.vue`
- `app/frontend/src/views/HomeView.vue` (grid layout)
- `app/frontend/src/styles/_utilities.scss` (if shared card styles)

---

## ✅ Acceptance Criteria

**Grid Layout:**
- [ ] 3 columns on desktop (≥1024px)
- [ ] 2 columns on tablet (768-1023px)
- [ ] 2 columns on large phones (≥414px)
- [ ] 1 column on small phones (<375px)
- [ ] Consistent gap between cards

**Card Spacing:**
- [ ] 16px padding on all screen sizes
- [ ] 12-16px internal spacing between elements
- [ ] Footer clearly separated with border

**Touch Targets:**
- [ ] All buttons 48px height on mobile
- [ ] Delete button 40px × 40px with extra touch area
- [ ] No accidental clicks on adjacent elements
- [ ] Buttons full-width on very small screens

**Typography:**
- [ ] Streamer name 20px on mobile
- [ ] Title truncates to 3 lines on mobile
- [ ] All text 14px+ (readable without zoom)
- [ ] No text overlap or clipping

**Visual Quality:**
- [ ] Cards don't look cramped
- [ ] Proper breathing room around content
- [ ] Status badge prominent but not blocking
- [ ] Consistent with Design System

---

## 🧪 Testing Checklist

**Device Testing:**
- [ ] iPhone SE (375px) - 1 column
- [ ] iPhone 12 (390px) - 2 columns
- [ ] iPhone 12 Pro Max (428px) - 2 columns
- [ ] Android small (360px) - 1-2 columns
- [ ] Android large (412px) - 2 columns
- [ ] iPad portrait (768px) - 2-3 columns
- [ ] Desktop (1024px+) - 3+ columns

**Interaction Testing:**
- [ ] Tap card → Opens correctly
- [ ] Tap delete button → Only delete triggered
- [ ] Tap action button → Correct action
- [ ] No accidental adjacent card clicks
- [ ] Scrolling smooth with proper spacing

**Visual Testing:**
- [ ] Cards don't touch each other
- [ ] Text readable without zoom
- [ ] Buttons clearly tappable
- [ ] Status badge visible
- [ ] Consistent appearance across devices

**Edge Cases:**
- [ ] Very long streamer name → Truncates
- [ ] Very long stream title → 3 lines max
- [ ] No stream title → Card still looks good
- [ ] Many cards (50+) → Grid performance OK

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md`  
**Design:** `docs/DESIGN_SYSTEM.md` (Card patterns)  
**Reference:** `.github/instructions/frontend.instructions.md`

---

## 🤖 Copilot Instructions

**Context:**
Improve streamer card spacing and touch targets for mobile devices. Current cards are cramped with too-small buttons and insufficient spacing, causing accidental clicks and poor readability.

**Critical Patterns:**

1. **Responsive grid:**
   ```scss
   grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
   @media (max-width: 375px) { grid-template-columns: 1fr; }
   ```

2. **Touch targets:**
   ```scss
   @include m.respond-below('md') {
     .btn { min-height: 48px; }
   }
   ```

3. **Text truncation:**
   ```scss
   display: -webkit-box;
   -webkit-line-clamp: 3;
   -webkit-box-orient: vertical;
   ```

4. **Touch area expansion:**
   ```scss
   padding: 8px;
   margin: -8px; // Invisible touch area
   ```

**Implementation Order:**
1. Update grid layout breakpoints
2. Adjust card internal spacing
3. Increase button sizes on mobile
4. Improve text sizing and truncation
5. Test on multiple device sizes

**Testing Strategy:**
1. Visual comparison: Before/After on iPhone SE
2. Test all breakpoints (375px, 390px, 414px, 768px)
3. Verify no accidental clicks
4. Check text readability
5. Performance test with 50+ cards

**Files to Read First:**
- `app/frontend/src/components/StreamerCard.vue` (current styling)
- `docs/DESIGN_SYSTEM.md` (card patterns and spacing)
- `.github/instructions/frontend.instructions.md` (mobile guidelines)

**Success Criteria:**
Cards properly spaced on all devices, touch targets 48px+, text readable, no accidental clicks, consistent with Design System.

**Common Pitfalls:**
- ❌ Not testing on iPhone SE (smallest common device)
- ❌ Touch targets < 44px
- ❌ Forgetting to expand touch area on small icons
- ❌ Text truncation cutting off mid-word
- ❌ Cards touching each other on mobile
