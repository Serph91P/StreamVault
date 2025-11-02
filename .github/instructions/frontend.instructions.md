---
applyTo: "app/frontend/**/*.vue,app/frontend/**/*.ts,app/frontend/**/*.scss"
---

# Frontend Development Guidelines

## Component Architecture

- Use Vue 3 Composition API with `<script setup lang="ts">`
- Prefer composables over mixins for reusable logic
- Keep components focused - one responsibility per component

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

## SCSS Variables

**NEVER hard-code colors/spacing** - use variables from `_variables.scss`:
```scss
@use 'styles/variables' as v;

.component {
  background: v.$background-card;
  color: v.$text-primary;
  padding: v.$spacing-md v.$spacing-lg;
  border-radius: v.$border-radius;
}
```

## Touch Targets

All interactive elements must have `min-height: 44px` on mobile for accessibility.

## Breakpoints

- Mobile: 320px-640px (base styles)
- Tablet: 768px-1023px
- Desktop: 1024px+
- Large: 1440px+
- XL: 1920px+

Use `@media (min-width: X)` for progressive enhancement.
