---
applyTo: "app/frontend/**/*.vue,app/frontend/**/*.ts,app/frontend/**/*.scss"
---

# Frontend Development Guidelines

## Component Architecture

- Use Vue 3 Composition API with `<script setup lang="ts">`
- Prefer composables over mixins for reusable logic
- Keep components focused - one responsibility per component
- **NO MAGIC NUMBERS**: Extract delays, thresholds, timeouts to named constants
- **USE VUE LIFECYCLE**: Use `nextTick()` instead of `setTimeout()` for deferred operations

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
- `32px` → `$spacing-xl` (2rem)

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
