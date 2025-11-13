# StreamVault Design System

**Version:** 2.0  
**Datum:** 12. November 2025  
**Status:** ✅ Production Ready

---

## 📋 Übersicht

Dieses Design-System stellt alle wiederverwendbaren UI-Komponenten, Utility-Klassen, Mixins und Pattern für StreamVault bereit. **IMMER** diese globalen Styles verwenden anstatt per-Component-Duplikation.

---

## 🎨 Design Tokens (CSS Custom Properties)

### Farben

Alle Farben sind über CSS Custom Properties verfügbar und reagieren automatisch auf Theme-Switches (Dark/Light Mode).

```scss
// Brand Colors
var(--primary-color)        // Teal #14b8a6
var(--primary-color-light)  // Teal-400 #2dd4bf
var(--primary-color-dark)   // Teal-600 #0d9488
var(--accent-color)         // Purple #8b5cf6
var(--secondary-color)      // Alias für accent

// Semantic Colors
var(--success-color)        // Green #10b981
var(--danger-color)         // Red #ef4444
var(--warning-color)        // Orange #f59e0b
var(--info-color)           // Blue #3b82f6

// Backgrounds
var(--background-dark)      // Slate-900 (dark) / Slate-50 (light)
var(--background-darker)    // Slate-950 (dark) / Slate-100 (light)
var(--background-card)      // Slate-800 (dark) / White (light)

// Text
var(--text-primary)         // Slate-50 (dark) / Slate-900 (light)
var(--text-secondary)       // Slate-400 (dark) / Slate-600 (light)

// Borders
var(--border-color)         // Slate-700 (dark) / Slate-300 (light)

// RGB Values (für rgba() Nutzung)
var(--primary-color-rgb)    // 20, 184, 166
var(--danger-color-rgb)     // 239, 68, 68
var(--background-card-rgb)  // 30, 41, 59 (dark) / 255, 255, 255 (light)
```

### Spacing (4px Base Grid)

```scss
var(--spacing-1)   // 4px
var(--spacing-2)   // 8px
var(--spacing-3)   // 12px
var(--spacing-4)   // 16px
var(--spacing-5)   // 20px
var(--spacing-6)   // 24px
var(--spacing-8)   // 32px
var(--spacing-10)  // 40px
var(--spacing-12)  // 48px
var(--spacing-16)  // 64px
```

**Utility-Klassen:**

```html
<!-- Padding -->
<div class="p-4">Padding: 16px</div>
<div class="px-6">Padding X: 24px</div>
<div class="py-3">Padding Y: 12px</div>

<!-- Margin -->
<div class="m-4">Margin: 16px</div>
<div class="mx-auto">Horizontal zentriert</div>
<div class="mb-6">Margin Bottom: 24px</div>

<!-- Gap -->
<div class="gap-4">Gap: 16px (Flexbox/Grid)</div>
```

### Border Radius

```scss
var(--radius-sm)   // 4px
var(--radius)      // 8px (Standard)
var(--radius-md)   // 10px
var(--radius-lg)   // 12px
var(--radius-xl)   // 16px
var(--radius-2xl)  // 24px
var(--radius-full) // 9999px (Pills, Circles)
```

**Utility-Klassen:**

```html
<div class="rounded-lg">Border-radius: 12px</div>
<div class="rounded-full">Kreisförmig</div>
```

### Shadows (Elevation)

```scss
var(--shadow-xs)    // Minimal
var(--shadow-sm)    // Subtil (Cards)
var(--shadow-md)    // Medium (Hover)
var(--shadow-lg)    // Prominent (Modals)
var(--shadow-xl)    // Sehr prominent
var(--shadow-2xl)   // Maximum elevation
```

**Utility-Klassen:**

```html
<div class="shadow-md">Medium shadow</div>
<div class="shadow-lg">Large shadow</div>
```

### Typography

```scss
// Font Sizes
var(--text-xs)    // 12px
var(--text-sm)    // 14px
var(--text-base)  // 16px
var(--text-lg)    // 18px
var(--text-xl)    // 20px
var(--text-2xl)   // 24px
var(--text-3xl)   // 30px

// Line Heights
var(--leading-tight)    // 1.25
var(--leading-normal)   // 1.5
var(--leading-relaxed)  // 1.625
```

**Utility-Klassen:**

```html
<h1 class="heading-1">Große Überschrift (responsive)</h1>
<h2 class="heading-2">Medium Überschrift</h2>
<p class="text-lg font-semibold">Großer, fetter Text</p>
<span class="text-sm text-secondary">Kleiner Sekundärtext</span>
```

---

## 🧱 Button System

### Base Button Klassen

```html
<!-- Primary Action -->
<button class="btn btn-primary">Speichern</button>

<!-- Secondary Action -->
<button class="btn btn-secondary">Abbrechen</button>

<!-- Accent (Purple) -->
<button class="btn btn-accent">Highlights</button>

<!-- Danger (Destructive) -->
<button class="btn btn-danger">Löschen</button>

<!-- Success -->
<button class="btn btn-success">Erfolgreich</button>

<!-- Warning -->
<button class="btn btn-warning">Warnung</button>

<!-- Info -->
<button class="btn btn-info">Information</button>
```

### Button Varianten

```html
<!-- Ghost/Outline (transparenter Hintergrund) -->
<button class="btn btn-ghost">Ghost</button>
<button class="btn btn-outline-primary">Outline Primary</button>
<button class="btn btn-outline-danger">Outline Danger</button>

<!-- Text Button (nur Text, kein Hintergrund) -->
<button class="btn btn-text">Text Button</button>

<!-- Icon-Only Button -->
<button class="btn btn-icon">
  <svg>...</svg>
</button>

<!-- Button mit Icon + Text -->
<button class="btn btn-primary btn-with-icon">
  <svg>...</svg>
  <span>Mit Icon</span>
</button>
```

### Button Sizes

```html
<!-- Klein (32px min-height) -->
<button class="btn btn-primary btn-sm">Klein</button>

<!-- Standard (36px desktop / 44px mobile) -->
<button class="btn btn-primary">Standard</button>

<!-- Groß (48px min-height) -->
<button class="btn btn-primary btn-lg">Groß</button>

<!-- Full-Width (für Mobile-Forms) -->
<button class="btn btn-primary btn-block">Volle Breite</button>
```

**Wichtig:** Alle Buttons haben automatisch:
- **Mobile**: 44px min-height (Apple HIG Touch Target)
- **Desktop**: 36px min-height
- Hover-Lift-Effekt (translateY -1px)
- Focus-Outline für Accessibility

---

## 🏷️ Badge System

### Status Badges

```html
<!-- Live Status (pulsierendes Rot) -->
<span class="status-badge status-live">LIVE</span>

<!-- Recording Status (pulsierender Border) -->
<span class="status-badge status-recording">RECORDING</span>

<!-- Offline Status -->
<span class="status-badge status-offline">OFFLINE</span>

<!-- Processing -->
<span class="status-badge status-processing">PROCESSING</span>

<!-- Completed -->
<span class="status-badge status-completed">COMPLETED</span>
```

### Small Badges (Pills)

```html
<!-- Color Variants -->
<span class="badge badge-primary">Primary</span>
<span class="badge badge-success">Success</span>
<span class="badge badge-danger">Danger</span>
<span class="badge badge-warning">Warning</span>
<span class="badge badge-info">Info</span>
<span class="badge badge-neutral">Neutral</span>

<!-- Sizes -->
<span class="badge badge-sm badge-primary">Klein</span>
<span class="badge badge-primary">Standard</span>
<span class="badge badge-lg badge-primary">Groß</span>

<!-- Mit Dot-Indikator (z.B. LIVE) -->
<span class="badge badge-danger badge-dot">LIVE</span>
```

### Border Accents (für Cards)

```html
<div class="card status-border-live">
  <!-- Linke Border: rot (LIVE) -->
</div>

<div class="card status-border-recording">
  <!-- Linke Border: rot, pulsierend (RECORDING) -->
</div>

<div class="card status-border-success">
  <!-- Linke Border: grün (SUCCESS) -->
</div>
```

---

## 📢 Alert/Banner System

```html
<!-- Info Alert -->
<div class="alert alert-info">
  <div class="alert-icon">
    <svg>...</svg>
  </div>
  <div class="alert-content">
    <strong>Info:</strong> Wichtige Information hier.
  </div>
</div>

<!-- Success Alert -->
<div class="alert alert-success">
  <div class="alert-icon">✓</div>
  <div class="alert-content">Erfolgreich gespeichert!</div>
</div>

<!-- Warning Alert -->
<div class="alert alert-warning">
  <div class="alert-icon">⚠</div>
  <div class="alert-content">Achtung: Bitte überprüfen.</div>
</div>

<!-- Danger Alert -->
<div class="alert alert-danger">
  <div class="alert-icon">✕</div>
  <div class="alert-content">Fehler aufgetreten.</div>
</div>

<!-- Full-Width Banner (kein Border-Radius) -->
<div class="alert alert-info banner">
  Banner über volle Breite
</div>
```

---

## 🃏 Card System

### Verwendung in Vue-Komponenten (Mixins)

```scss
<style scoped lang="scss">
@use '@/styles/mixins' as m;

.my-card {
  @include m.card-base;  // Standard Card
}

.elevated-card {
  @include m.card-elevated;  // Erhöhte Elevation
}

.flat-card {
  @include m.card-flat;  // Ohne Shadow
}

.glass-card {
  @include m.card-glass;  // Glassmorphism
}

.compact-card {
  @include m.card-compact;  // Weniger Padding
}

.accent-card {
  @include m.card-with-border-accent(var(--primary-color), 4px);
  // Linke Border-Akzent
}
</style>
```

### Utility-Klassen (HTML)

```html
<!-- Standard Card -->
<div class="card">
  <h3>Card Title</h3>
  <p>Card content...</p>
</div>

<!-- Glassmorphism Card -->
<div class="glass-card">
  <h3>Glass Card</h3>
  <p>Mit Backdrop-Blur...</p>
</div>

<!-- Elevated Card (mehr Shadow) -->
<div class="card card-elevated">
  Elevated Card
</div>

<!-- Interactive Card (Hover-Effekt + Cursor) -->
<div class="card card-interactive">
  Klickbare Card
</div>
```

---

## 🔲 Modal System

```html
<!-- Modal Overlay (Fullscreen + Blur) -->
<div class="modal-overlay" @click.self="closeModal">
  <div class="modal-card">
    <!-- Modal Header -->
    <div class="modal-header">
      <h2 class="modal-title">Modal Titel</h2>
      <button class="modal-close" @click="closeModal">
        <svg>...</svg>
      </button>
    </div>
    
    <!-- Modal Body -->
    <div class="modal-body">
      <p>Modal Content hier...</p>
    </div>
    
    <!-- Modal Footer (optional) -->
    <div class="modal-footer">
      <button class="btn btn-secondary" @click="closeModal">
        Abbrechen
      </button>
      <button class="btn btn-primary" @click="save">
        Speichern
      </button>
    </div>
  </div>
</div>
```

**Features:**
- `modal-overlay`: Fullscreen, backdrop-blur, z-index: 1000
- `modal-card`: Zentriert, max-width: 600px, max-height: 90vh
- Click-outside schließt Modal (verwende `@click.self`)

---

## 🎬 Loading States & Skeletons

```html
<!-- Skeleton Loaders -->
<div class="skeleton skeleton-heading"></div>
<div class="skeleton skeleton-text"></div>
<div class="skeleton skeleton-text"></div>
<div class="skeleton skeleton-button"></div>
<div class="skeleton skeleton-card"></div>
<div class="skeleton skeleton-avatar"></div>
```

**Animation:** Automatisches Shimmer-Effect via CSS Animation

---

## 🧩 Layout Utilities

### Flexbox

```html
<div class="flex items-center justify-between gap-4">
  <span>Links</span>
  <button>Rechts</button>
</div>

<div class="flex flex-col gap-3">
  <div>Element 1</div>
  <div>Element 2</div>
</div>
```

**Klassen:**
- `.flex`, `.inline-flex`
- `.flex-row`, `.flex-col`, `.flex-row-reverse`, `.flex-col-reverse`
- `.justify-start`, `.justify-center`, `.justify-between`, `.justify-end`
- `.items-start`, `.items-center`, `.items-end`, `.items-stretch`
- `.gap-1`, `.gap-2`, `.gap-3`, `.gap-4`, `.gap-6`, `.gap-8`

### Display

```html
<div class="block">Block</div>
<div class="inline-block">Inline Block</div>
<div class="hidden">Versteckt</div>
```

### Position

```html
<div class="relative">Relative</div>
<div class="absolute">Absolute</div>
<div class="fixed">Fixed</div>
<div class="sticky">Sticky</div>
```

---

## 📐 Responsive Breakpoints

### SCSS Mixins (EMPFOHLEN)

```scss
@use '@/styles/mixins' as m;

.component {
  // Mobile-First: Base styles
  padding: 8px;
  
  // Tablet & Desktop (>= 768px)
  @include m.respond-to('md') {
    padding: 16px;
  }
  
  // Mobile Only (< 640px)
  @include m.respond-below('sm') {
    font-size: 14px;
  }
}
```

### Breakpoint-Werte

```scss
'xs':  375px   // Mobile extra-small (iPhone SE)
'sm':  640px   // Mobile / Phablet
'md':  768px   // Tablet portrait
'lg':  1024px  // Desktop / Tablet landscape
'xl':  1200px  // Large desktop
```

**⚠️ VERBOTEN:** Hard-coded `@media (max-width: XXXpx)` in Vue-Komponenten!  
**✅ IMMER:** SCSS Mixins verwenden (`@include m.respond-to()`)

---

## 🎨 Text Utilities

```html
<!-- Alignment -->
<p class="text-left">Linksbündig</p>
<p class="text-center">Zentriert</p>
<p class="text-right">Rechtsbündig</p>

<!-- Transform -->
<p class="uppercase">UPPERCASE</p>
<p class="lowercase">lowercase</p>
<p class="capitalize">Capitalize</p>

<!-- Truncate -->
<p class="truncate">Langer Text mit Ellipsis...</p>
<p class="line-clamp-2">Zwei Zeilen max...</p>
<p class="line-clamp-3">Drei Zeilen max...</p>

<!-- Colors -->
<p class="text-primary">Primary Color</p>
<p class="text-secondary">Secondary (grau)</p>
<p class="text-danger">Danger Color</p>
<p class="text-success">Success Color</p>

<!-- Gradients -->
<h1 class="text-gradient">Gradient Text (Primary → Accent)</h1>
```

---

## 🎭 Animations

### Keyframe Animations

```html
<!-- Fade In -->
<div class="animate-fade-in">Erscheint sanft</div>

<!-- Slide Up -->
<div class="animate-slide-up">Gleitet von unten</div>

<!-- Slide Down -->
<div class="animate-slide-down">Gleitet von oben</div>

<!-- Slide In (Left/Right) -->
<div class="animate-slide-in-right">Von rechts</div>
<div class="animate-slide-in-left">Von links</div>

<!-- Shake (Error) -->
<div class="animate-shake">Schütteln</div>

<!-- Spin (Loader) -->
<div class="animate-spin">Rotiert endlos</div>
```

### Transition Utilities

```html
<div class="transition-all duration-300 ease-in-out">
  Smooth transition für alle Properties
</div>

<button class="transition-colors hover-lift">
  Nur Colors transitionieren + Hover-Lift
</button>
```

**Klassen:**
- `.transition-all`, `.transition-colors`, `.transition-opacity`, `.transition-shadow`, `.transition-transform`
- `.duration-150`, `.duration-200`, `.duration-300`, `.duration-500`
- `.ease-linear`, `.ease-in`, `.ease-out`, `.ease-in-out`

---

## 🧰 Hilfreiche Mixins

### In Vue-Komponenten verwenden

```scss
<style scoped lang="scss">
@use '@/styles/mixins' as m;

// Hover Lift Effect
.my-button {
  @include m.hover-lift(2px, var(--shadow-lg));
}

// Text Truncate
.title {
  @include m.truncate;
}

// Multi-Line Clamp
.description {
  @include m.line-clamp(3);  // Max 3 Zeilen
}

// Flex Center
.icon-wrapper {
  @include m.flex-center;
}

// Focus Outline (Accessibility)
.interactive {
  @include m.focus-outline;
}

// Aspect Ratio (für responsive Images/Videos)
.video-container {
  @include m.aspect-ratio(16, 9);
}

// Custom Scrollbar
.scrollable {
  @include m.smooth-scroll;
}
</style>
```

---

## 🔄 Divider / Separator

```html
<!-- Horizontale Linie -->
<div class="divider"></div>

<!-- Vertikale Linie -->
<div class="flex items-center">
  <span>Links</span>
  <div class="divider-vertical"></div>
  <span>Rechts</span>
</div>

<!-- Divider mit Text -->
<div class="divider-text">ODER</div>
```

---

## 🎯 Best Practices

### ✅ DO's

1. **IMMER CSS Custom Properties nutzen:**
   ```scss
   color: var(--text-primary);  // ✅
   background: var(--background-card);  // ✅
   ```

2. **IMMER Spacing-Variablen nutzen:**
   ```scss
   padding: var(--spacing-4);  // ✅
   gap: var(--spacing-3);      // ✅
   ```

3. **IMMER globale Utility-Klassen verwenden wo möglich:**
   ```html
   <div class="flex items-center gap-4 p-6 rounded-lg shadow-md">
   ```

4. **IMMER SCSS Mixins für Breakpoints:**
   ```scss
   @include m.respond-to('md') { ... }  // ✅
   ```

5. **IMMER globale Button-Klassen:**
   ```html
   <button class="btn btn-primary">  // ✅
   ```

### ❌ DON'Ts

1. **NIEMALS hard-coded colors:**
   ```scss
   color: #14b8a6;  // ❌
   background: #1e293b;  // ❌
   ```

2. **NIEMALS hard-coded spacing:**
   ```scss
   padding: 16px;  // ❌
   margin: 24px;   // ❌
   ```

3. **NIEMALS hard-coded breakpoints in Vue:**
   ```scss
   @media (max-width: 768px) { ... }  // ❌
   ```

4. **NIEMALS inline styles für wiederholende Patterns:**
   ```html
   <button style="padding: 8px 16px; background: #14b8a6;">  // ❌
   ```

5. **NIEMALS per-Component Button-Styling:**
   ```scss
   // ❌ DON'T: Custom button in jeder Komponente
   .my-custom-button {
     background: teal;
     padding: 12px 24px;
   }
   
   // ✅ DO: Globale Klasse verwenden
   <button class="btn btn-primary">
   ```

---

## 📚 Zusätzliche Ressourcen

- **Frontend Instructions:** `.github/instructions/frontend.instructions.md`
- **SCSS Breakpoint Migration:** `docs/REMAINING_FRONTEND_TASKS.md`
- **Design Overhaul Summary:** `docs/COMPLETE_DESIGN_OVERHAUL_SUMMARY.md`

---

## 🚀 Schnellreferenz

### Neue Seite erstellen?

1. **Verwende globale Layout-Utilities:**
   ```html
   <div class="container py-8">
     <h1 class="heading-1 mb-6">Seitentitel</h1>
     
     <div class="card mb-4">
       <h2 class="heading-3 mb-3">Section</h2>
       <p class="body-readable">Content...</p>
     </div>
     
     <div class="flex gap-3">
       <button class="btn btn-primary">Speichern</button>
       <button class="btn btn-secondary">Abbrechen</button>
     </div>
   </div>
   ```

2. **Importiere Mixins wo nötig:**
   ```scss
   @use '@/styles/mixins' as m;
   
   .custom-card {
     @include m.card-base;
     @include m.respond-to('md') {
       padding: var(--spacing-8);
     }
   }
   ```

3. **Nutze Animationen:**
   ```html
   <div class="animate-fade-in">
     <div class="animate-slide-up">Content...</div>
   </div>
   ```

---

**Fazit:** Mit diesem Design-System können neue Seiten **konsistent**, **wartbar** und **schnell** erstellt werden, ohne per-Component-Duplikation.
