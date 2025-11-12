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

## Component Architecture

- Use Vue 3 Composition API with `<script setup lang="ts">`
- Prefer composables over mixins for reusable logic
- Keep components focused - one responsibility per component
- **NO MAGIC NUMBERS**: Extract delays, thresholds, timeouts to named constants
- **USE VUE LIFECYCLE**: Use `nextTick()` instead of `setTimeout()` for deferred operations

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

## SCSS Variables & Design Tokens

**CRITICAL: NEVER hard-code colors, spacing, or border-radius!**

Always use SCSS variables from `_variables.scss` or CSS custom properties:

### Color Variables
```scss
// SCSS variables
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

// CSS custom properties (runtime-accessible)
var(--primary-color)
var(--danger-color)
var(--success-color)
var(--warning-color)
var(--info-color)
var(--background-card)
var(--text-primary)
var(--text-secondary)
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

❌ **Bad - Hard-coded values:**
```scss
.card {
  background: #1f1f23;
  color: #f1f1f3;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #2d2d35;
}

.badge {
  background: #22c55e;
  color: #ffffff;
  border-radius: 4px;
}
```

✅ **Good - Design tokens:**
```scss
@use 'styles/variables' as v;

.card {
  background: v.$background-card;
  color: v.$text-primary;
  padding: v.$spacing-md;
  border-radius: v.$border-radius;
  border: 1px solid v.$border-color;
}

.badge {
  background: v.$success-color;
  color: v.$text-primary;
  border-radius: v.$border-radius-sm;
}
```

✅ **Also Good - CSS custom properties (for dynamic values):**
```scss
.card {
  background: var(--background-card);
  color: var(--text-primary);
  padding: var(--spacing-md, 1rem);
  border-radius: var(--border-radius, 8px);
}
```

### Common Mappings

When refactoring hard-coded values:

**Colors:**
- `#42b883`, `#2ed573`, `#22c55e`, `#28a745` → `$success-color` / `var(--success-color)`
- `#ff4757`, `#ef4444`, `#dc2626`, `#dc3545` → `#danger-color` / `var(--danger-color)`
- `#ffa502`, `#f59e0b`, `#eab308`, `#ffc107` → `$warning-color` / `var(--warning-color)`
- `#70a1ff`, `#3b82f6`, `#2563eb`, `#3498db` → `$info-color` / `var(--info-color)` or `$primary-color`
- `#1f1f23`, `#18181b` → `$background-card` / `$background-darker`
- `#ffffff`, `#f1f1f3` → `$text-primary`
- `#aaa`, `#b1b1b9`, `#ccc`, `#6b7280` → `$text-secondary`

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

