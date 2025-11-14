---
applyTo: "app/frontend/**/*.vue,app/frontend/**/*.ts,app/frontend/**/*.scss"
---

# Frontend Development Guidelines

## API Communication (CRITICAL)

### Session Authentication - credentials:'include' (MANDATORY)

**CRITICAL RULE**: ALL fetch() calls MUST include `credentials: 'include'` to send session cookies!

**Why this is critical:**
- Session cookies are NOT sent by default in fetch() requests
- Without `credentials: 'include'`, backend returns 401 Unauthorized
- Results in empty data, TypeErrors on array operations, blank pages

**Pattern for ALL API calls:**

```typescript
// ✅ CORRECT: GET requests
const response = await fetch('/api/streamers', {
  credentials: 'include'  // CRITICAL!
})

// ✅ CORRECT: POST/PUT/DELETE requests
const response = await fetch('/api/settings', {
  method: 'POST',
  credentials: 'include',  // CRITICAL!
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
})

// ✅ CORRECT: Auth endpoints
const response = await fetch('/auth/login', {
  method: 'POST',
  credentials: 'include',  // CRITICAL!
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
})
```

**❌ NEVER forget credentials:**
```typescript
// ❌ WRONG: No credentials = 401 errors
await fetch('/api/streamers')  // Session cookie not sent!

// ❌ WRONG: Composables fail without credentials
const { streamers } = useStreamers()  // Will be empty if fetch missing credentials
```

**Checklist for new composables/API calls:**
- [ ] Added `credentials: 'include'` to ALL fetch() calls
- [ ] Tested after login that data loads
- [ ] Tested page refresh - session persists
- [ ] No 401 errors in dev console
- [ ] No TypeErrors on .filter()/.sort()

**Affected Patterns:**
- All composables: `use*.ts` files making API calls
- Auth flows: LoginView, Router guards
- Settings panels: Notification, Recording, PWA
- Data fetching: Streamers, Streams, Categories

**Related Commits:**
- c37d167f - Initial auth guard fixes
- 06bc13b1 - All composable fetch() calls fixed
- 66b90ced - Login redirect delay fix

## SCSS & Styling Philosophy (CRITICAL - Read First!)

### ⚠️ GOLDEN RULE: Global SCSS First, Component Styles Last

**MANDATORY PRINCIPLE**: Reuse global SCSS patterns. Only write component-specific styles when absolutely necessary.

**Decision Tree for ANY styling task:**

```
Need to add/change a style?
│
├─ Is it used in 3+ components? → Use global SCSS
├─ Is it a base HTML element (input, button, a)? → Add to main.scss
├─ Is it a design token (color, spacing, border-radius)? → Use _variables.scss
├─ Is it a reusable pattern? → Add to _utilities.scss or _mixins.scss
└─ Is it truly component-specific? → Only then use <style scoped>
```

**Why This Matters:**
- ✅ **Consistency** - All components look identical
- ✅ **Speed** - Copy-paste from DESIGN_SYSTEM.md instead of writing CSS
- ✅ **Maintainability** - Change in 1 file, applies everywhere
- ✅ **Theme Support** - CSS variables enable automatic dark/light mode

**Global SCSS Files:**
- `app/frontend/src/styles/main.scss` - Base HTML elements (input, button, a, body, html)
- `app/frontend/src/styles/_variables.scss` - Design tokens (colors, spacing, typography, breakpoints)
- `app/frontend/src/styles/_mixins.scss` - Reusable patterns (breakpoints, flex-center, truncate-text)
- `app/frontend/src/styles/_utilities.scss` - Utility classes (.text-center, .mt-4, .flex, .grid, .badge, .btn)

**❌ ANTI-PATTERN - Component-Specific Duplication:**
```vue
<!-- BAD: LoginView.vue -->
<style scoped>
input { font-size: 16px; } /* iOS zoom prevention */
.button { min-height: 44px; } /* Touch target */
</style>

<!-- BAD: SetupView.vue -->
<style scoped>
input { font-size: 16px; } /* Same fix duplicated! */
.button { min-height: 44px; } /* Same fix duplicated! */
</style>

<!-- Result: 20+ files with duplicate CSS! -->
```

**✅ CORRECT PATTERN - Global SCSS:**
```scss
// GOOD: app/frontend/src/styles/main.scss
@use 'mixins' as m;

input, select, textarea {
  @include m.respond-below('md') {  // < 768px (mobile)
    font-size: 16px !important;  // iOS zoom prevention - applies everywhere
  }
}

button, .btn {
  @include m.respond-below('md') {  // < 768px (mobile)
    min-height: 44px;  // Touch-friendly - applies everywhere
  }
}

// Result: Fixed in ALL components automatically!
```

**Pre-Commit Checklist:**
- [ ] Checked `docs/DESIGN_SYSTEM.md` for existing patterns
- [ ] Used global utility classes from `_utilities.scss` where possible
- [ ] Used design tokens from `_variables.scss` (no hard-coded colors/spacing)
- [ ] Used SCSS breakpoint mixins (no hard-coded `@media (max-width: XXXpx)`)
- [ ] Only wrote custom CSS if pattern truly unique to this component

**See:** "Global SCSS Changes" section below for complete migration guide.

---

## Component Architecture

- Use Vue 3 Composition API with `<script setup lang="ts">`
- Prefer composables over mixins for reusable logic
- Keep components focused - one responsibility per component
- **NO MAGIC NUMBERS**: Extract delays, thresholds, timeouts to named constants
- **USE VUE LIFECYCLE**: Use `nextTick()` instead of `setTimeout()` for deferred operations
- **REUSE GLOBAL STYLES**: Check `_utilities.scss` before writing component-specific CSS

### Constants Management (MANDATORY)

**ALWAYS** use `app/frontend/src/config/constants.ts` for magic numbers, delays, and thresholds.

#### Available Constant Groups:

```typescript
import { IMAGE_LOADING, API, UI } from '@/config/constants'

// Image loading configuration
IMAGE_LOADING.VISIBLE_CATEGORIES_PRELOAD_COUNT  // 20 - Preload count for initial render

// API configuration
API.DEFAULT_TIMEOUT  // 30000ms - Default API timeout

// UI configuration
UI.SEARCH_DEBOUNCE_MS   // 300ms - Search input debounce
UI.TOAST_DURATION_MS    // 3000ms - Notification duration
```

#### When to Use Constants:

❌ **Bad - Magic Numbers:**
```typescript
const preloadCount = 20  // Why 20?
setTimeout(() => {}, 300)  // What does 300 mean?
if (elapsed > 3000) {}  // Why 3000?
```

✅ **Good - Named Constants:**
```typescript
import { IMAGE_LOADING, UI } from '@/config/constants'

const preloadCount = IMAGE_LOADING.VISIBLE_CATEGORIES_PRELOAD_COUNT
setTimeout(() => {}, UI.SEARCH_DEBOUNCE_MS)
if (elapsed > UI.TOAST_DURATION_MS) {}
```

#### Adding New Constants:

When you find a magic number in component code:
1. **Check** if a similar constant exists in `constants.ts`
2. **Add** to appropriate group (IMAGE_LOADING, API, UI) if new
3. **Document** purpose with JSDoc comment
4. **Use** `as const` for type safety

**Categories:**
- `IMAGE_LOADING` - Image preload counts, lazy load thresholds
- `API` - API timeouts, retry delays, polling intervals
- `UI` - Debounce delays, animation durations, toast timings

## Design System (Mobile-First PWA)

### 🎨 Design Language - Glassmorphism UI

**StreamVault uses a modern glassmorphism design language** established in the Complete Design Overhaul (November 2025).

**Core Design Principles:**
1. **Glassmorphism Effects** - Translucent cards with backdrop blur
2. **Smooth Animations** - 200-300ms transitions, fade-in/slide-up effects
3. **Visual Hierarchy** - Clear information density, consistent spacing
4. **Mobile-First** - Touch-friendly (44x44px targets), responsive layouts
5. **Loading States** - Skeleton loaders for all content types
6. **Empty States** - Descriptive messages with call-to-action buttons

**Reference:** See `docs/COMPLETE_DESIGN_OVERHAUL_SUMMARY.md` for complete redesign documentation.

---

### 🪟 GlassCard Component (PRIMARY CONTAINER)

**ALWAYS use `<GlassCard>` for content containers** - don't create custom card styles!

```vue
<template>
  <!-- Basic GlassCard -->
  <GlassCard>
    <h2>Content Title</h2>
    <p>Your content here</p>
  </GlassCard>
  
  <!-- With hover effect -->
  <GlassCard hover>
    <p>This card lifts on hover</p>
  </GlassCard>
  
  <!-- Custom padding -->
  <GlassCard padding="sm">  <!-- sm, md (default), lg, xl -->
    <p>Small padding</p>
  </GlassCard>
</template>

<script setup lang="ts">
import GlassCard from '@/components/cards/GlassCard.vue'
</script>
```

**GlassCard Features:**
- ✅ Backdrop blur effect (`backdrop-filter: blur(16px)`)
- ✅ Translucent background (`rgba(31, 31, 35, 0.7)`)
- ✅ Smooth border glow
- ✅ Optional hover lift effect
- ✅ Customizable padding (sm/md/lg/xl)
- ✅ Theme-aware colors
- ✅ Optimized performance

**When to Use:**
- Main content sections (Settings panels, forms, tables)
- Feature cards (Welcome steps, empty states)
- Modal dialogs and overlays
- Any container that needs visual separation

**DON'T create custom card styles** - use `<GlassCard>` for consistency!

---

### 📦 Specialized Card Components

#### StreamerCard
```vue
<StreamerCard
  :streamer="streamer"
  @click="navigateToStreamer"
  @force-record="handleForceRecord"
  @delete="handleDelete"
/>
```
**Used in:** HomeView (Live Now), StreamersView

#### VideoCard
```vue
<VideoCard
  :video="video"
  :show-streamer="true"
  @click="playVideo"
  @delete="handleDelete"
/>
```
**Used in:** HomeView (Recent Recordings), StreamerDetailView, VideosView

#### StatusCard
```vue
<StatusCard
  title="Total VODs"
  :value="42"
  icon="icon-video"
  color="primary"
/>
```
**Used in:** HomeView (Quick Stats), StreamerDetailView (Stats)

---

### 🎭 Animation Patterns

**All components use consistent animation timing:**

```scss
// Transitions
transition: all 0.2s ease;  // Fast interactions (hover, focus)
transition: all 0.3s ease;  // Medium animations (expand, collapse)

// Entrance animations
.fade-in {
  animation: fadeIn 0.3s ease-out;
}

.slide-up {
  animation: slideUp 0.4s ease-out;
}

// Staggered lists
.stagger-item {
  animation: fadeIn 0.3s ease-out;
  animation-fill-mode: both;
  
  &:nth-child(1) { animation-delay: 0.05s; }
  &:nth-child(2) { animation-delay: 0.1s; }
  &:nth-child(3) { animation-delay: 0.15s; }
}
```

**Available Animations:**
- `fadeIn` - Fade opacity 0 → 1
- `slideUp` - Slide from bottom with fade
- `shimmer` - Loading skeleton effect
- `shake` - Error animation (forms)
- `ripple` - Button press effect (v-ripple directive)

**Apply to views:**
```vue
<template>
  <div class="view fade-in">
    <div class="content slide-up">
      <!-- Animated entrance -->
    </div>
  </div>
</template>
```

---

### 🎨 Loading States

**ALWAYS use `<LoadingSkeleton>` for loading states** - matches content layout!

```vue
<template>
  <!-- Loading video cards -->
  <LoadingSkeleton v-if="loading" type="video-card" :count="6" />
  <VideoCard v-else v-for="video in videos" :video="video" />
  
  <!-- Loading text -->
  <LoadingSkeleton v-if="loading" type="text" :lines="3" />
  
  <!-- Loading table -->
  <LoadingSkeleton v-if="loading" type="table" :rows="5" />
  
  <!-- Loading card -->
  <LoadingSkeleton v-if="loading" type="card" />
</template>

<script setup lang="ts">
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
</script>
```

**Available Types:**
- `video-card` - Thumbnail + title + metadata
- `streamer-card` - Avatar + name + status
- `text` - Text lines with shimmer
- `table` - Table rows skeleton
- `card` - Generic card shape
- `avatar` - Circular avatar
- `button` - Button shape

**Shimmer Effect:** Automatically applied to all skeleton types (subtle wave animation).

---

### 🏜️ Empty States

**ALWAYS use `<EmptyState>` for empty data** - consistent messaging!

```vue
<template>
  <!-- No videos -->
  <EmptyState
    v-if="videos.length === 0"
    icon="icon-video-off"
    title="No Recordings Yet"
    description="Start recording streams to see them here"
    action-text="Add Streamer"
    @action="navigateToAddStreamer"
  />
  
  <!-- Search no results -->
  <EmptyState
    v-if="filteredVideos.length === 0"
    icon="icon-search"
    title="No Results Found"
    description="Try adjusting your filters or search terms"
  />
</template>

<script setup lang="ts">
import EmptyState from '@/components/EmptyState.vue'
</script>
```

**Props:**
- `icon` - FontAwesome icon class
- `title` - Main message (bold, larger)
- `description` - Supporting text
- `action-text` - Optional button text
- `@action` - Button click handler

**Used in:** HomeView, StreamersView, VideosView, StreamerDetailView, SubscriptionsView

---

### Available Global Utility Classes

**CRITICAL**: Before writing ANY component-specific CSS, check if a global utility class exists!

**Reference:** See `docs/DESIGN_SYSTEM.md` for complete copy-paste examples (800+ lines).

#### Layout & Spacing
```vue
<!-- Flexbox utilities -->
<div class="flex items-center justify-between gap-4">
<div class="flex-col items-start">

<!-- Grid utilities -->
<div class="grid grid-cols-2 gap-4">
<div class="grid grid-cols-3 gap-6">

<!-- Spacing utilities -->
<div class="mt-4 mb-6 px-4 py-2">
<div class="m-0 p-0">
```

#### Typography
```vue
<!-- Text sizing -->
<p class="text-xs">Extra small text</p>
<p class="text-sm">Small text</p>
<p class="text-base">Base text</p>
<p class="text-lg">Large text</p>

<!-- Text alignment -->
<p class="text-center">Centered</p>
<p class="text-right">Right aligned</p>

<!-- Font weight -->
<span class="font-medium">Medium weight</span>
<span class="font-bold">Bold weight</span>
```

#### Badges & Status
```vue
<!-- Status badges -->
<span class="badge badge-success">Live</span>
<span class="badge badge-danger">Error</span>
<span class="badge badge-warning">Warning</span>
<span class="badge badge-info">Info</span>

<!-- Status borders (left accent) -->
<div class="card status-border status-border-success">
<div class="alert status-border status-border-warning">
```

#### Buttons
```vue
<!-- Button variants - NEVER create custom button styles! -->
<button class="btn btn-primary">Primary Action</button>
<button class="btn btn-secondary">Secondary</button>
<button class="btn btn-success">Confirm</button>
<button class="btn btn-danger">Delete</button>
<button class="btn btn-ghost">Ghost</button>
<button class="btn btn-icon">⚙️</button>

<!-- Button sizes -->
<button class="btn btn-sm">Small</button>
<button class="btn btn-lg">Large</button>

<!-- Loading state -->
<button class="btn btn-primary" disabled>
  <span class="spinner"></span> Loading...
</button>
```

#### Cards & Containers
```vue
<!-- Card variants -->
<div class="card">Basic card</div>
<div class="card card-elevated">With shadow</div>
<div class="glass-card">Glassmorphism effect</div>

<!-- Sections -->
<section class="section">Content section</section>
<div class="container">Centered container</div>
```

#### Alerts & Messages
```vue
<!-- Alert types -->
<div class="alert alert-success">Success message</div>
<div class="alert alert-danger">Error message</div>
<div class="alert alert-warning">Warning message</div>
<div class="alert alert-info">Info message</div>
```

#### Skeletons & Loading States
```vue
<!-- Loading skeletons -->
<div class="skeleton"></div>
<div class="skeleton-text"></div>
<div class="skeleton-card"></div>
<div class="skeleton-avatar"></div>
```

#### Modals
```vue
<!-- Modal structure -->
<div class="modal-overlay" @click.self="close">
  <div class="modal-card">
    <div class="modal-header">
      <h2>Title</h2>
      <button class="btn btn-icon" @click="close">×</button>
    </div>
    <div class="modal-body">Content</div>
    <div class="modal-footer">
      <button class="btn btn-secondary">Cancel</button>
      <button class="btn btn-primary">Confirm</button>
    </div>
  </div>
</div>
```

#### Forms
```vue
<!-- Form elements -->
<div class="form-group">
  <label class="form-label">Username</label>
  <input type="text" class="form-input" />
  <p class="form-help">Helper text</p>
  <p class="form-error">Error message</p>
</div>

<!-- Input groups -->
<div class="input-group">
  <span class="input-group-text">@</span>
  <input type="text" class="form-input" />
</div>
```

**When to Use Global vs Component Styles:**
- **Badge?** → Use `.badge .badge-success` (NEVER custom)
- **Button?** → Use `.btn .btn-primary` (NEVER custom)
- **Card?** → Use `.card` or `.glass-card` (NEVER custom)
- **Alert?** → Use `.alert .alert-danger` (NEVER custom)
- **Form?** → Use `.form-group .form-input` (NEVER custom)
- **Truly unique layout?** → Only then use component `<style scoped>`

### Button Styling
**ALWAYS use global `.btn` classes** - never create custom button styles:
- `.btn-primary` - Primary actions
- `.btn-success` - Positive actions  
- `.btn-danger` - Destructive actions
- `.btn-secondary` - Secondary actions

### Status Indicators & Left-Accent Borders

**ALWAYS use `.status-border-*` utility classes** for left-accent borders (3px solid):

#### Available Classes (from `_components.scss`)
- `.status-border-primary` - Blue accent (default/info)
- `.status-border-success` - Green accent (healthy/passed)
- `.status-border-warning` - Orange accent (warnings)
- `.status-border-danger` - Red accent (critical)
- `.status-border-error` - Red accent (errors/failed)
- `.status-border-info` - Blue accent (information)
- `.status-border-secondary` - Gray accent (neutral/unknown)

#### Usage Pattern
```vue
<!-- Static border -->
<div class="card status-border status-border-success">
  Content
</div>

<!-- Dynamic border with helper function -->
<div 
  class="item status-border"
  :class="getBorderClass(status)"
>
  Content
</div>

<script setup lang="ts">
const getBorderClass = (status: string) => {
  switch (status) {
    case 'healthy': return 'status-border-success'
    case 'warning': return 'status-border-warning'
    case 'error': return 'status-border-error'
    default: return 'status-border-secondary'
  }
}
</script>
```

#### Migration from Inline Styles
**NEVER use inline `border-left` styles** - migrate to utility classes:

❌ **Bad:**
```scss
.element {
  border-left: 3px solid #42b883;
}
```

✅ **Good:**
```vue
<div class="element status-border status-border-primary">

<style scoped>
.element {
  /* Border color handled by .status-border-* classes */
  padding: 1rem;
  background: var(--background-card);
}
</style>
```

### Responsive Grids
```scss
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  
  @media (min-width: 1024px) {
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  }
}
```

### Tables → Mobile Cards
All tables must transform to cards on mobile (`@media (max-width: 480px)`):
- Add `data-label` attributes to `<td>` elements
- Use `display: block` and repositioning for card layout

### Modals
- Use `position: fixed` (not absolute)
- Add `backdrop-filter: blur(4px)` for separation
- Include `@click.self="close"` on overlay for backdrop close
- Add smooth animations (fadeIn, slideUp)

## SCSS Variables & Design Tokens (MANDATORY)

### ⚠️ CRITICAL: NEVER Hard-Code Colors, Spacing, or Border-Radius!

**ALWAYS** use SCSS variables from `_variables.scss` or CSS custom properties.

**Why This Matters:**
- ✅ **Theme Support** - Automatic dark/light mode switching
- ✅ **Consistency** - Same colors/spacing everywhere
- ✅ **Maintainability** - Change primary color in 1 place, applies to 100+ files
- ✅ **Future-Proof** - Easy to add new themes or rebrand

### Decision Tree: Which Format to Use?

```
Need to use a color/spacing/border-radius?
│
├─ Need runtime access (Vue template, computed)? → Use CSS custom properties: var(--primary-color)
├─ Using in SCSS file? → Use SCSS variables: v.$primary-color (with @use 'variables' as v;)
└─ Building calculations? → Use SCSS variables with math: v.$spacing-4 * 2
```

### Color Variables
```scss
// SCSS variables (use in .scss files)
@use 'variables' as v;

$primary-color: #42b883;
$danger-color: #ff4757;
$success-color: #2ed573;
$warning-color: #ffa502;
$info-color: #70a1ff;
$secondary-color: #6d6d6d;

$background-dark: #121214;
$background-darker: #18181b;
$background-card: #1f1f23;
$text-primary: #f1f1f3;
$text-secondary: #b1b1b9;
$border-color: #2d2d35;

// CSS custom properties (use in .vue files)
var(--primary-color)
var(--danger-color)
var(--success-color)
var(--warning-color)
var(--info-color)
var(--background-card)
var(--text-primary)
var(--text-secondary)
var(--border-color)
```

### Border-Radius Variables
```scss
$border-radius-sm: 4px;   // Small elements (badges, pills)
$border-radius: 8px;      // DEFAULT - most components
$border-radius-lg: 12px;  // Cards, modals
$border-radius-xl: 16px;  // Large containers
$border-radius-pill: 9999px; // Fully rounded
```

### Spacing Variables
```scss
$spacing-xs: 0.25rem;  // 4px
$spacing-sm: 0.5rem;   // 8px
$spacing-md: 1rem;     // 16px - DEFAULT
$spacing-lg: 1.5rem;   // 24px
$spacing-xl: 2rem;     // 32px
$spacing-xxl: 3rem;    // 48px
```

### Usage Pattern

**Rule of Thumb:** If you're typing a hex color (#xxx) or pixel value (XXpx) → STOP and find the design token!

❌ **ANTI-PATTERN - Hard-coded values everywhere:**
```vue
<!-- Component 1: LoginView.vue -->
<style scoped>
.card {
  background: #1f1f23;     /* Hardcoded! */
  color: #f1f1f3;          /* Hardcoded! */
  padding: 16px;           /* Hardcoded! */
  border-radius: 8px;      /* Hardcoded! */
  border: 1px solid #2d2d35; /* Hardcoded! */
}
</style>

<!-- Component 2: SetupView.vue -->
<style scoped>
.card {
  background: #1f1f23;     /* Duplicate! */
  color: #f1f1f3;          /* Duplicate! */
  padding: 16px;           /* Duplicate! */
  border-radius: 8px;      /* Duplicate! */
  border: 1px solid #2d2d35; /* Duplicate! */
}
</style>

<!-- 😫 Result: Same values duplicated in 50+ files! -->
<!-- To change card background, must edit 50+ files! -->
```

✅ **CORRECT PATTERN - Use global utility class:**
```vue
<!-- Component 1: LoginView.vue -->
<template>
  <div class="card">
    <!-- ✅ Reuses global .card class from _utilities.scss -->
  </div>
</template>

<!-- NO <style> block needed! -->

<!-- Component 2: SetupView.vue -->
<template>
  <div class="card">
    <!-- ✅ Same global class, consistent styling -->
  </div>
</template>

<!-- 🎉 Result: 0 lines of duplicate CSS! -->
<!-- To change card background, edit _utilities.scss once! -->
```

✅ **CORRECT PATTERN - When custom styles needed:**
```vue
<!-- If you truly need component-specific styles: -->
<template>
  <div class="custom-component">
    <!-- Unique layout that doesn't exist in design system -->
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.custom-component {
  // ✅ Use design tokens, NOT hard-coded values
  background: v.$background-card;     // NOT #1f1f23
  color: v.$text-primary;             // NOT #f1f1f3
  padding: v.$spacing-md;             // NOT 16px
  border-radius: v.$border-radius;    // NOT 8px
  border: 1px solid v.$border-color;  // NOT #2d2d35
  
  // ✅ Use mixins for breakpoints
  @include m.respond-below('md') {
    padding: v.$spacing-sm;           // NOT 8px
  }
}
</style>
```

✅ **ALSO CORRECT - CSS custom properties (runtime values):**
```vue
<style scoped>
.card {
  /* ✅ Use CSS variables for theme support */
  background: var(--background-card);
  color: var(--text-primary);
  padding: var(--spacing-md, 1rem);          /* Fallback value */
  border-radius: var(--border-radius, 8px);  /* Fallback value */
}
</style>
```

**When to use each format:**
- **Global utility class** (`.card`, `.badge`, `.btn`) → Use for 99% of cases
- **SCSS variables** (`v.$spacing-md`) → When building custom layouts with calculations
- **CSS custom properties** (`var(--spacing-md)`) → When needing runtime theme switching

### Common Mappings

When refactoring hard-coded values to design tokens:

**Colors:**
- `#42b883`, `#2ed573`, `#22c55e`, `#28a745` → `v.$success-color` or `var(--success-color)`
- `#ff4757`, `#ef4444`, `#dc2626`, `#dc3545` → `v.$danger-color` or `var(--danger-color)`
- `#ffa502`, `#f59e0b`, `#eab308`, `#ffc107` → `v.$warning-color` or `var(--warning-color)`
- `#70a1ff`, `#3b82f6`, `#2563eb`, `#3498db` → `v.$info-color` or `v.$primary-color`
- `#1f1f23`, `#18181b` → `v.$background-card` or `v.$background-darker`
- `#ffffff`, `#f1f1f3` → `v.$text-primary`
- `#aaa`, `#b1b1b9`, `#ccc`, `#6b7280` → `v.$text-secondary`

**Border-Radius:**
- `2px`, `3px`, `4px` → `$border-radius-sm` (4px)
- `5px`, `6px`, `8px` → `$border-radius` (8px) - **DEFAULT**
- `10px`, `12px` → `$border-radius-lg` (12px)
- `15px`, `16px`, `20px` → `$border-radius-xl` (16px)
- `25px`, `9999px`, `50%` → `$border-radius-pill` (9999px)

**Spacing (for padding/margin):**
- `4px` → `$spacing-xs` (0.25rem)
- `8px` → `$spacing-sm` (0.5rem)
- `12px`, `16px` → `$spacing-md` (1rem) - **DEFAULT**
- `20px`, `24px` → `$spacing-lg` (1.5rem)

## SCSS Breakpoints & Responsive Design (CRITICAL)

### ⚠️ MANDATORY: Use SCSS Mixins for ALL Breakpoints

**CRITICAL RULE**: NEVER use hard-coded `@media (max-width: XXXpx)` queries in Vue components!

**❌ FORBIDDEN - Hard-coded breakpoints:**
```scss
// ❌ WRONG: Hard-coded magic numbers
@media (max-width: 640px) {
  .component { padding: 8px; }
}

@media (max-width: 768px) {
  .header { flex-direction: column; }
}

@media (max-width: 480px) {
  .button { width: 100%; }
}
```

**✅ REQUIRED - SCSS Mixins:**
```scss
// ✅ CORRECT: Use mixins from _mixins.scss
@use '@/styles/mixins' as m;

@include m.respond-below('sm') {  // < 640px
  .component { padding: 8px; }
}

@include m.respond-below('md') {  // < 768px
  .header { flex-direction: column; }
}

@include m.respond-below('xs') {  // < 375px
  .button { width: 100%; }
}
```

### Centralized Breakpoint System

**Breakpoints** are defined in `app/frontend/src/styles/_variables.scss`:

```scss
$breakpoints: (
  'xs': 375px,   // Mobile extra-small (iPhone SE)
  'sm': 640px,   // Mobile / Phablet (most phones in landscape)
  'md': 768px,   // Tablet portrait
  'lg': 1024px,  // Desktop / Tablet landscape
  'xl': 1200px   // Large desktop
);
```

**Mixins** are provided in `app/frontend/src/styles/_mixins.scss`:

```scss
// Minimum width (mobile-first approach)
@mixin respond-to($breakpoint) {
  @media (min-width: map.get(v.$breakpoints, $breakpoint)) {
    @content;
  }
}

// Maximum width (desktop-first approach)
@mixin respond-below($breakpoint) {
  $breakpoint-value: map.get(v.$breakpoints, $breakpoint);
  @media (max-width: #{$breakpoint-value - 1px}) {
    @content;
  }
}
```

### Migration Guide: Hard-Coded → SCSS Mixins

**Step 1: Add mixin import to your component**

```vue
<style scoped lang="scss">
// Add this at the top of your <style> block
@use '@/styles/mixins' as m;

.your-component {
  // your styles
}
</style>
```

**Step 2: Replace hard-coded breakpoints**

| Hard-coded | SCSS Mixin Replacement | Reason |
|------------|------------------------|--------|
| `@media (max-width: 374px)` | `@include m.respond-below('xs')` | < 375px |
| `@media (max-width: 375px)` | `@include m.respond-below('xs')` | < 375px |
| `@media (max-width: 480px)` | `@include m.respond-below('xs')` | Map to xs (closest) |
| `@media (max-width: 639px)` | `@include m.respond-below('sm')` | < 640px |
| `@media (max-width: 640px)` | `@include m.respond-below('sm')` | < 640px |
| `@media (max-width: 767px)` | `@include m.respond-below('md')` | < 768px |
| `@media (max-width: 768px)` | `@include m.respond-below('md')` | < 768px |
| `@media (max-width: 1023px)` | `@include m.respond-below('lg')` | < 1024px |
| `@media (max-width: 1024px)` | `@include m.respond-below('lg')` | < 1024px |

**Step 3: Add explanatory comments**

```scss
// ✅ GOOD: Explain what breakpoint means
@include m.respond-below('md') {  // < 768px - Tablet and below
  .component {
    flex-direction: column;
  }
}

// ❌ BAD: No context
@include m.respond-below('md') {
  .component {
    flex-direction: column;
  }
}
```

### Common Responsive Patterns

**Pattern 1: Mobile-First (Recommended)**

```scss
.component {
  // Base styles for mobile
  padding: var(--spacing-2);
  font-size: var(--text-sm);
}

@include m.respond-to('sm') {  // >= 640px
  .component {
    padding: var(--spacing-3);
  }
}

@include m.respond-to('md') {  // >= 768px
  .component {
    padding: var(--spacing-4);
    font-size: var(--text-base);
  }
}

@include m.respond-to('lg') {  // >= 1024px
  .component {
    padding: var(--spacing-6);
    font-size: var(--text-lg);
  }
}
```

**Pattern 2: Desktop-First (When Needed)**

```scss
.component {
  // Base styles for desktop
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-6);
}

@include m.respond-below('lg') {  // < 1024px
  .component {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--spacing-4);
  }
}

@include m.respond-below('sm') {  // < 640px
  .component {
    grid-template-columns: 1fr;
    gap: var(--spacing-3);
  }
}
```

**Pattern 3: Progressive Enhancement (Touch Targets)**

```scss
.button {
  min-height: 36px;  // Base height
  padding: var(--spacing-2) var(--spacing-4);
}

@include m.respond-below('md') {  // < 768px - Touch devices
  .button {
    min-height: 44px;  // Touch-friendly (Apple HIG)
    padding: var(--spacing-3) var(--spacing-4);
  }
}

@include m.respond-below('sm') {  // < 640px - Small phones
  .button {
    width: 100%;  // Full-width on mobile
    min-height: 48px;  // Extra touch area
  }
}
```

### Why This Matters (Benefits)

1. **Single Source of Truth**: Changing `640px → 720px` only requires editing `_variables.scss`
2. **Maintainability**: No scattered magic numbers across 50+ Vue files
3. **Consistency**: All components break at the same viewport widths
4. **Semantic Names**: `'sm'` is more readable than `640px`
5. **Type Safety**: SCSS will error on unknown breakpoints like `'medium'`

### Pre-Commit Checklist

Before committing any Vue component:

- [ ] No `@media (max-width: XXXpx)` in component styles
- [ ] All breakpoints use `@include m.respond-below('breakpoint')`
- [ ] Mixin import `@use '@/styles/mixins' as m;` is present
- [ ] Breakpoint comments explain viewport size (e.g., `// < 768px`)
- [ ] Touch targets >= 44px on mobile breakpoints

### Related Documentation

- Breakpoint definitions: `app/frontend/src/styles/_variables.scss`
- Mixin implementations: `app/frontend/src/styles/_mixins.scss`
- Refactoring commit: See commit "refactor: migrate all hard-coded breakpoints to SCSS mixins"

---

## Global SCSS Changes (CRITICAL - Read This First!)

### ⚠️ NEVER Make Per-Page/Per-Component Style Changes

**CRITICAL PRINCIPLE**: When fixing styling issues (font sizes, input styles, spacing, etc.), ALWAYS work in the global SCSS files, NOT in individual Vue components!

**Why This Matters:**
- Changes in global SCSS apply to ALL components automatically
- Prevents inconsistencies across pages
- Reduces code duplication (DRY principle)
- Makes maintenance easier (change once, apply everywhere)
- Ensures design system consistency

### Common Scenarios & Correct Approach

#### ❌ WRONG: Fix font-size in each component

```scss
// LoginView.vue - ❌ BAD
input {
  font-size: 16px;  // iOS zoom prevention
}

// SetupView.vue - ❌ BAD
input {
  font-size: 16px;  // iOS zoom prevention (duplicate!)
}

// AddStreamerView.vue - ❌ BAD
input {
  font-size: 16px;  // iOS zoom prevention (duplicate again!)
}
```

**Problem**: Same fix repeated 10+ times across different files. If we need to change it later, we have to update 10+ files!

#### ✅ CORRECT: Fix once in global SCSS

```scss
// app/frontend/src/styles/main.scss - ✅ GOOD
input, select, textarea {
  font-size: 16px;  // iOS zoom prevention - applies globally
  
  @include m.respond-to('md') {  // >= 768px (desktop)
    font-size: var(--text-base);  // Use design system on desktop
  }
}
```

**Result**: Fixed everywhere automatically! All inputs in LoginView, SetupView, AddStreamerView, Settings, etc. get the correct font-size.

### Global SCSS Files & Their Purpose

| File | Purpose | When to Use |
|------|---------|-------------|
| `app/frontend/src/styles/main.scss` | **Global base styles** | Base HTML elements (input, button, a, h1-h6), body, html, resets |
| `app/frontend/src/styles/_variables.scss` | **Design tokens** | Colors, spacing, typography, breakpoints, shadows, borders |
| `app/frontend/src/styles/_mixins.scss` | **Reusable patterns** | Breakpoint mixins, common styles (flex-center, truncate-text) |
| `app/frontend/src/styles/_utilities.scss` | **Utility classes** | .text-center, .mt-4, .flex, .grid, status borders |

### Decision Tree: Where to Make Changes?

```
┌─────────────────────────────────────────┐
│ Need to change a style?                 │
└───────────────┬─────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Affects HTML  │
        │ base element? │
        │ (input, button)│
        └───┬───────────┘
            │
    ┌───────┴───────┐
    │ YES           │ NO
    ▼               ▼
┌────────────┐  ┌──────────────┐
│ main.scss  │  │ Used in 3+   │
│            │  │ components?  │
└────────────┘  └───┬──────────┘
                    │
            ┌───────┴───────┐
            │ YES           │ NO
            ▼               ▼
    ┌──────────────┐  ┌────────────────┐
    │ _utilities.   │  │ Component      │
    │ scss or       │  │ <style scoped> │
    │ _mixins.scss  │  │                │
    └──────────────┘  └────────────────┘
```

### Examples by Category

#### 1. iOS Zoom Prevention (Input Font Size)

**❌ WRONG Approach:**
- Add `font-size: 16px` to every component with inputs
- LoginView.vue, SetupView.vue, AddStreamerView.vue, SettingsView.vue...
- Result: 20+ files modified, same code duplicated

**✅ CORRECT Approach:**
```scss
// app/frontend/src/styles/main.scss
input, select, textarea {
  @include m.respond-below('md') {  // < 768px (mobile/tablet)
    font-size: 16px !important;  // Prevent iOS zoom
  }
}
```

#### 2. Touch Targets (Button Minimum Height)

**❌ WRONG Approach:**
- Add `min-height: 44px` to buttons in each view
- Modify HomeView, StreamersView, VideosView, SettingsView...

**✅ CORRECT Approach:**
```scss
// app/frontend/src/styles/main.scss
button, .btn, a.btn {
  @include m.respond-below('md') {  // < 768px
    min-height: 44px;  // Touch-friendly
    padding: var(--spacing-3) var(--spacing-4);
  }
}
```

#### 3. Consistent Spacing

**❌ WRONG Approach:**
- Replace hard-coded `padding: 12px` in 50+ components individually

**✅ CORRECT Approach:**
```scss
// First, verify the pattern exists in design system
// app/frontend/src/styles/_variables.scss
$spacing-3: 0.75rem;  // 12px

// Then use it everywhere:
.card {
  padding: var(--spacing-3);  // Not 12px!
}
```

#### 4. Theme Colors (Light Mode Buttons)

**❌ WRONG Approach:**
- Fix button colors in NotificationSettingsPanel.vue
- Then fix in RecordingSettingsPanel.vue
- Then fix in PWAPanel.vue...

**✅ CORRECT Approach:**
```scss
// app/frontend/src/styles/_utilities.scss or main.scss
.btn-primary {
  background: var(--primary-color);
  color: white;
  
  &:hover {
    background: var(--primary-600);
  }
  
  // Light mode override
  [data-theme="light"] & {
    background: var(--primary-600);
    border: 1px solid var(--primary-700);
  }
}
```

### Audit Process for Global Changes

When you identify a pattern that needs fixing across multiple components:

**Step 1: Identify the Pattern**
```bash
# Example: Find all hard-coded font-sizes
rg "font-size:\s*\d+px" app/frontend/src --type scss
```

**Step 2: Count Occurrences**
```bash
# How many files need updating?
rg "font-size:\s*\d+px" app/frontend/src --type scss --files-with-matches | wc -l
```

**Step 3: Decide Scope**
- **1-2 files**: Component-scoped change is okay
- **3-5 files**: Consider creating a mixin or utility class
- **6+ files**: MUST use global SCSS or design token

---

## View-Specific Patterns (From Complete Redesign)

### 🏠 Main View Structure

**All main views follow this consistent pattern:**

```vue
<template>
  <div class="view-name fade-in">
    <!-- Header section -->
    <div class="view-header">
      <div class="header-content">
        <h1 class="view-title">Page Title</h1>
        <p class="view-subtitle">Brief description</p>
      </div>
      
      <!-- Action buttons (right side) -->
      <div class="header-actions">
        <button class="btn btn-primary">Primary Action</button>
        <button class="btn btn-secondary">Secondary</button>
      </div>
    </div>
    
    <!-- Content section(s) -->
    <GlassCard>
      <!-- Loading state -->
      <LoadingSkeleton v-if="loading" type="card" />
      
      <!-- Empty state -->
      <EmptyState
        v-else-if="items.length === 0"
        icon="icon-inbox"
        title="No Items Yet"
        description="Get started by adding your first item"
        action-text="Add Item"
        @action="handleAdd"
      />
      
      <!-- Content -->
      <div v-else class="content-grid">
        <ItemCard
          v-for="item in items"
          :key="item.id"
          :item="item"
        />
      </div>
    </GlassCard>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import GlassCard from '@/components/cards/GlassCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'

const loading = ref(true)
const items = ref([])

onMounted(async () => {
  // Load data
  await fetchItems()
  loading.value = false
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.view-name {
  padding: v.$spacing-6;
  
  @include m.respond-below('md') {
    padding: v.$spacing-4;
  }
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: v.$spacing-6;
  
  @include m.respond-below('md') {
    flex-direction: column;
    gap: v.$spacing-4;
  }
}

.view-title {
  font-size: v.$text-3xl;
  font-weight: v.$font-bold;
  margin-bottom: v.$spacing-2;
}

.view-subtitle {
  color: v.$text-secondary;
  font-size: v.$text-base;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: v.$spacing-4;
  
  @include m.respond-below('sm') {
    grid-template-columns: 1fr;
  }
}
</style>
```

**Used in:** HomeView, StreamersView, VideosView, StreamerDetailView, SubscriptionsView

---

### 🔄 Filter & Sort Patterns

**Standard filter/sort UI pattern:**

```vue
<template>
  <GlassCard padding="sm">
    <div class="filters-bar">
      <!-- Search input -->
      <div class="search-box">
        <i class="icon-search"></i>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search..."
          class="search-input"
        />
      </div>
      
      <!-- Filter dropdown -->
      <select v-model="filterType" class="filter-select">
        <option value="all">All Items</option>
        <option value="active">Active Only</option>
        <option value="archived">Archived</option>
      </select>
      
      <!-- Sort dropdown -->
      <select v-model="sortBy" class="sort-select">
        <option value="date-desc">Newest First</option>
        <option value="date-asc">Oldest First</option>
        <option value="name-asc">Name A-Z</option>
      </select>
      
      <!-- View toggle -->
      <div class="view-toggle">
        <button
          class="btn btn-icon"
          :class="{ active: viewMode === 'grid' }"
          @click="viewMode = 'grid'"
        >
          <i class="icon-grid"></i>
        </button>
        <button
          class="btn btn-icon"
          :class="{ active: viewMode === 'list' }"
          @click="viewMode = 'list'"
        >
          <i class="icon-list"></i>
        </button>
      </div>
    </div>
  </GlassCard>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.filters-bar {
  display: flex;
  gap: v.$spacing-3;
  align-items: center;
  
  @include m.respond-below('md') {
    flex-wrap: wrap;
  }
}

.search-box {
  flex: 1;
  position: relative;
  min-width: 200px;
  
  i {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: v.$text-secondary;
  }
}

.search-input {
  width: 100%;
  padding-left: 40px;
}

.view-toggle {
  display: flex;
  gap: v.$spacing-2;
  
  .btn.active {
    background: v.$primary-color;
    color: white;
  }
}
</style>
```

**Used in:** VideosView, StreamersView, StreamerDetailView

---

### 📊 Stats Display Pattern

**Use StatusCard for metrics:**

```vue
<template>
  <div class="stats-grid">
    <StatusCard
      title="Total VODs"
      :value="stats.totalVods"
      icon="icon-video"
      color="primary"
    />
    
    <StatusCard
      title="Total Duration"
      :value="formatDuration(stats.totalDuration)"
      icon="icon-clock"
      color="success"
    />
    
    <StatusCard
      title="Total Size"
      :value="formatSize(stats.totalSize)"
      icon="icon-database"
      color="info"
    />
  </div>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: v.$spacing-4;
  margin-bottom: v.$spacing-6;
  
  @include m.respond-below('sm') {
    grid-template-columns: 1fr;
  }
}
</style>
```

**Used in:** HomeView, StreamerDetailView

---

### 📝 Form Patterns

**Consistent form structure with validation:**

```vue
<template>
  <GlassCard>
    <form @submit.prevent="handleSubmit">
      <div class="form-group">
        <label for="username" class="form-label">Username</label>
        <div class="input-with-icon">
          <i class="icon-user input-icon"></i>
          <input
            id="username"
            v-model="form.username"
            type="text"
            class="form-input"
            :class="{ 'is-valid': isValid, 'is-invalid': isInvalid }"
            placeholder="Enter username"
          />
          <div v-if="isValid" class="input-status">
            <i class="icon-check text-success"></i>
          </div>
        </div>
        <p v-if="errors.username" class="form-error">
          {{ errors.username }}
        </p>
        <p v-else class="form-help">
          Helper text for username field
        </p>
      </div>
      
      <div class="form-actions">
        <button type="button" class="btn btn-secondary" @click="handleCancel">
          Cancel
        </button>
        <button type="submit" class="btn btn-primary" :disabled="!isFormValid">
          Save Changes
        </button>
      </div>
    </form>
  </GlassCard>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.form-group {
  margin-bottom: v.$spacing-4;
}

.form-label {
  display: block;
  margin-bottom: v.$spacing-2;
  font-weight: v.$font-medium;
  color: v.$text-primary;
}

.input-with-icon {
  position: relative;
  
  .input-icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: v.$text-secondary;
  }
  
  .form-input {
    padding-left: 40px;
    
    &.is-valid {
      border-color: v.$success-color;
    }
    
    &.is-invalid {
      border-color: v.$danger-color;
    }
  }
  
  .input-status {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
  }
}

.form-actions {
  display: flex;
  gap: v.$spacing-3;
  justify-content: flex-end;
  margin-top: v.$spacing-6;
  
  @include m.respond-below('sm') {
    flex-direction: column-reverse;
    
    button {
      width: 100%;
    }
  }
}
</style>
```

**Used in:** SetupView, AddStreamerView, Settings panels

---

### 🎬 Modal Patterns

**Consistent modal structure:**

```vue
<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="isOpen" class="modal-overlay" @click.self="close">
        <div class="modal-card slide-up">
          <div class="modal-header">
            <h2>{{ title }}</h2>
            <button class="btn btn-icon" @click="close">
              <i class="icon-x"></i>
            </button>
          </div>
          
          <div class="modal-body">
            <slot></slot>
          </div>
          
          <div class="modal-footer">
            <button class="btn btn-secondary" @click="close">
              Cancel
            </button>
            <button class="btn btn-danger" @click="handleConfirm">
              Confirm
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: v.$spacing-4;
}

.modal-card {
  background: v.$background-card;
  border: 1px solid v.$border-color;
  border-radius: v.$border-radius-xl;
  max-width: 500px;
  width: 100%;
  max-height: 90vh;
  overflow: auto;
  box-shadow: v.$shadow-2xl;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: v.$spacing-4;
  border-bottom: 1px solid v.$border-color;
  
  h2 {
    font-size: v.$text-xl;
    font-weight: v.$font-bold;
  }
}

.modal-body {
  padding: v.$spacing-4;
}

.modal-footer {
  display: flex;
  gap: v.$spacing-3;
  justify-content: flex-end;
  padding: v.$spacing-4;
  border-top: 1px solid v.$border-color;
}

// Transition animations
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
  
  .modal-card {
    transition: transform 0.3s ease;
  }
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
  
  .modal-card {
    transform: translateY(20px) scale(0.95);
  }
}
</style>
```

**Used in:** Delete confirmations, settings modals, video details

---

**Step 3: Decide Scope**
- **1-2 files**: Component-scoped change is okay
- **3-5 files**: Consider creating a mixin or utility class
- **6+ files**: MUST use global SCSS or design token

**Step 4: Implement Globally**
1. Add/update in `main.scss`, `_variables.scss`, or `_utilities.scss`
2. Test in dev server (changes apply immediately)
3. Verify in multiple components
4. Remove old component-specific overrides

**Step 5: Document**
- Add comment in SCSS explaining why the style exists
- Reference iOS guidelines, accessibility standards, etc.

### Common Global Patterns

#### Input Styling (iOS Zoom + Theme)

```scss
// app/frontend/src/styles/main.scss
input:not([type="checkbox"]):not([type="radio"]),
select,
textarea {
  // Base styles
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  padding: var(--spacing-2) var(--spacing-3);
  transition: border-color 0.2s ease;
  
  // iOS zoom prevention on mobile
  @include m.respond-below('md') {
    font-size: 16px !important;
  }
  
  // Desktop: Use design system font
  @include m.respond-to('md') {
    font-size: var(--text-base);
  }
  
  &:focus {
    outline: none;
    border-color: var(--primary-color);
  }
  
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}
```

#### Button Styling (Touch Targets + Theme)

```scss
// app/frontend/src/styles/main.scss
button, .btn {
  // Base styles
  border-radius: var(--radius-lg);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all 0.2s ease;
  
  // Touch targets on mobile
  @include m.respond-below('md') {
    min-height: 44px;
    padding: var(--spacing-3) var(--spacing-4);
  }
  
  // Desktop
  @include m.respond-to('md') {
    min-height: 36px;
    padding: var(--spacing-2) var(--spacing-4);
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
```

### Pre-Commit Checklist for Global Changes

Before making style changes:

- [ ] Is this pattern used in 3+ components? → Use global SCSS
- [ ] Does it affect base HTML elements? → Add to `main.scss`
- [ ] Is it a design token (color/spacing)? → Check `_variables.scss` first
- [ ] Is it a responsive pattern? → Use SCSS breakpoint mixins
- [ ] Will it affect light AND dark themes? → Test both
- [ ] Is it accessibility-related? → Add explanatory comment

### Related Commits

Reference commits that demonstrate global SCSS changes:

- SCSS Breakpoint Migration: `12d23ab7` - Migrated 50+ files to use centralized mixins
- Animation Toggle: `da402917` - Global `.no-animations` class in `main.scss`
- Design System Consistency: `61f16b68` - Fixed hardcoded colors with CSS variables

### Key Takeaway

**Think globally, code once!** Before editing component styles, ask:
- "Will other components need this too?"
- "Is this a design pattern or a one-off?"
- "Can I solve this with a design token?"

If the answer is "yes" to any of these → Use global SCSS files!

---

## Touch Targets

All interactive elements must have `min-height: 44px` on mobile for accessibility.

## Breakpoints

- Mobile: 320px-640px (base styles)
- Tablet: 768px-1023px
- Desktop: 1024px+
- Large: 1440px+
- XL: 1920px+

## PWA & Service Worker Requirements

### Service Worker Registration
**CRITICAL**: Service worker files MUST be served at root level, not in subdirectories.

#### File Location Requirements
```
✅ CORRECT:
/sw.js               - Service worker itself
/registerSW.js       - Registration script
/manifest.json       - Web app manifest

❌ WRONG:
/pwa/sw.js          - Can only control /pwa/** (not whole app!)
/assets/sw.js       - Cannot control parent directories
```

**Why Root Level?**
- Service workers can only control their own directory and subdirectories
- `/pwa/sw.js` scope is limited to `/pwa/**`
- `/sw.js` scope includes the entire application
- Browser security model enforces this restriction

#### Backend Integration (FastAPI)
Service worker files must have dedicated endpoints:

```python
# ✅ CORRECT: Root-level endpoints
@app.get("/registerSW.js")
async def register_service_worker():
    return FileResponse(
        "app/frontend/dist/registerSW.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache", 
            "Expires": "0"
        }
    )

@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        "app/frontend/dist/sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"}  # Never cache SW!
    )

# ❌ WRONG: Only mounting under /pwa/
app.mount("/pwa", StaticFiles(directory="dist"))
# Browser requests /registerSW.js → 404!
```

#### Cache Headers for Service Workers
**NEVER cache service worker files** - they must always be fresh:

```
✅ CORRECT Cache Headers:
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0

❌ WRONG:
Cache-Control: public, max-age=31536000  # Will prevent updates!
```

**Why No Cache?**
- Service worker updates must be detected immediately
- Stale service workers can break the entire application
- Browser checks for updates on every page load
- If cached, users get stuck with old broken code

#### Testing Service Worker Registration

```bash
# Check if files are accessible at root
curl -I https://your-app.com/registerSW.js  # Should return 200
curl -I https://your-app.com/sw.js          # Should return 200

# Verify headers
curl -I https://your-app.com/sw.js | grep -i cache
# Should show: Cache-Control: no-cache
```

**Browser DevTools:**
1. Open Application tab → Service Workers
2. Should show service worker registered at `/sw.js`
3. Check Console for errors like "Failed to load /registerSW.js"
4. Network tab should show 200 responses for SW files

#### Common Issues & Solutions

**Issue: 404 on /registerSW.js**
```
❌ Problem: File only available at /pwa/registerSW.js
✅ Solution: Add root-level endpoint in FastAPI main.py
```

**Issue: Service worker not updating**
```
❌ Problem: Cached with max-age header
✅ Solution: Use no-cache headers for all SW files
```

**Issue: Service worker scope limited**
```
❌ Problem: Registered at /pwa/sw.js, can't control /api/
✅ Solution: Move service worker to root level
```

Use `@media (min-width: X)` for progressive enhancement.

## SCSS Build Errors & Debugging (CRITICAL)

### Sass Module System (@use vs @import)

**ALWAYS use `@use` with namespace** - never use bare `@import`:

```scss
// ✅ CORRECT - Modern Sass module system
@use 'variables' as v;
@use 'mixins' as m;

.component {
  padding: v.$spacing-md;        // Namespaced variable
  @include m.card-base;          // Namespaced mixin
}

// ❌ WRONG - Deprecated @import (will be removed in Sass 2.0)
@import 'variables';
@import 'mixins';

.component {
  padding: $spacing-md;          // Bare variable (pollutes global scope)
  @include card-base;            // Bare mixin
}
```

### Common Build Errors & Solutions

#### Error 1: "Undefined variable"

**Symptom:**
```
[sass] Undefined variable.
  6 │ .text-xs { font-size: $text-xs; }
    │                       ^^^^^^^^
```

**Root Cause:** Missing `@use` import or missing namespace prefix

**Solution:**
```scss
// 1. Add @use at top of file (MUST be first line before any code)
@use 'variables' as v;

// 2. Add namespace to all variable references
.text-xs { font-size: v.$text-xs; }        // Was: $text-xs
.card { padding: v.$spacing-4; }           // Was: $spacing-4
.rounded { border-radius: v.$border-radius-md; }  // Was: $border-radius
```

**Batch Fix with sed (for many references):**
```bash
# Fix hyphenated variables (spacing-, shadow-, duration-, etc.)
sed -i 's/\$spacing-/v.\$spacing-/g' file.scss
sed -i 's/\$shadow-/v.\$shadow-/g' file.scss
sed -i 's/\$border-radius-/v.\$border-radius-/g' file.scss

# Fix non-hyphenated variables (font-sans, font-mono)
sed -i 's/\$font-sans/v.\$font-sans/g' file.scss
sed -i 's/\$font-mono/v.\$font-mono/g' file.scss
```

#### Error 2: "Mixed Declarations" (Sass 2.0 Deprecation)

**Symptom:**
```
Deprecation Warning: Sass's behavior for declarations that appear after nested
rules will be changing to match the behavior specified by CSS.

More info: https://sass-lang.com/d/mixed-decls

    ╷
7   │ ┌     @media (min-width: ...) {
8   │ │       @content;
9   │ │     }
    │ └─── nested rule
... │
83  │     border: 1px solid var(--border-color);
    │     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ declaration
    ╵
```

**Root Cause:** Declarations (properties) appear AFTER nested rules (@media, &:hover, etc.)

**Bad Example:**
```scss
@mixin card-base {
  padding: 1rem;
  
  @media (min-width: 768px) {  // ← Nested rule
    padding: 2rem;
  }
  
  border: 1px solid gray;  // ⚠️ Declaration AFTER nested rule (deprecated)
}
```

**Solutions (3 options):**

**Option 1: Move declaration BEFORE nested rules (preferred for simple cases)**
```scss
@mixin card-base {
  padding: 1rem;
  border: 1px solid gray;  // ✅ Declaration BEFORE nested rule
  
  @media (min-width: 768px) {
    padding: 2rem;
  }
}
```

**Option 2: Wrap in `& {}` (preferred for mixins that extend other mixins)**
```scss
@mixin card-flat {
  @include card-base;  // This includes nested @media rules
  
  & {  // ✅ Explicit nested rule wrapper
    box-shadow: none;
    border: 1px solid var(--border-color);
  }
}
```

**Option 3: Wrap in `@at-root & {}` (for root-level declarations)**
```scss
.component {
  @include some-mixin;  // Has nested rules
  
  @at-root & {  // ✅ Forces root-level scope
    display: block;
  }
}
```

**When to use each:**
- **Move up** → Simple cases, few declarations
- **`& {}`** → Mixins extending other mixins, multiple declarations
- **`@at-root &`** → Need to escape deeply nested context

#### Error 3: Missing Variables in _variables.scss

**Symptom:**
```
[sass] Undefined variable.
  265 │ $transition-base: $duration-250 $ease-in-out;
      │                   ^^^^^^^^^^^^^
```

**Root Cause:** Variable used in definition doesn't exist

**Solution - Add missing variable:**
```scss
// Check variable list for gaps
$duration-200: 200ms;
$duration-250: 250ms;  // ← ADD if missing
$duration-300: 300ms;
$duration-400: 400ms;  // ← ADD if missing
$duration-500: 500ms;
```

**Pattern:** Keep variable scales complete (no gaps in 100/200/300 sequences)

#### Error 4: Duplicate Style Tags in Vue Components

**Symptom:**
```
[plugin vite:vue] Invalid end tag at ComponentName.vue:2339:1
```

**Root Cause:** Multiple `</style>` tags from incomplete edits

**Detection:**
```bash
grep -n "</style>" Component.vue
# Output: 1466:</style>
#         2339:</style>  ← Duplicate!
```

**Solution:**
```bash
# Delete orphaned CSS between first and second closing tag
sed -i '1466,2338d' Component.vue  # Deletes lines 1466-2338
```

**Prevention:** Always verify Vue SFC structure after large edits:
- One `<template>` block
- One `<script>` block
- One `<style>` block (scoped or not)

### SCSS Build Debugging Workflow

**Step-by-step error resolution:**

1. **Read error message carefully**
   - Note exact line number and file
   - Identify variable/property name
   - Check if it's Sass error vs Vue/Vite error

2. **Read file context** (3-5 lines before/after error)
   ```bash
   # Read specific line range
   sed -n '260,270p' _variables.scss
   ```

3. **Identify root cause**
   - Missing import? → Add `@use 'variables' as v;`
   - Missing namespace? → Add `v.$` prefix
   - Missing variable? → Add to _variables.scss
   - Mixed decls? → Wrap in `& {}` or move up
   - Duplicate tags? → Remove orphaned code

4. **Apply targeted fix**
   - Small fixes: Use replace_string_in_file
   - Batch fixes: Use sed commands
   - Large cleanups: Delete line ranges

5. **Rebuild and validate**
   ```bash
   npm run build
   ```

6. **Repeat until clean build** (errors are sequential)

### SCSS File Organization Rules

**Import order (MUST be at top, before any code):**
```scss
// 1. Sass built-ins first
@use 'sass:map';
@use 'sass:math';

// 2. Variables and configuration
@use 'variables' as v;
@use 'mixins' as m;

// 3. External libraries (if any)
@use 'some-library';

// 4. Now write your styles
.component {
  padding: v.$spacing-4;
}
```

**Variable naming conventions:**
```scss
// Use descriptive suffixes for variants
$shadow-sm: ...;        // Small
$shadow-md: ...;        // Medium (default)
$shadow-lg: ...;        // Large
$shadow-xl: ...;        // Extra large

$shadow-focus-primary: ...;  // Specific use case variant

// NOT just numeric without context
$shadow-1: ...;  // ❌ What does 1 mean?
$shadow-2: ...;  // ❌ Is 2 bigger or darker?
```

**Mixin organization:**
```scss
// Base mixin (foundation)
@mixin card-base {
  // Declarations first
  padding: v.$spacing-4;
  background: v.$background-card;
  
  // Nested rules after
  @media (min-width: 768px) {
    padding: v.$spacing-8;
  }
}

// Variant mixins (extend base)
@mixin card-elevated {
  @include card-base;
  
  & {  // ✅ Wrap to avoid mixed-decls
    box-shadow: v.$shadow-lg;
  }
}
```

### Production Build Validation

**Before committing SCSS changes:**

```bash
# 1. Clean build
rm -rf dist/
npm run build

# 2. Check for errors
# Should show: "✓ built in X.XXs"
# Should NOT show: "[sass]" or "Undefined variable"

# 3. Check for warnings
# Acceptable: None
# Fix immediately: "Deprecation Warning: mixed-decls"

# 4. Verify bundle sizes (should be reasonable)
# CSS: < 250 KB (gzipped < 50 KB)
# JS: < 500 KB (gzipped < 150 KB)

# 5. Test in browser
npm run dev
# Open http://localhost:5173
# Check DevTools Console for errors
```

**Build output should show:**
```
✓ 134 modules transformed.
✓ built in 2.31s
PWA v0.21.1
precache  83 entries (2952.94 KiB)

# No errors ✅
# No warnings ✅
# All assets generated ✅
```

---

## 📚 Quick Reference - Design System Checklist

### Before Writing ANY Component Code

**Step 1: Check Global Patterns** (in order of preference)

- [ ] Does a **component** already exist? (`GlassCard`, `LoadingSkeleton`, `EmptyState`, `StatusCard`)
- [ ] Does a **utility class** exist? (`.badge`, `.btn`, `.card`, `.alert`, `.status-border-*`)
- [ ] Does a **design token** exist? (`v.$primary-color`, `v.$spacing-md`, `v.$border-radius`)
- [ ] Does a **mixin** exist? (`@include m.respond-below('md')`, `@include m.card-base`)
- [ ] Is this pattern in **DESIGN_SYSTEM.md**? (Check for copy-paste examples)

**Step 2: Only If Truly Unique**

If you checked all 5 items above and found nothing → Then write component-specific styles.

**Step 3: Follow Design Principles**

- [ ] Use glassmorphism effects (backdrop-blur, translucent backgrounds)
- [ ] Add smooth animations (0.2-0.3s transitions)
- [ ] Implement loading states (`<LoadingSkeleton>`)
- [ ] Implement empty states (`<EmptyState>`)
- [ ] Make touch-friendly (44px minimum targets on mobile)
- [ ] Responsive design (`@include m.respond-below('md')`)

---

### Component Import Quick Reference

**CRITICAL:** Always verify correct folder before importing!

```typescript
// Cards (in cards/ subfolder)
import GlassCard from '@/components/cards/GlassCard.vue'
import StreamerCard from '@/components/cards/StreamerCard.vue'
import VideoCard from '@/components/cards/VideoCard.vue'
import StatusCard from '@/components/cards/StatusCard.vue'

// Common Components (in root components/ folder)
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ToastContainer from '@/components/ToastContainer.vue'

// Navigation (in navigation/ subfolder)
import NavigationWrapper from '@/components/navigation/NavigationWrapper.vue'
import SidebarNav from '@/components/navigation/SidebarNav.vue'
import BottomNav from '@/components/navigation/BottomNav.vue'

// Settings (in settings/ subfolder)
import RecordingSettingsPanel from '@/components/settings/RecordingSettingsPanel.vue'
import NotificationSettingsPanel from '@/components/settings/NotificationSettingsPanel.vue'
import ProxySettingsPanel from '@/components/settings/ProxySettingsPanel.vue'
```

**Component Folder Structure:**
```
app/frontend/src/components/
├── cards/              ← Card components (GlassCard, StreamerCard, VideoCard, StatusCard)
├── navigation/         ← Navigation components (SidebarNav, BottomNav, NavigationWrapper)
├── settings/           ← Settings panels (Recording, Notification, Proxy)
├── admin/              ← Admin-specific components
├── icons/              ← Icon components
└── *.vue              ← Root components (LoadingSkeleton, EmptyState, ToastContainer)
```

---

### SCSS Import Quick Reference

```scss
// At top of every <style> block (MUST be first lines)
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

// Then use:
color: v.$primary-color;           // NOT #42b883
padding: v.$spacing-md;            // NOT 16px
border-radius: v.$border-radius;   // NOT 8px

@include m.respond-below('md') {   // NOT @media (max-width: 768px)
  padding: v.$spacing-sm;
}
```

---

## Component Import Best Practices (CRITICAL)

### ⚠️ ALWAYS Verify File Location Before Importing

**Problem:** Build failures from wrong import paths (e.g., Issue #15 - GlassCard import)

**Root Cause:**
- Components moved during refactoring
- Imports not updated
- Build succeeds locally (cached) but fails in CI

**MANDATORY Workflow:**

**Step 1: Verify Component Exists**
```bash
# Before importing, CHECK file location:
ls app/frontend/src/components/cards/GlassCard.vue
ls app/frontend/src/components/LoadingSkeleton.vue
ls app/frontend/src/components/navigation/SidebarNav.vue
```

**Step 2: Use Correct Path Alias**
```typescript
// ✅ CORRECT: Use @ alias (tsconfig.json path mapping)
import GlassCard from '@/components/cards/GlassCard.vue'

// ❌ WRONG: Relative paths are fragile
import GlassCard from '../cards/GlassCard.vue'
import GlassCard from '../../components/cards/GlassCard.vue'
```

**Step 3: Verify Folder Structure**
```
components/
├── cards/          ← GlassCard, StreamerCard, VideoCard, StatusCard
├── navigation/     ← SidebarNav, BottomNav, NavigationWrapper
├── settings/       ← RecordingSettingsPanel, NotificationSettingsPanel, ProxySettingsPanel
├── admin/          ← Admin components
├── icons/          ← Icon components
└── *.vue          ← Root components (LoadingSkeleton, EmptyState, ToastContainer)
```

**Step 4: Use IDE Autocomplete**
```typescript
// Type import and let IDE suggest path:
import GlassCard from '@/components/  // ← Ctrl+Space shows available folders
```

### Common Import Errors

**❌ ERROR: Importing from wrong subfolder**
```typescript
// WRONG: GlassCard is in cards/, not common/
import GlassCard from '@/components/common/GlassCard.vue'  // ❌ File not found!

// CORRECT:
import GlassCard from '@/components/cards/GlassCard.vue'   // ✅
```

**❌ ERROR: Importing root component from subfolder**
```typescript
// WRONG: LoadingSkeleton is in root components/, not common/
import LoadingSkeleton from '@/components/common/LoadingSkeleton.vue'  // ❌

// CORRECT:
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'  // ✅
```

**❌ ERROR: Using relative path**
```typescript
// WRONG: Relative paths break when file moves
import GlassCard from '../cards/GlassCard.vue'  // ❌ Fragile

// CORRECT: Path alias is robust
import GlassCard from '@/components/cards/GlassCard.vue'  // ✅
```

### Import Verification Checklist

**Before committing new component imports:**
- [ ] Verified file exists with `ls` or File Explorer
- [ ] Used `@/` path alias (not relative paths)
- [ ] Correct subfolder (`cards/`, `navigation/`, `settings/`, or root)
- [ ] IDE shows no red squiggles on import
- [ ] `npm run type-check` passes
- [ ] `npm run build` succeeds
- [ ] No console errors in dev server

### When Moving Components

**If you move a component to different folder:**

**Step 1: Search for all imports**
```bash
# Find all imports of the component
grep -r "import.*GlassCard" app/frontend/src/
```

**Step 2: Update all import paths**
```bash
# Check how many files need updating
grep -r "from '@/components/common/GlassCard.vue'" app/frontend/src/

# Update each file
```

**Step 3: Verify build**
```bash
cd app/frontend
npm run type-check  # Must pass
npm run build       # Must succeed
```

**Step 4: Test in browser**
- Start dev server: `npm run dev`
- Navigate to affected pages
- Check console: No import errors
- Verify components render

### IDE Configuration

**Ensure tsconfig.json has path aliases:**
```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]  // Enables @/components/... imports
    }
  }
}
```

**VSCode Benefits:**
- Ctrl+Click on import → Jumps to file
- Autocomplete suggests available components
- Red squiggle if file not found
- Rename refactoring updates imports

### Production Build Prevention

**Always test build before pushing:**
```bash
# MANDATORY before commit:
cd app/frontend
npm run build

# If build fails → Fix imports BEFORE committing
# CI/CD will catch import errors, but fix locally first
```

**CI/CD Protection:**
- GitHub Actions runs `npm run build`
- Fails if any import path wrong
- Blocks merge until fixed

---

### Common Mistakes to Avoid

❌ **DON'T:**
```vue
<!-- Creating custom card styles -->
<div class="my-custom-card">

<style>
.my-custom-card {
  background: rgba(31, 31, 35, 0.7);
  backdrop-filter: blur(16px);
  /* 😫 Duplicating GlassCard! */
}
</style>
```

✅ **DO:**
```vue
<!-- Use existing component -->
<GlassCard>
  <!-- ✨ Automatic glassmorphism -->
</GlassCard>
```

---

❌ **DON'T:**
```vue
<!-- Custom button styling -->
<button class="my-button">Click</button>

<style>
.my-button {
  background: #42b883;
  color: white;
  /* 😫 Duplicating .btn-primary! */
}
</style>
```

✅ **DO:**
```vue
<!-- Use utility class -->
<button class="btn btn-primary">Click</button>
<!-- ✨ Theme-aware, consistent -->
```

---

❌ **DON'T:**
```vue
<!-- Hard-coded loading state -->
<div v-if="loading" class="my-skeleton">
  <div class="shimmer"></div>
</div>

<style>
/* 😫 Reimplementing LoadingSkeleton! */
</style>
```

✅ **DO:**
```vue
<!-- Use existing component -->
<LoadingSkeleton v-if="loading" type="card" />
<!-- ✨ Consistent shimmer animation -->
```

---

### Documentation References

**Complete Guides:**
- `docs/DESIGN_SYSTEM.md` - 800+ lines of copy-paste examples
- `docs/COMPLETE_DESIGN_OVERHAUL_SUMMARY.md` - Redesign documentation
- `.github/copilot-instructions.md` - Project-wide conventions

**Key Sections in This File:**
- Line ~50: **SCSS & Styling Philosophy** - Global-first approach
- Line ~210: **Design Language** - Glassmorphism principles
- Line ~250: **Available Components** - GlassCard, LoadingSkeleton, etc.
- Line ~450: **Global Utility Classes** - Complete reference
- Line ~650: **SCSS Variables** - Design tokens
- Line ~1300: **View Patterns** - Standard layouts for new views
- Line ~1520: **Global SCSS Changes** - When to use global files

**Quick Search:**
- Need a button? → Search "Button Styling" or ".btn"
- Need a card? → Search "GlassCard Component"
- Need colors? → Search "Color Variables" or "Design Tokens"
- Need breakpoints? → Search "Breakpoints & Responsive"
- Need animations? → Search "Animation Patterns"

---

**Remember:** When in doubt, reuse global patterns! The design system exists to make your life easier. 🚀


