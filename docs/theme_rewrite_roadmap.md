# StreamVault - Theme Rewrite Roadmap

**Erstellt:** 4. November 2025  
**Aktualisiert:** 4. November 2025  
**Status:** ✅ Bereit für Implementierung  
**Ziel:** Modernes, konsistentes Design-System mit Theme-Support (Dark + Light Mode)

---

## 🎯 Entscheidung: Color Palette Option B (Modern Neutral)

**Gewählt am:** 4. November 2025  
**Begründung:** 
- Unabhängige, eigenständige Brand-Identity (kein Twitch-Kopie)
- Professional und modern
- Teal/Purple Kombination ist zeitgemäß und vielseitig
- Bessere Eignung für Dark + Light Mode

**Anforderungen:**
- ✅ Dark Mode (Primär)
- ✅ Light Mode (Secondary)
- ✅ Theme-Toggle im UI (localStorage-basiert)
- ✅ Smooth Transitions zwischen Themes

---

## 📋 Aktueller Stand

### ✅ Abgeschlossen: Phase 1 & 2 - Design Token Migration (KOMPLETT)
**Status:** 100% abgeschlossen am 4. November 2025

**Statistiken:**
- **14 Komponenten** vollständig refactored
  - Phase 1-2: 6 Komponenten (StreamList, AdminPanel, BackgroundQueueMonitor, FavoritesSettingsPanel, RecordingSettingsPanel, NotificationsDashboard)
  - Phase 3: 8 Komponenten (StatusDashboard, TwitchImportForm, VideosView, PWATester, VideoModal, PostProcessingManagement, etc.)
- **~170+ hard-coded values** zu CSS-Variablen migriert
- **0 hard-coded Farben übrig** (verifiziert mit grep)
- **100% Design Token Coverage** erreicht

**Technische Grundlage:**
- ✅ Alle Komponenten nutzen zentrale Design-Tokens aus `_variables.scss`
- ✅ Semantische Farbnamen (`--primary-color`, `--danger-color`, etc.)
- ✅ Konsistente Border-Radius-Werte (`--border-radius-sm/default/lg/xl`)
- ✅ Codebase bereit für Theme-Switching

---

## 🎨 Phase 3: Theme Rewrite (Nach Phase 2)

### 1. Design-System Audit & Planung

**Aufgaben:**
- [ ] Farbpalette analysieren und modernisieren
- [ ] Typography-System überarbeiten (Font-Stacks, Sizes, Line-Heights)
- [ ] Spacing-System vereinheitlichen (4px/8px Grid?)
- [ ] Shadow-System definieren (elevation levels)
- [ ] Border-Radius-System erweitern (aktuelle Werte: 4px, 8px, 12px, 16px)
- [ ] Animation/Transition-System standardisieren

**Deliverables:**
- Design-Tokens-Dokumentation
- Figma/Design-Mockups (optional)
- Color-Contrast-Matrix (WCAG AA/AAA)

---

### 2. Neues Color-System

#### Aktuelles Problem:
- Inkonsistente Farben: `#42b883`, `#3498db`, `#ef4444`, etc.
- Keine semantische Hierarchie
- Dark-Theme ist primär, Light-Theme existiert nicht

#### Vorschlag: Modern Color Palette

**Option A: Twitch-inspired (Gaming-fokussiert)**
```scss
// Primary Colors
$primary-500: #9147ff;      // Twitch Purple (Main Brand)
$primary-400: #a970ff;
$primary-600: #772ce8;

// Accent Colors
$accent-500: #00f2ea;       // Twitch Cyan (Highlights)
$accent-400: #33f4ed;
$accent-600: #00d9d1;

// Semantic Colors
$success-500: #00f593;      // Bright Green
$danger-500: #ff4757;       // Red
$warning-500: #ffd93d;      // Yellow
$info-500: #1e90ff;         // Blue

// Neutrals (Dark Theme)
$gray-50: #fafafa;
$gray-100: #f4f4f5;
$gray-200: #e4e4e7;
$gray-300: #d4d4d8;
$gray-400: #a1a1aa;
$gray-500: #71717a;
$gray-600: #52525b;
$gray-700: #3f3f46;
$gray-800: #27272a;
$gray-900: #18181b;
$gray-950: #0a0a0b;
```

**Option B: Modern Neutral (Professional)**
```scss
// Primary Colors (Teal/Green)
$primary-500: #14b8a6;      // Teal
$primary-400: #2dd4bf;
$primary-600: #0d9488;

// Accent Colors (Purple)
$accent-500: #8b5cf6;
$accent-400: #a78bfa;
$accent-600: #7c3aed;

// Semantic Colors
$success-500: #10b981;
$danger-500: #ef4444;
$warning-500: #f59e0b;
$info-500: #3b82f6;

// Neutrals (Slate-based)
$slate-50: #f8fafc;
$slate-900: #0f172a;
// ... rest of slate scale
```

#### Migration Plan:
1. Neue Farben in `_variables.scss` definieren
2. CSS Custom Properties mit beiden Themes erstellen
3. Theme-Switcher implementieren (localStorage)
4. Komponenten testen und anpassen

---

### 3. Typography-System

#### Aktuelles Problem:
- Inkonsistente Font-Sizes
- Keine definierte Type-Scale
- Line-Heights sind hard-coded

#### Vorschlag: Type-Scale System

```scss
// Font Families
$font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
$font-mono: 'Fira Code', 'Monaco', 'Courier New', monospace;

// Type Scale (1.250 - Major Third)
$text-xs: 0.75rem;      // 12px
$text-sm: 0.875rem;     // 14px
$text-base: 1rem;       // 16px
$text-lg: 1.125rem;     // 18px
$text-xl: 1.25rem;      // 20px
$text-2xl: 1.5rem;      // 24px
$text-3xl: 1.875rem;    // 30px
$text-4xl: 2.25rem;     // 36px

// Line Heights
$leading-none: 1;
$leading-tight: 1.25;
$leading-snug: 1.375;
$leading-normal: 1.5;
$leading-relaxed: 1.625;
$leading-loose: 2;

// Font Weights
$font-light: 300;
$font-normal: 400;
$font-medium: 500;
$font-semibold: 600;
$font-bold: 700;
```

**Migration:**
- Alle `font-size` zu `$text-*` migrieren
- Alle `line-height` zu `$leading-*` migrieren
- Font-weights vereinheitlichen

---

### 4. Spacing-System

#### Aktuelles Problem:
- Random spacing values: `12px`, `15px`, `18px`, `24px`
- Keine konsistente Skala

#### Vorschlag: 4px Base Grid

```scss
// Spacing Scale (4px base)
$spacing-0: 0;
$spacing-1: 0.25rem;    // 4px
$spacing-2: 0.5rem;     // 8px
$spacing-3: 0.75rem;    // 12px
$spacing-4: 1rem;       // 16px
$spacing-5: 1.25rem;    // 20px
$spacing-6: 1.5rem;     // 24px
$spacing-8: 2rem;       // 32px
$spacing-10: 2.5rem;    // 40px
$spacing-12: 3rem;      // 48px
$spacing-16: 4rem;      // 64px
$spacing-20: 5rem;      // 80px
$spacing-24: 6rem;      // 96px
```

**Usage:**
```scss
.card {
  padding: $spacing-6;           // 24px
  margin-bottom: $spacing-4;     // 16px
  gap: $spacing-3;               // 12px
}
```

---

### 5. Shadow-System

#### Vorschlag: Elevation Levels

```scss
// Shadows (5 levels)
$shadow-xs: 0 1px 2px 0 rgb(0 0 0 / 0.05);
$shadow-sm: 0 1px 3px 0 rgb(0 0 0 / 0.1);
$shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
$shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
$shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1);
$shadow-2xl: 0 25px 50px -12px rgb(0 0 0 / 0.25);

// Colored Shadows (for focus, hover)
$shadow-primary: 0 0 0 3px rgba($primary-500, 0.1);
$shadow-danger: 0 0 0 3px rgba($danger-500, 0.1);
```

---

### 6. Border-Radius-System (Erweitert)

#### Aktuell:
```scss
$border-radius-sm: 4px;
$border-radius: 8px;
$border-radius-lg: 12px;
$border-radius-xl: 16px;
```

#### Vorschlag: Erweitern
```scss
$border-radius-none: 0;
$border-radius-sm: 0.25rem;     // 4px
$border-radius: 0.5rem;         // 8px
$border-radius-md: 0.625rem;    // 10px
$border-radius-lg: 0.75rem;     // 12px
$border-radius-xl: 1rem;        // 16px
$border-radius-2xl: 1.5rem;     // 24px
$border-radius-full: 9999px;    // Pills, circles
```

---

### 7. Animation-System

#### Vorschlag: Standardisierte Transitions

```scss
// Timing Functions
$ease-linear: linear;
$ease-in: cubic-bezier(0.4, 0, 1, 1);
$ease-out: cubic-bezier(0, 0, 0.2, 1);
$ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
$ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);

// Durations
$duration-75: 75ms;
$duration-100: 100ms;
$duration-150: 150ms;
$duration-200: 200ms;
$duration-300: 300ms;
$duration-500: 500ms;
$duration-700: 700ms;
$duration-1000: 1000ms;

// Common Transitions
$transition-base: all $duration-200 $ease-in-out;
$transition-colors: color $duration-150 $ease-in-out,
                    background-color $duration-150 $ease-in-out,
                    border-color $duration-150 $ease-in-out;
$transition-transform: transform $duration-200 $ease-out;
```

---

### 8. Component-Specific Changes

#### Button-System Overhaul
```scss
.btn {
  // Base styles with new system
  padding: $spacing-3 $spacing-6;
  font-size: $text-base;
  font-weight: $font-medium;
  border-radius: $border-radius;
  transition: $transition-base;
  
  // Size variants
  &.btn-sm { padding: $spacing-2 $spacing-4; font-size: $text-sm; }
  &.btn-lg { padding: $spacing-4 $spacing-8; font-size: $text-lg; }
  
  // Color variants with new palette
  &.btn-primary { 
    background: $primary-500;
    &:hover { background: $primary-600; }
  }
}
```

#### Card-System
```scss
.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: $border-radius-lg;
  padding: $spacing-6;
  box-shadow: $shadow-sm;
  
  &:hover {
    box-shadow: $shadow-md;
    transform: translateY(-2px);
    transition: $transition-base;
  }
}
```

---

### 9. Theme-Switcher Implementation

#### Komponente: `ThemeSwitcher.vue`

```typescript
// Store theme in localStorage
const theme = ref(localStorage.getItem('theme') || 'dark');

const toggleTheme = () => {
  theme.value = theme.value === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', theme.value);
  localStorage.setItem('theme', theme.value);
};

// Apply on mount
onMounted(() => {
  document.documentElement.setAttribute('data-theme', theme.value);
});
```

#### CSS Custom Properties (both themes)

```scss
// Dark Theme (default)
:root,
[data-theme="dark"] {
  --primary: #{$primary-500};
  --background: #{$gray-900};
  --card-bg: #{$gray-800};
  --text-primary: #{$gray-50};
  --text-secondary: #{$gray-400};
  // ... all tokens
}

// Light Theme
[data-theme="light"] {
  --primary: #{$primary-500};
  --background: #{$gray-50};
  --card-bg: white;
  --text-primary: #{$gray-900};
  --text-secondary: #{$gray-600};
  // ... all tokens
}
```

---

## 📅 Implementierungs-Zeitplan

### Woche 1-2: Planung & Design
- [ ] Design-System-Dokumentation finalisieren
- [ ] Farbpalette entscheiden (Option A vs B)
- [ ] Mockups erstellen (optional)
- [ ] Stakeholder-Feedback einholen

### Woche 3-4: Core-System Implementation
- [ ] Neue `_variables.scss` mit komplettem Design-System
- [ ] CSS Custom Properties für beide Themes
- [ ] Theme-Switcher-Komponente
- [ ] Global styles updaten

### Woche 5-6: Component Migration
- [ ] Button-System refactoren
- [ ] Card-System refactoren
- [ ] Form-Controls refactoren
- [ ] Navigation refactoren

### Woche 7-8: Testing & Polish
- [ ] Cross-browser testing
- [ ] Accessibility audit (WCAG AA)
- [ ] Performance testing
- [ ] Documentation updaten

---

## 🎯 Success Metrics

- [ ] **100% Design Token Coverage** - Keine hard-coded values mehr
- [ ] **WCAG AA Compliance** - Alle Farbkontraste erfüllen Standards
- [ ] **Theme-Switching** - Seamless light/dark mode toggle
- [ ] **Performance** - Keine Layout-Shifts, smooth transitions
- [ ] **Consistency** - Alle Komponenten nutzen dasselbe Design-System
- [ ] **Documentation** - Vollständige Storybook/Style-Guide

---

## 🚀 Quick Wins (After Phase 2)

**Sofort umsetzbar ohne großes Rewrite:**

1. **Better Focus States**
   ```scss
   *:focus-visible {
     outline: 2px solid var(--primary);
     outline-offset: 2px;
     border-radius: $border-radius-sm;
   }
   ```

2. **Smooth Scrolling**
   ```scss
   html {
     scroll-behavior: smooth;
   }
   ```

3. **Better Loading States**
   - Skeleton screens statt Spinner
   - Smooth fade-ins für Bilder

4. **Micro-Interactions**
   - Button-Ripple-Effekte
   - Smooth hover transitions
   - Success/Error animations

---

## 📚 Ressourcen & Inspiration

**Design Systems:**
- [Tailwind CSS](https://tailwindcss.com/docs/customizing-colors) - Color & Spacing
- [Radix Colors](https://www.radix-ui.com/colors) - Accessible color scales
- [Material Design 3](https://m3.material.io/) - Component patterns
- [Shadcn/ui](https://ui.shadcn.com/) - Modern component library

**Tools:**
- [Coolors](https://coolors.co/) - Color palette generator
- [Contrast Checker](https://webaim.org/resources/contrastchecker/) - WCAG compliance
- [Type Scale](https://type-scale.com/) - Typography calculator
- [Spacing Calculator](https://spacingcalculator.com/) - Spacing system

---

## ⚠️ Breaking Changes

**User Impact:**
- Visual appearance ändert sich komplett
- Theme-Switcher ist neue Feature
- Möglicherweise Custom-CSS-Overrides brechen

**Migration Path:**
- Opt-in Beta-Theme während Entwicklung
- Feature-Flag für Theme-Switcher
- Dokumentation für Custom-CSS-Migrationen

---

## 🚀 Implementierungsplan (Konkret)

### Phase 3A: Color System Implementation (Woche 1-2)

**Schritt 1: Neue Color Palette definieren** (Tag 1-2)
```scss
// app/frontend/src/styles/_theme-colors.scss (NEUE DATEI)

// Option B: Modern Neutral (GEWÄHLT)
// Primary Colors (Teal/Green)
$primary-50: #f0fdfa;
$primary-100: #ccfbf1;
$primary-200: #99f6e4;
$primary-300: #5eead4;
$primary-400: #2dd4bf;
$primary-500: #14b8a6;    // Main
$primary-600: #0d9488;
$primary-700: #0f766e;
$primary-800: #115e59;
$primary-900: #134e4a;

// Accent Colors (Purple)
$accent-50: #faf5ff;
$accent-100: #f3e8ff;
$accent-200: #e9d5ff;
$accent-300: #d8b4fe;
$accent-400: #c084fc;
$accent-500: #a855f7;
$accent-600: #9333ea;
$accent-700: #7e22ce;
$accent-800: #6b21a8;
$accent-900: #581c87;

// Semantic Colors
$success-500: #10b981;
$danger-500: #ef4444;
$warning-500: #f59e0b;
$info-500: #3b82f6;

// Neutrals (Slate) für Dark + Light Mode
$gray-50: #f8fafc;
$gray-100: #f1f5f9;
$gray-200: #e2e8f0;
$gray-300: #cbd5e1;
$gray-400: #94a3b8;
$gray-500: #64748b;
$gray-600: #475569;
$gray-700: #334155;
$gray-800: #1e293b;
$gray-900: #0f172a;
$gray-950: #020617;
```

**Schritt 2: Theme-Switching System** (Tag 3-4)
```scss
// app/frontend/src/styles/_variables.scss (UPDATE)

:root {
  // Default: Dark Mode
  --primary-color: #{$primary-500};
  --primary-color-dark: #{$primary-600};
  --primary-color-light: #{$primary-400};
  
  --accent-color: #{$accent-500};
  
  --success-color: #{$success-500};
  --danger-color: #{$danger-500};
  --warning-color: #{$warning-500};
  --info-color: #{$info-500};
  
  // Dark Mode Backgrounds
  --background-dark: #{$gray-950};
  --background-darker: #{$gray-900};
  --background-card: #{$gray-800};
  
  // Dark Mode Text
  --text-primary: #{$gray-50};
  --text-secondary: #{$gray-400};
  
  // Dark Mode Borders
  --color-border: #{$gray-700};
}

// Light Mode (via data-theme attribute)
[data-theme="light"] {
  // Light Mode Backgrounds
  --background-dark: #{$gray-50};
  --background-darker: #{$gray-100};
  --background-card: white;
  
  // Light Mode Text
  --text-primary: #{$gray-900};
  --text-secondary: #{$gray-600};
  
  // Light Mode Borders
  --color-border: #{$gray-300};
  
  // Angepasste Semantic Colors für Light Mode
  --success-color: #{$success-600};
  --danger-color: #{$danger-600};
  --warning-color: #{$warning-600};
  --info-color: #{$info-600};
}

// Smooth transitions für Theme-Switch
* {
  transition: background-color 0.2s ease, 
              color 0.2s ease, 
              border-color 0.2s ease;
}
```

**Schritt 3: Theme-Toggle Component** (Tag 5-6)
```typescript
// app/frontend/src/components/ThemeToggle.vue (NEUE DATEI)
<script setup lang="ts">
import { ref, onMounted } from 'vue'

type Theme = 'dark' | 'light'

const currentTheme = ref<Theme>('dark')

const setTheme = (theme: Theme) => {
  currentTheme.value = theme
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('streamvault-theme', theme)
}

const toggleTheme = () => {
  const newTheme = currentTheme.value === 'dark' ? 'light' : 'dark'
  setTheme(newTheme)
}

onMounted(() => {
  const savedTheme = localStorage.getItem('streamvault-theme') as Theme
  if (savedTheme) {
    setTheme(savedTheme)
  } else {
    // System preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    setTheme(prefersDark ? 'dark' : 'light')
  }
})
</script>

<template>
  <button 
    @click="toggleTheme"
    class="theme-toggle"
    :aria-label="currentTheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
  >
    <span v-if="currentTheme === 'dark'">🌙</span>
    <span v-else>☀️</span>
  </button>
</template>
```

**Schritt 4: Integration** (Tag 7-8)
- Theme-Toggle in Header/Navigation einbauen
- Alle Komponenten auf neue Farben testen
- WCAG-Kontrast-Prüfung (Dark + Light Mode)

**Schritt 5: Testing** (Tag 9-10)
- Visual Regression Testing (alle Komponenten)
- Accessibility Testing (Kontrast-Ratios)
- Cross-Browser Testing
- Mobile Testing

---

### Phase 3B: Typography & Spacing (Woche 3-4)
- Inter Font-Family einbinden
- Type-Scale implementieren
- Line-Heights standardisieren
- Spacing-System (4px Grid) implementieren

### Phase 3C: Shadows & Animations (Woche 5-6)
- Shadow-System (5 Elevation-Levels)
- Animation-System (Transitions, Easing-Functions)
- Micro-Interactions optimieren

### Phase 3D: Component Polish (Woche 7-8)
- Alle Komponenten durchgehen
- Edge-Cases fixen
- Performance-Optimierung
- Dokumentation schreiben

---

## ✅ Success Criteria

- [ ] **Color System:** 100% Option B implementiert (Dark + Light Mode)
- [ ] **Theme Toggle:** Funktionsfähig und persistent (localStorage)
- [ ] **Typography:** Inter Font + Type-Scale aktiv
- [ ] **Spacing:** 4px Grid konsistent angewendet
- [ ] **Accessibility:** WCAG AA für alle Farb-Kombinationen
- [ ] **Performance:** Theme-Switch < 100ms
- [ ] **Browser Support:** Chrome, Firefox, Safari, Edge (neueste 2 Versionen)
- [ ] **Mobile:** Responsive und touch-friendly
- [ ] **Documentation:** Design-Token-Dokumentation vollständig

---

## 📝 Nächste Schritte (Sofort)

1. **Diese Roadmap reviewen** ✅ (ERLEDIGT)
2. **Option B Color Palette bestätigen** ✅ (ERLEDIGT)
3. **Entscheiden:** Wann mit Phase 3A starten?
4. **Branch erstellen:** `feature/theme-rewrite-phase3`
5. **Erste Implementierung:** `_theme-colors.scss` Datei anlegen

---

**Status:** 📋 Planung abgeschlossen, bereit für Implementierung  
**Nächste Aktion:** Entscheidung wann Phase 3A startet  
**Letzte Aktualisierung:** 4. November 2025
