# Component Modernization Guide - Quick Reference

**Date**: November 9, 2025  
**Purpose**: Step-by-step guide for modernizing remaining components with design tokens

---

## 🎯 Modernization Checklist

For each component, follow this systematic approach:

### 1. **Spacing** 
Replace all hardcoded px values with spacing tokens:

```scss
// ❌ Old
padding: 12px 24px;
margin: 16px 0;
gap: 8px;

// ✅ New (SCSS files)
padding: v.$spacing-3 v.$spacing-6;  // 12px 24px
margin: v.$spacing-4 0;  // 16px 0
gap: v.$spacing-2;  // 8px

// ✅ New (Vue scoped styles)
padding: var(--spacing-3) var(--spacing-6);  // 12px 24px
margin: var(--spacing-4) 0;  // 16px 0
gap: var(--spacing-2);  // 8px
```

**Spacing Scale Reference:**
| Token | Value | Use Case |
|-------|-------|----------|
| `v.$spacing-1` / `var(--spacing-1)` | 4px | Tiny gaps, icon margins |
| `v.$spacing-2` / `var(--spacing-2)` | 8px | Small gaps, button gaps |
| `v.$spacing-3` / `var(--spacing-3)` | 12px | Default padding |
| `v.$spacing-4` / `var(--spacing-4)` | 16px | Section spacing |
| `v.$spacing-5` / `var(--spacing-5)` | 20px | Card padding |
| `v.$spacing-6` / `var(--spacing-6)` | 24px | Large padding |
| `v.$spacing-8` / `var(--spacing-8)` | 32px | Section margins |

### 2. **Typography**
Replace font-size and font-weight with typography tokens:

```scss
// ❌ Old
font-size: 14px;
font-weight: 600;
line-height: 1.5;

// ✅ New (SCSS)
font-size: v.$text-sm;  // 14px
font-weight: v.$font-semibold;  // 600
line-height: v.$leading-relaxed;  // 1.625

// ✅ New (Vue scoped)
font-size: var(--text-sm);  // 14px
font-weight: var(--font-semibold);  // 600
line-height: var(--leading-relaxed);  // 1.625
```

**Typography Scale:**
| Size Token | Value | Weight Token | Value |
|------------|-------|--------------|-------|
| `v.$text-xs` | 12px | `v.$font-light` | 300 |
| `v.$text-sm` | 14px | `v.$font-normal` | 400 |
| `v.$text-base` | 16px | `v.$font-medium` | 500 |
| `v.$text-lg` | 18px | `v.$font-semibold` | 600 |
| `v.$text-xl` | 20px | `v.$font-bold` | 700 |
| `v.$text-2xl` | 24px | | |
| `v.$text-3xl` | 30px | | |

**Line Heights:**
| Token | Value | Use Case |
|-------|-------|----------|
| `v.$leading-tight` | 1.25 | Headings |
| `v.$leading-snug` | 1.375 | Titles |
| `v.$leading-normal` | 1.5 | Default text |
| `v.$leading-relaxed` | 1.625 | Paragraph text |
| `v.$leading-loose` | 2 | Spaced content |

### 3. **Colors**
Replace all color values with theme-aware CSS variables:

```scss
// ❌ Old
color: #f1f1f3;
background: #1a1a1f;
border-color: rgba(127, 127, 127, 0.3);

// ✅ New
color: var(--text-primary);
background: var(--background-card);
border-color: var(--border-color);
```

**Color Variable Reference:**
| Variable | Use Case |
|----------|----------|
| `var(--text-primary)` | Main text color |
| `var(--text-secondary)` | Secondary/muted text |
| `var(--background-card)` | Card backgrounds |
| `var(--background-darker)` | Input backgrounds |
| `var(--background-hover)` | Hover states |
| `var(--border-color)` | Borders |
| `var(--primary-color)` | Primary brand color |
| `var(--accent-color)` | Accent highlights |
| `var(--success-color)` | Success states |
| `var(--danger-color)` | Error states |
| `var(--warning-color)` | Warning states |
| `var(--info-color)` | Info states |

### 4. **Border Radius**
Replace hardcoded border-radius values:

```scss
// ❌ Old
border-radius: 8px;
border-radius: 12px;
border-radius: 50%;

// ✅ New (SCSS)
border-radius: v.$border-radius-md;  // 10px
border-radius: v.$border-radius-lg;  // 12px
border-radius: v.$border-radius-full;  // 9999px (pill/circle)

// ✅ New (Vue scoped)
border-radius: var(--radius-md);  // 10px
border-radius: var(--radius-lg);  // 12px
border-radius: var(--radius-full);  // 9999px
```

**Border Radius Scale:**
| Token | Value | Use Case |
|-------|-------|----------|
| `v.$border-radius-sm` / `var(--radius-sm)` | 6px | Small elements |
| `v.$border-radius-md` / `var(--radius-md)` | 10px | Buttons, inputs |
| `v.$border-radius-lg` / `var(--radius-lg)` | 12px | Cards |
| `v.$border-radius-xl` / `var(--radius-xl)` | 16px | Modals |
| `v.$border-radius-2xl` / `var(--radius-2xl)` | 20px | Large cards |
| `v.$border-radius-full` / `var(--radius-full)` | 9999px | Pills, circles |

### 5. **Shadows**
Replace box-shadow with shadow tokens:

```scss
// ❌ Old
box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);

// ✅ New (SCSS)
box-shadow: v.$shadow-sm;
box-shadow: v.$shadow-md;

// ✅ New (Vue scoped)
box-shadow: var(--shadow-sm);
box-shadow: var(--shadow-md);
```

**Shadow Scale:**
| Token | Use Case |
|-------|----------|
| `v.$shadow-xs` / `var(--shadow-xs)` | Subtle depth |
| `v.$shadow-sm` / `var(--shadow-sm)` | Cards, buttons |
| `v.$shadow-md` / `var(--shadow-md)` | Elevated cards |
| `v.$shadow-lg` / `var(--shadow-lg)` | Dropdowns |
| `v.$shadow-xl` / `var(--shadow-xl)` | Modals |
| `v.$shadow-2xl` / `var(--shadow-2xl)` | Overlays |

**Focus Shadows:**
| Token | Use Case |
|-------|----------|
| `v.$shadow-focus-primary` / `var(--shadow-focus-primary)` | Primary focus |
| `v.$shadow-focus-danger` / `var(--shadow-focus-danger)` | Error focus |
| `v.$shadow-focus-success` / `var(--shadow-focus-success)` | Success focus |

### 6. **Transitions**
Replace transition values with standard tokens:

```scss
// ❌ Old
transition: all 0.2s ease;
transition: color 0.3s;

// ✅ New (SCSS)
transition: v.$transition-all;  // all 150ms ease-in-out
transition: v.$transition-colors;  // color, background 150ms

// ✅ New (Vue scoped)
transition: var(--transition-all);
transition: var(--transition-colors);
```

**Transition Tokens:**
| Token | Properties | Duration | Easing |
|-------|-----------|----------|--------|
| `v.$transition-colors` | color, background | 150ms | ease-in-out |
| `v.$transition-opacity` | opacity | 150ms | ease-in-out |
| `v.$transition-transform` | transform | 150ms | ease-in-out |
| `v.$transition-all` | all | 150ms | ease-in-out |

**Duration Only:**
| Token | Value |
|-------|-------|
| `v.$duration-75` | 75ms |
| `v.$duration-150` | 150ms |
| `v.$duration-200` | 200ms |
| `v.$duration-300` | 300ms |
| `v.$duration-500` | 500ms |

**Easing Only:**
| Token | Curve |
|-------|-------|
| `v.$ease-in` | cubic-bezier(0.4, 0, 1, 1) |
| `v.$ease-out` | cubic-bezier(0, 0, 0.2, 1) |
| `v.$ease-in-out` | cubic-bezier(0.4, 0, 0.2, 1) |

### 7. **Touch Targets (Mobile)**
Ensure all interactive elements meet minimum size:

```scss
// ✅ All buttons, links, inputs
.btn, button, a, input, select {
  min-height: 44px;  // Minimum touch target
  min-width: 44px;   // For icon-only buttons
}
```

### 8. **Focus States (Accessibility)**
Add visible focus indicators:

```scss
// ✅ All interactive elements
.btn, button, a, input {
  &:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
    box-shadow: var(--shadow-focus-primary);
  }
}
```

---

## 📝 Step-by-Step Process

### For SCSS Files (e.g., `_components.scss`, `_views.scss`)

1. **Import design tokens** (if not already):
   ```scss
   @use 'variables' as v;
   @use 'mixins' as m;
   ```

2. **Find and replace spacing**:
   - Search: `padding: (\d+)px`
   - Consider: Map to nearest spacing token
   - Replace: `padding: v.$spacing-X`

3. **Find and replace typography**:
   - Search: `font-size: (\d+)px`
   - Replace: `font-size: v.$text-X`
   - Search: `font-weight: (\d+)`
   - Replace: `font-weight: v.$font-X`

4. **Replace colors**:
   - Search: `color: #[0-9a-f]{3,6}`
   - Replace: `color: var(--text-primary)` (context-dependent)

5. **Replace border-radius**:
   - Search: `border-radius: (\d+)px`
   - Replace: `border-radius: v.$border-radius-X`

6. **Replace shadows**:
   - Search: `box-shadow: 0 \d+px`
   - Replace: `box-shadow: v.$shadow-X`

7. **Add responsive helpers**:
   ```scss
   @include m.respond-to('md') {
     // Desktop styles
   }

   @include m.respond-below('md') {
     // Mobile styles
   }
   ```

### For Vue Scoped Styles

1. **Use CSS custom properties**:
   ```vue
   <style scoped>
   .component {
     padding: var(--spacing-4);  /* 16px */
     font-size: var(--text-base);  /* 16px */
     border-radius: var(--radius-md);  /* 10px */
     box-shadow: var(--shadow-sm);
   }
   </style>
   ```

2. **Add accessibility**:
   ```scss
   .interactive-element {
     min-height: 44px;  // Touch target

     &:focus-visible {
       outline: 2px solid var(--primary-color);
       outline-offset: 2px;
     }
   }
   ```

3. **Mobile-first responsive**:
   ```scss
   .component {
     padding: var(--spacing-3);  // 12px mobile

     @media (min-width: 768px) {
       padding: var(--spacing-6);  // 24px desktop
     }
   }
   ```

---

## 🔍 Common Patterns

### Buttons
```scss
.btn {
  padding: var(--spacing-3) var(--spacing-6);  // 12px 24px
  font-size: var(--text-base);  // 16px
  font-weight: var(--font-semibold);  // 600
  border-radius: var(--radius-md);  // 10px
  transition: var(--transition-all);
  min-height: 44px;

  &:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }

  &:focus-visible {
    outline: 2px solid var(--primary-color);
    box-shadow: var(--shadow-focus-primary);
  }
}
```

### Cards
```scss
.card {
  padding: var(--spacing-6);  // 24px
  border-radius: var(--radius-lg);  // 12px
  background: var(--background-card);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  transition: var(--transition-all);

  &:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
  }
}
```

### Inputs
```scss
.input-field {
  padding: var(--spacing-3) var(--spacing-4);  // 12px 16px
  font-size: var(--text-base);  // 16px (prevents iOS zoom)
  border-radius: var(--radius-md);  // 10px
  background: var(--background-darker);
  border: 2px solid var(--border-color);
  color: var(--text-primary);
  min-height: 44px;

  &:focus {
    border-color: var(--primary-color);
    box-shadow: var(--shadow-focus-primary);
    outline: none;
  }
}
```

### Modals
```scss
.modal {
  background: var(--background-card);
  border-radius: var(--radius-xl);  // 16px
  padding: var(--spacing-6);  // 24px
  box-shadow: var(--shadow-2xl);
  border: 1px solid var(--border-color);
}

.modal-overlay {
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
}
```

---

## ⚠️ Gotchas & Tips

### 1. **Mobile Font Sizes**
Always use minimum 16px font-size on inputs to prevent iOS zoom:
```scss
input, select, textarea {
  font-size: var(--text-base);  // 16px minimum
}
```

### 2. **Touch Targets**
All interactive elements need 44x44px minimum:
```scss
button, a, input, select {
  min-height: 44px;
  min-width: 44px;  // For icon-only
}
```

### 3. **Focus Indicators**
Always add visible focus states for keyboard navigation:
```scss
:focus-visible {
  outline: 2px solid var(--primary-color);
  outline-offset: 2px;
}
```

### 4. **Responsive Breakpoints**
Use the mixin helpers:
```scss
// Mobile-first
.component {
  padding: var(--spacing-3);

  @include m.respond-to('md') {  // >= 768px
    padding: var(--spacing-6);
  }
}

// Desktop-first (if needed)
@include m.respond-below('md') {  // < 768px
  padding: var(--spacing-2);
}
```

### 5. **Custom Scrollbars**
Standardize scrollbar styling:
```scss
.scrollable::-webkit-scrollbar {
  width: 8px;
}

.scrollable::-webkit-scrollbar-track {
  background: var(--background-darker);
}

.scrollable::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: var(--radius-full);
}

.scrollable::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}
```

### 6. **Line Clamping**
Use both standard and webkit for compatibility:
```scss
.truncate-2-lines {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;  // Standard property
  -webkit-box-orient: vertical;
  overflow: hidden;
}
```

---

## 🧪 Validation Checklist

After modernizing a component:

- [ ] No hardcoded px values remain
- [ ] All colors use `var(--name)` theme variables
- [ ] Border-radius uses token system
- [ ] Box-shadows use shadow tokens
- [ ] Typography uses text/font tokens
- [ ] Touch targets >= 44px
- [ ] Focus states visible and accessible
- [ ] Mobile-responsive (test at 375px, 768px, 1024px)
- [ ] No compile errors (`get_errors` tool)
- [ ] Component renders correctly in browser
- [ ] Dark/light mode both work (if theme toggle exists)

---

## 📚 Reference Files

- **Design Tokens**: `app/frontend/src/styles/_variables.scss`
- **Utility Classes**: `app/frontend/src/styles/_utilities.scss`
- **Mixins**: `app/frontend/src/styles/_mixins.scss`
- **Component Examples**: `app/frontend/src/styles/_components.scss`
- **Full Reference**: `docs/DESIGN_SYSTEM_REFERENCE.md`

---

**Last Updated**: November 9, 2025  
**Next Component**: _views.scss (global view styles)
