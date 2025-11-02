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

### Status Indicators
Use `.status-border-*` classes for left-accent borders:
- `.status-border-primary`, `.status-border-success`, `.status-border-error`

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
