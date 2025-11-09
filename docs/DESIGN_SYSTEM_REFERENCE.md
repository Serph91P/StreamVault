# Design System Quick Reference

Schnelle Übersicht über alle verfügbaren Design-Tokens und Utility-Klassen.

## 🎨 Farben

### Theme Colors (CSS Custom Properties)
```scss
// Brand
--primary-color          // Teal #14b8a6
--accent-color           // Purple #8b5cf6

// Semantic
--success-color          // Green
--danger-color           // Red
--warning-color          // Orange
--info-color             // Blue

// Text
--text-primary           // Main text
--text-secondary         // Muted text

// Backgrounds
--background-dark        // Main background
--background-darker      // Deeper background
--background-card        // Card background

// Borders
--border-color           // Border color
```

### Utility Classes
```html
<p class="text-primary">Primary text</p>
<p class="text-secondary">Secondary text</p>
<p class="text-accent">Accent colored</p>
<p class="text-success">Success message</p>
<p class="text-danger">Error message</p>
<p class="text-warning">Warning</p>
<p class="text-info">Info text</p>
```

## 📝 Typography

### Font Sizes
```html
<p class="text-xs">Extra small (12px)</p>
<p class="text-sm">Small (14px)</p>
<p class="text-base">Base (16px)</p>
<p class="text-lg">Large (18px)</p>
<p class="text-xl">Extra large (20px)</p>
<p class="text-2xl">2XL (24px)</p>
<p class="text-3xl">3XL (30px)</p>
<p class="text-4xl">4XL (36px)</p>
<p class="text-5xl">5XL (48px)</p>
```

### Font Weights
```html
<p class="font-light">Light (300)</p>
<p class="font-normal">Normal (400)</p>
<p class="font-medium">Medium (500)</p>
<p class="font-semibold">Semibold (600)</p>
<p class="font-bold">Bold (700)</p>
```

### Line Heights
```html
<p class="leading-none">1.0</p>
<p class="leading-tight">1.25</p>
<p class="leading-snug">1.375</p>
<p class="leading-normal">1.5</p>
<p class="leading-relaxed">1.625</p>
<p class="leading-loose">2.0</p>
```

### Text Utilities
```html
<p class="text-left">Left aligned</p>
<p class="text-center">Centered</p>
<p class="text-right">Right aligned</p>

<p class="uppercase">UPPERCASE</p>
<p class="lowercase">lowercase</p>
<p class="capitalize">Capitalized</p>

<p class="truncate">Long text that will be truncated...</p>
<p class="line-clamp-2">Text limited to 2 lines...</p>
```

## 📏 Spacing

### Spacing Scale (4px base)
- `0` = 0px
- `1` = 4px
- `2` = 8px
- `3` = 12px
- `4` = 16px
- `5` = 20px
- `6` = 24px
- `8` = 32px
- `10` = 40px
- `12` = 48px

### Padding
```html
<!-- All sides -->
<div class="p-4">16px padding</div>
<div class="p-6">24px padding</div>

<!-- Horizontal (left + right) -->
<div class="px-4">16px horizontal</div>

<!-- Vertical (top + bottom) -->
<div class="py-2">8px vertical</div>
```

### Margin
```html
<!-- All sides -->
<div class="m-4">16px margin</div>

<!-- Auto centering -->
<div class="mx-auto">Centered</div>

<!-- Bottom spacing -->
<div class="mb-4">16px bottom margin</div>

<!-- Top spacing -->
<div class="mt-6">24px top margin</div>
```

## 🌓 Shadows

### Elevation Levels
```html
<div class="shadow-xs">Subtle</div>
<div class="shadow-sm">Small</div>
<div class="shadow-md">Medium</div>
<div class="shadow-lg">Large</div>
<div class="shadow-xl">Extra large</div>
<div class="shadow-2xl">2XL</div>

<div class="shadow-none">No shadow</div>
<div class="shadow-inner">Inner shadow</div>
```

### Focus Shadows
```html
<button class="shadow-primary-focus">Primary focus</button>
<button class="shadow-accent-focus">Accent focus</button>
<button class="shadow-danger-focus">Danger focus</button>
```

## 🔲 Border Radius

```html
<div class="rounded-none">No radius</div>
<div class="rounded-sm">4px</div>
<div class="rounded">8px</div>
<div class="rounded-md">10px</div>
<div class="rounded-lg">12px</div>
<div class="rounded-xl">16px</div>
<div class="rounded-2xl">24px</div>
<div class="rounded-3xl">32px</div>
<div class="rounded-full">Fully rounded (pill/circle)</div>
```

## 🎭 Flexbox

### Display
```html
<div class="flex">Flexbox</div>
<div class="inline-flex">Inline flex</div>
<div class="grid">Grid</div>
<div class="block">Block</div>
<div class="hidden">Hidden</div>
```

### Direction
```html
<div class="flex flex-row">Row (default)</div>
<div class="flex flex-col">Column</div>
```

### Justify Content
```html
<div class="flex justify-start">Start</div>
<div class="flex justify-center">Center</div>
<div class="flex justify-end">End</div>
<div class="flex justify-between">Space between</div>
<div class="flex justify-around">Space around</div>
```

### Align Items
```html
<div class="flex items-start">Start</div>
<div class="flex items-center">Center</div>
<div class="flex items-end">End</div>
<div class="flex items-stretch">Stretch</div>
```

### Gap
```html
<div class="flex gap-2">8px gap</div>
<div class="flex gap-4">16px gap</div>
<div class="flex gap-6">24px gap</div>
```

### Common Patterns
```html
<!-- Centered content -->
<div class="flex items-center justify-center">
  Centered both ways
</div>

<!-- Space between items -->
<div class="flex items-center justify-between">
  <span>Left</span>
  <span>Right</span>
</div>

<!-- Vertical stack with gap -->
<div class="flex flex-col gap-4">
  <div>Item 1</div>
  <div>Item 2</div>
</div>
```

## ⚡ Transitions

### Transition Types
```html
<div class="transition-all">All properties</div>
<div class="transition-colors">Colors only</div>
<div class="transition-opacity">Opacity only</div>
<div class="transition-shadow">Shadow only</div>
<div class="transition-transform">Transform only</div>
```

### Duration
```html
<div class="transition-all duration-150">Fast (150ms)</div>
<div class="transition-all duration-300">Medium (300ms)</div>
<div class="transition-all duration-500">Slow (500ms)</div>
```

### Easing
```html
<div class="transition-all ease-linear">Linear</div>
<div class="transition-all ease-in">Ease in</div>
<div class="transition-all ease-out">Ease out</div>
<div class="transition-all ease-in-out">Ease in-out</div>
```

## 📦 Complete Component Example

```vue
<template>
  <div class="flex flex-col gap-4 p-6">
    <!-- Card with shadow and rounded corners -->
    <div class="rounded-lg shadow-md p-6 bg-card">
      
      <!-- Header with spacing -->
      <h2 class="text-2xl font-bold mb-4 text-primary">
        Card Title
      </h2>
      
      <!-- Content with gap -->
      <div class="flex flex-col gap-3">
        <p class="text-base leading-normal text-secondary">
          This is a description using the new design system.
        </p>
        
        <!-- Button group -->
        <div class="flex gap-2 mt-4">
          <button class="px-4 py-2 rounded-md shadow-sm 
                         transition-all duration-150 ease-out
                         hover:shadow-primary-focus">
            Primary
          </button>
          
          <button class="px-4 py-2 rounded-md shadow-sm
                         transition-colors duration-150">
            Secondary
          </button>
        </div>
      </div>
    </div>
    
    <!-- Another card -->
    <div class="rounded-xl shadow-lg p-8">
      <h3 class="text-xl font-semibold mb-3 text-accent">
        Feature Card
      </h3>
      
      <p class="text-sm leading-relaxed text-secondary line-clamp-3">
        Long description that will be limited to 3 lines with an ellipsis
        at the end if it exceeds that limit.
      </p>
    </div>
  </div>
</template>
```

## 🎯 SCSS Variables Usage

### In Component Styles
```scss
<style scoped lang="scss">
@use '@/styles/variables' as v;

.custom-button {
  padding: v.$spacing-3 v.$spacing-6;
  font-size: v.$text-base;
  font-weight: v.$font-semibold;
  border-radius: v.$border-radius-md;
  box-shadow: v.$shadow-sm;
  transition: v.$transition-colors;
  
  &:hover {
    box-shadow: v.$shadow-md;
  }
  
  &:focus {
    box-shadow: v.$shadow-primary;
  }
}

.card-title {
  font-size: v.$text-2xl;
  line-height: v.$leading-tight;
  margin-bottom: v.$spacing-4;
  color: var(--text-primary);
}
</style>
```

### CSS Custom Properties
```scss
.dynamic-element {
  // Use CSS vars for theme-aware properties
  background-color: var(--background-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  
  // Use SCSS vars for static properties
  padding: v.$spacing-4;
  border-radius: v.$border-radius-lg;
  box-shadow: v.$shadow-md;
}
```

## 🌈 Color Scales (SCSS only)

```scss
// Primary (Teal)
v.$primary-50   // Lightest
v.$primary-100
v.$primary-200
v.$primary-300
v.$primary-400
v.$primary-500  // Main (CSS: --primary-color)
v.$primary-600
v.$primary-700
v.$primary-800
v.$primary-900  // Darkest

// Accent (Purple)
v.$accent-50 to v.$accent-900

// Neutrals (Slate)
v.$slate-50 to v.$slate-950

// Semantic
v.$success-50, v.$success-400, v.$success-500, v.$success-600, v.$success-700
v.$danger-50 to v.$danger-700
v.$warning-50 to v.$warning-700
v.$info-50 to v.$info-700
```

## 💡 Best Practices

### ✅ DO

```html
<!-- Use utility classes for layout and spacing -->
<div class="flex items-center gap-4 p-6">

<!-- Use CSS vars for theme-aware colors -->
<p style="color: var(--text-primary)">

<!-- Combine utilities for complex layouts -->
<div class="flex flex-col md:flex-row justify-between items-start gap-6">
```

### ❌ DON'T

```html
<!-- Don't use inline styles for spacing -->
<div style="padding: 24px">  ❌

<!-- Use utility classes instead -->
<div class="p-6">  ✅

<!-- Don't hardcode colors -->
<p style="color: #14b8a6">  ❌

<!-- Use CSS vars or utility classes -->
<p class="text-primary">  ✅
```

## 🔍 Migration Tips

### Old → New

```scss
// OLD
padding: 24px;
margin-bottom: 16px;
font-size: 14px;
box-shadow: 0 2px 4px rgba(0,0,0,0.1);

// NEW (SCSS)
padding: v.$spacing-6;
margin-bottom: v.$spacing-4;
font-size: v.$text-sm;
box-shadow: v.$shadow-sm;

// NEW (HTML Utilities)
<div class="p-6 mb-4 text-sm shadow-sm">
```

### Theme-Aware Colors

```scss
// OLD (hardcoded)
color: #f1f1f3;
background: #1f1f23;

// NEW (theme-aware)
color: var(--text-primary);
background: var(--background-card);
```

---

**Vollständige Dokumentation**: Siehe `docs/theme_rewrite_roadmap.md`
