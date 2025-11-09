# SCSS Design Token Refactoring - Ausstehende Arbeiten

**Stand:** 4. November 2025  
**Ziel:** Alle hard-coded Werte (Farben, border-radius, spacing) durch SCSS-Variablen ersetzen

## ✅ Bereits erledigt

### 1. Documentation (Completed)
- ✅ `.github/instructions/frontend.instructions.md` erweitert mit:
  - Kompletter SCSS-Variablen-Guide
  - Color mappings (#hex → $variable)
  - Border-radius standards (2px→sm, 8px→default, 12px→lg)
  - Spacing guidelines
  - Bad vs Good Beispiele

### 2. StreamList.vue (Completed)
- ✅ Alle Farben zu CSS-Variablen migriert
- ✅ Status-Badges: `#ef4444` → `var(--danger-color)`, etc.
- ✅ Button-Style-Overrides entfernt
- ✅ Alle border-radius zu Variablen
- ✅ Header-Layout verbessert (größerer Titel auf Desktop)

---

## ✅ Bereits erledigt (Fortsetzung)

### 3. AdminPanel.vue (✅ Completed)
**Location:** `app/frontend/src/components/admin/AdminPanel.vue`  
**Lines:** 1800 total

**All completed (28 replacements):**
- ✅ 18 border-radius instances (4px→sm, 6px→default, 8px→default, 12px→lg)
- ✅ 10 color instances (blues, greens, reds, grays → semantic variables)
- ✅ Debug buttons, status badges, utility classes, file extensions all migrated
- ✅ 100% design token coverage - fully theme-ready

### 4. BackgroundQueueMonitor.vue (✅ Completed)
**Location:** `app/frontend/src/components/BackgroundQueueMonitor.vue`  
**Lines:** 738 total

**All completed (50+ replacements):**
- ✅ All colors: #aaa, #3b82f6, #dc3545, #28a745, #eab308, #ffffff → semantic variables
- ✅ All border-radius: 2px, 3px, 4px, 6px, 8px, 12px → design tokens
- ✅ Status badges (pending, running, completed, failed, retrying) using CSS variables
- ✅ Progress bars using gradient with info-color and primary-color
- ✅ Recording indicators using success-color
- ✅ 100% design token coverage - fully theme-ready

---

## 📋 Priority 1 - Critical Components (All Completed! ✨)

---

## 📋 Priority 2 - Settings Panels

### 5. FavoritesSettingsPanel.vue (Not Started)
**Location:** `app/frontend/src/components/settings/FavoritesSettingsPanel.vue`

**Critical issue:** `#18181b` repeated 7x (lines 286, 360, 513, 531, 601)
- Should be: `var(--background-darker)`

**Button colors:**
```scss
Line 640, 645: #42b883, #3ca978 → var(--primary-color) with hover
Line 662, 668: #17a2b8, #138496 → var(--info-color) with hover
Line 674, 680: #ffc107, #e0a800 → var(--warning-color) with hover
Line 688: background: #121214 → var(--background-dark)
```

**Border-radius:**
```scss
Lines 287, 361, 383, 692: 6px
Lines 595, 630: 4px
```

### 6. RecordingSettingsPanel.vue (Not Started)
**Location:** `app/frontend/src/components/settings/RecordingSettingsPanel.vue`

**Border-radius instances (~10+):**
```scss
Line 699: 6px 6px 0 0
Line 1041: 6px
Lines 1468, 1473: 2px
Line 1509, 1617: 8px
Line 1531: 12px
Lines 1560, 1574: 6px
```

### 7. NotificationsDashboard.vue (Not Started)
**Location:** `app/frontend/src/components/NotificationsDashboard.vue`

**Background colors for status indicators:**
```scss
Line 388, 566, 690: #fee2e2 → rgba(var(--danger-color-rgb), 0.1)
Line 393: #dcfce7 → rgba(var(--success-color-rgb), 0.1)
Line 408: #ef4444 → var(--danger-color)
Line 412: #22c55e → var(--success-color)
Line 430, 671: #f9fafb → var(--background-card)
Line 616: #e2e8f0 → var(--border-color)
Line 675: #3b82f6 → var(--info-color)
Line 681: #2563eb → darker info variant
```

---

## 📋 Priority 3 - Remaining Components

### 8. StatusDashboard.vue (Not Started)
**Location:** `app/frontend/src/components/StatusDashboard.vue`

**Colors:**
```scss
Lines 310, 315, 320: Status background colors (#dcfce7, #fee2e2, #fef3c7)
Lines 341, 549: #f9fafb
Line 365: #fee2e2
Line 457: #f8fafc
Line 489: #ef4444
Line 515: #f1f5f9
```

### 9. TwitchImportForm.vue (Not Started)
**Location:** `app/frontend/src/components/TwitchImportForm.vue`

**Colors:**
```scss
Lines 346, 365: #9146FF, #7d5bbe (Twitch purple)
```

### 10. VideosView.vue (Not Started)
**Location:** `app/frontend/src/views/VideosView.vue`

**Colors:**
```scss
Line 596: #e74c3c
Lines 678-681: Theme colors (#404040, #6f42c1, #28a745)
Lines 692-695: Light theme (#dee2e6, #6f42c1, #28a745)
```

**Border-radius:**
```scss
Lines 316, 451: 12px
Lines 330, 345: 25px
Line 366: 20px
Line 401: 15px
Line 504: 4px
Line 610: 8px
```

### 11. PWATester.vue (Not Started)
**Location:** `app/frontend/src/views/PWATester.vue`

**Colors:** Multiple gray shades (#333, #666, #495057)  
**Border-radius:** 6px, 8px variants

### 12. VideoModal.vue (Not Started)
**Location:** `app/frontend/src/components/VideoModal.vue`

**Colors:** Line 504: `background: #000`  

### 13. Smaller Components (Not Started)
- StreamerList.vue
- PWAInstallPrompt.vue
- VideoTabs.vue
- SettingsView.vue

---

## 🎯 Verfügbare SCSS-Variablen

### Farben
```scss
// Main colors
$primary-color: #42b883;
$danger-color: #ff4757;
$success-color: #2ed573;
$warning-color: #ffa502;
$info-color: #70a1ff;
$secondary-color: #6d6d6d;

// Backgrounds
$background-dark: #121214;
$background-darker: #18181b;
$background-card: #1f1f23;

// Text
$text-primary: #f1f1f3;
$text-secondary: #b1b1b9;

// Border
$border-color: #2d2d35;

// CSS Custom Properties (runtime)
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

### Border-Radius
```scss
$border-radius-sm: 4px;
$border-radius: 8px;      // DEFAULT
$border-radius-lg: 12px;
$border-radius-xl: 16px;
$border-radius-pill: 9999px;

// CSS Custom Properties
var(--border-radius-sm, 4px)
var(--border-radius, 8px)
var(--border-radius-lg, 12px)
```

### Spacing
```scss
$spacing-xs: 0.25rem;   // 4px
$spacing-sm: 0.5rem;    // 8px
$spacing-md: 1rem;      // 16px - DEFAULT
$spacing-lg: 1.5rem;    // 24px
$spacing-xl: 2rem;      // 32px
$spacing-xxl: 3rem;     // 48px
```

---

## 📝 Refactoring-Pattern

### Schritt 1: Farben ersetzen
```scss
# Bad
.element {
  background: #1f1f23;
  color: #f1f1f3;
}

# Good
.element {
  background: var(--background-card);
  color: var(--text-primary);
}
```

### Schritt 2: Border-Radius standardisieren
```scss
# Bad
.card { border-radius: 6px; }
.badge { border-radius: 4px; }
.modal { border-radius: 12px; }

# Good
.card { border-radius: var(--border-radius, 8px); }
.badge { border-radius: var(--border-radius-sm, 4px); }
.modal { border-radius: var(--border-radius-lg, 12px); }
```

### Schritt 3: Button-Overrides entfernen
```scss
# Bad - Component-specific button colors
.btn-success { background: #22c55e; }

# Good - Use global classes from _components.scss
/* Button colors handled by global .btn-* classes */
```

---

## 🔍 Grep-Befehle für Suche

```bash
# Find all hard-coded colors
grep -rn "color.*#[0-9a-fA-F]\{3,6\}" app/frontend/src/**/*.vue

# Find all hard-coded backgrounds
grep -rn "background.*#[0-9a-fA-F]\{3,6\}" app/frontend/src/**/*.vue

# Find all border-radius with px
grep -rn "border-radius:.*[0-9]\+px" app/frontend/src/**/*.vue

# Find button color overrides
grep -rn "\.btn-.*background" app/frontend/src/**/*.vue
```

---

## 📊 Statistik

- **Total geschätzte Instanzen:** ~300+ Farben, ~200+ border-radius
- **Completed:** ~10% (StreamList.vue)
- **In Progress:** ~2% (AdminPanel.vue partial)
- **Remaining:** ~88%

**Geschätzte Arbeitszeit:** 4-6 Stunden für vollständige Migration aller Komponenten

---

## ✅ Definition of Done

Eine Komponente gilt als "refactored", wenn:

1. ✅ Keine hard-coded Hex-Farben mehr (`#[0-9a-f]{6}`)
2. ✅ Alle border-radius nutzen SCSS-Variablen
3. ✅ Button-Overrides entfernt (außer komponentenspezifische Modifiers)
4. ✅ Spacing nutzt rem statt px wo möglich
5. ✅ Keine Lint-Errors
6. ✅ Visuell identisch (keine Breaking Changes)

---

**Notizen:**
- Priorität 1 zuerst (AdminPanel, BackgroundQueueMonitor) - häufig genutzt
- Settings-Panels als Gruppe refactoren (ähnliche Patterns)
- PWA-spezifische Komponenten am Ende (weniger kritisch)
