# Frontend Fixes - To Do List

**Datum:** 10. November 2025  
**Status:** Dokumentation offener UI-Probleme für spätere Bearbeitung

---

## 🔴 KRITISCHE PROBLEME

### 1. Sidebar - Light Mode Active State (NOCH NICHT GEFIXT)
**Problem:** Ausgewählter Menüpunkt ist weiß auf weiß und unsichtbar

**Betroffene Datei:** `app/frontend/src/components/navigation/SidebarNav.vue`

**Aktueller Zustand:**
- Active state hat weiße Schrift auf weißem Hintergrund (light mode)
- Nutzer sieht nicht welcher Menüpunkt aktiv ist

**Fix benötigt:**
```scss
// In SidebarNav.vue <style scoped>

.sidebar-item.active {
  background: var(--accent-color);
  color: white;
  border-left: 4px solid var(--accent-secondary);
  
  // CRITICAL: Light mode override
  [data-theme="light"] & {
    background: var(--accent-color);  // z.B. #14b8a6 (teal)
    color: white;  // NICHT var(--text-primary)!
    border-left-color: var(--accent-secondary);
  }
}
```

**Testing:**
- [ ] Dark mode: Active item hat sichtbaren Hintergrund
- [ ] Light mode: Active item NICHT weiß auf weiß
- [ ] Kontrast mindestens WCAG AA (4.5:1)

---

## 🟡 LAYOUT PROBLEME

### 2. Streamübersicht Grid - Card Layout Broken
**Problem:** Streamer Cards passen nicht ins Grid, Buttons und Titel überlappen

**Betroffene Datei:** `app/frontend/src/views/StreamersView.vue`

**Screenshot-Beschreibung (Screen 1):**
- Grid-Ansicht: Cards haben verschiedene Höhen
- Streamer-Titel läuft über mehrere Zeilen
- Buttons (3-Punkt-Menü) überlagern Text
- Category-Name und Titel versetzt

**Fix benötigt:**

#### A. Card Grid Layout
```vue
<!-- StreamersView.vue -->
<div class="streamers-grid">
  <StreamerCard
    v-for="streamer in filteredStreamers"
    :key="streamer.id"
    :streamer="streamer"
  />
</div>

<style scoped>
.streamers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
  padding: 1rem;
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr;  // Single column on mobile
  }
}
</style>
```

#### B. StreamerCard Fixed Height
```vue
<!-- StreamerCard.vue -->
<template>
  <div class="streamer-card">
    <div class="card-header">
      <img :src="streamer.profile_image_url" class="profile-image" />
      <div class="header-info">
        <h3 class="streamer-name">{{ streamer.display_name }}</h3>
        <span class="live-badge" v-if="streamer.is_live">LIVE</span>
      </div>
      <button class="btn-more" @click.stop="toggleActions">⋮</button>
    </div>
    
    <div class="card-body">
      <!-- CRITICAL: Limit title to 2 lines with ellipsis -->
      <p class="stream-title" :title="streamer.title">
        {{ truncateTitle(streamer.title, 60) }}
      </p>
      
      <p class="category-name">{{ streamer.category_name }}</p>
      
      <div class="viewer-count" v-if="streamer.is_live">
        {{ streamer.viewer_count }} viewers
      </div>
    </div>
    
    <div class="card-footer">
      <button v-if="streamer.is_live" @click="watchLive">Watch</button>
      <span class="vod-count" v-else>{{ streamer.vods_count }} VODs</span>
    </div>
  </div>
</template>

<style scoped>
.streamer-card {
  display: flex;
  flex-direction: column;
  height: 100%;  // CRITICAL: Fill grid cell
  min-height: 320px;  // Consistent card height
  max-height: 400px;
  background: var(--bg-secondary);
  border-radius: 8px;
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.header-info {
  flex: 1;
  min-width: 0;  // Allow text truncation
}

.streamer-name {
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-more {
  flex-shrink: 0;  // Don't shrink button
  width: 32px;
  height: 32px;
  border-radius: 4px;
  background: transparent;
  
  &:hover {
    background: var(--bg-hover);
  }
}

.card-body {
  flex: 1;  // Take remaining space
  padding: 16px;
  overflow: hidden;  // Prevent content overflow
}

.stream-title {
  font-size: 0.95rem;
  margin: 0 0 8px 0;
  
  // CRITICAL: Limit to 2 lines
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
  max-height: 2.8em;  // 2 lines * 1.4 line-height
}

.category-name {
  font-size: 0.9rem;
  color: var(--text-secondary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
```

**Testing:**
- [ ] Grid: Alle Cards haben gleiche Höhe
- [ ] Titel bricht nach 2 Zeilen mit ...
- [ ] Buttons überlappen nichts
- [ ] Responsive: 1 Spalte auf Mobile

---

### 3. Listen-Ansicht - Titel und Kategorie versetzt
**Problem:** In der Listen-Ansicht sind Titel und Kategorie nicht auf gleicher Höhe

**Betroffene Datei:** `app/frontend/src/views/StreamersView.vue` (Listen-Modus)

**Screenshot-Beschreibung (Screen 2):**
- Titel und Kategorie nicht vertikal aligned
- Spacing zwischen Elementen inkonsistent

**Fix benötigt:**
```vue
<!-- StreamersView.vue - List Mode -->
<div class="streamers-list">
  <div class="streamer-row" v-for="streamer in filteredStreamers" :key="streamer.id">
    <div class="row-left">
      <img :src="streamer.profile_image_url" class="profile-image-small" />
      <div class="streamer-info">
        <h3 class="streamer-name">{{ streamer.display_name }}</h3>
        <span class="live-badge" v-if="streamer.is_live">LIVE</span>
      </div>
    </div>
    
    <div class="row-center">
      <p class="stream-title">{{ streamer.title }}</p>
      <p class="category-name">{{ streamer.category_name }}</p>
    </div>
    
    <div class="row-right">
      <button class="btn-more" @click.stop="toggleActions">⋮</button>
    </div>
  </div>
</div>

<style scoped>
.streamer-row {
  display: flex;
  align-items: center;  // CRITICAL: Vertical center alignment
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  
  &:hover {
    background: var(--bg-hover);
  }
}

.row-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
}

.row-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;  // CRITICAL: Consistent spacing
  justify-content: center;  // Vertical center
}

.stream-title {
  margin: 0;
  font-size: 1rem;
  line-height: 1.4;
}

.category-name {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.row-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
```

**Testing:**
- [ ] Titel und Kategorie vertikal zentriert
- [ ] Spacing konsistent zwischen Rows
- [ ] Hover-Effekt funktioniert

---

## 🔵 DROPDOWN MENU PROBLEME

### 4. Actions Dropdown zu groß
**Problem:** Edit-Menü (3-Punkt-Menü) nimmt zu viel Platz ein

**Betroffene Datei:** `app/frontend/src/components/cards/StreamerCard.vue`

**Screenshot-Beschreibung (Screen 3):**
- Dropdown ist sehr breit
- Buttons haben zu viel Padding
- Menü sieht "aufgebläht" aus

**Aktueller Code (zu groß):**
```scss
// PROBLEM: Zu viel Padding und Breite
.actions-dropdown {
  padding: 16px;  // ZU GROSS
  min-width: 200px;  // ZU BREIT
}

.actions-dropdown button {
  padding: 12px 16px;  // ZU GROSS
  font-size: 1rem;
}
```

**Fix benötigt:**
```vue
<!-- StreamerCard.vue -->
<Teleport to="body">
  <div
    v-if="showActions"
    class="actions-dropdown"
    :style="dropdownStyle"
    @click.stop
  >
    <button @click="handleWatch" v-if="streamer.is_live">
      Watch Live
    </button>
    <button @click="handleForceRecord">
      Force Record
    </button>
    <button @click="handleViewDetails">
      View Details
    </button>
    <button @click="handleDelete" class="action-danger">
      Delete Streamer
    </button>
  </div>
</Teleport>

<style scoped>
.actions-dropdown {
  position: fixed;  // Teleport to body
  z-index: 1000;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  
  // CRITICAL: Compact sizing
  min-width: 140px;  // Reduced from 200px
  max-width: 180px;
  padding: 4px;  // Reduced from 16px
  
  button {
    display: block;
    width: 100%;
    text-align: left;
    padding: 8px 12px;  // Reduced from 12px 16px
    font-size: 0.9rem;  // Reduced from 1rem
    border: none;
    background: none;
    cursor: pointer;
    border-radius: 4px;
    transition: background 0.15s;
    
    &:hover {
      background: var(--bg-hover);
    }
    
    &.action-danger {
      color: var(--danger-color);
      
      &:hover {
        background: rgba(239, 68, 68, 0.1);
      }
    }
  }
}
</style>
```

**Testing:**
- [ ] Dropdown ist kompakt (max 180px breit)
- [ ] Buttons haben angemessenes Padding
- [ ] Hover-Effekt funktioniert
- [ ] Danger-Button (Delete) ist rot

---

### 5. Dropdown Position Calculation
**Problem:** Dropdown wird immer an fester Position angezeigt, nicht relativ zum Button

**Betroffene Datei:** `app/frontend/src/components/cards/StreamerCard.vue`

**Aktueller Code (Placeholder):**
```typescript
const dropdownStyle = computed(() => {
  // TODO: Calculate actual button position
  return {
    top: '0px',
    left: '0px'
  }
})
```

**Fix benötigt:**
```vue
<script setup lang="ts">
import { ref, computed } from 'vue'

const showActions = ref(false)
const moreButtonRef = ref<HTMLButtonElement | null>(null)

const dropdownStyle = computed(() => {
  if (!moreButtonRef.value) {
    return { top: '0px', left: '0px' }
  }
  
  const rect = moreButtonRef.value.getBoundingClientRect()
  
  // Position dropdown below and to the right of button
  return {
    top: `${rect.bottom + 4}px`,
    left: `${rect.left}px`
  }
})

const toggleActions = () => {
  showActions.value = !showActions.value
}

// Close dropdown when clicking outside
const handleClickOutside = (event: MouseEvent) => {
  if (showActions.value && moreButtonRef.value) {
    const dropdown = document.querySelector('.actions-dropdown')
    if (dropdown && !dropdown.contains(event.target as Node) &&
        !moreButtonRef.value.contains(event.target as Node)) {
      showActions.value = false
    }
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <button
    ref="moreButtonRef"
    class="btn-more"
    @click.stop="toggleActions"
  >
    ⋮
  </button>
</template>
```

**Testing:**
- [ ] Dropdown erscheint direkt unter dem Button
- [ ] Click outside schließt Dropdown
- [ ] Position passt sich an Scroll an
- [ ] Funktioniert auf Mobile

---

## 🔴 NAVIGATION PROBLEME

### 6. View Details → Leere Seite (KRITISCH)
**Problem:** "View Details" im Dropdown führt zu leerer Seite

**Betroffene Dateien:**
- `app/frontend/src/components/cards/StreamerCard.vue` (Dropdown)
- `app/frontend/src/views/StreamerDetailView.vue` (Zielseite)

**Symptome:**
- Klick auf "View Details" → Navigation funktioniert
- Seite lädt aber bleibt leer
- URL ändert sich zu `/streamers/:id`
- Console zeigt evtl. "Streamer Not Found" Error

**Mögliche Root Causes:**

#### A. Router Parameter Problem
```typescript
// StreamerCard.vue
const handleViewDetails = () => {
  showActions.value = false
  
  // PROBLEM: Verwendet evtl. falsches ID-Format
  router.push(`/streamers/${props.streamer.id}`)
  
  // CHECK: Muss ID ein Number oder String sein?
  // CHECK: Muss es twitch_id statt id sein?
}
```

**Fix benötigt:**
```typescript
// StreamerCard.vue
const handleViewDetails = () => {
  showActions.value = false
  
  // CRITICAL: Use correct ID field
  const streamerId = props.streamer.id  // or props.streamer.twitch_id?
  
  console.log('Navigate to streamer detail:', {
    id: streamerId,
    type: typeof streamerId,
    streamer: props.streamer
  })
  
  router.push({
    name: 'streamer-detail',
    params: { id: String(streamerId) }  // Ensure string
  })
}
```

#### B. Backend API Response Problem
```typescript
// StreamerDetailView.vue
async function fetchStreamer() {
  try {
    const response = await fetch(`/api/streamers/${route.params.id}`, {
      credentials: 'include'  // CRITICAL: Must send session cookie
    })
    
    console.log('Streamer detail response:', {
      status: response.status,
      ok: response.ok,
      id: route.params.id,
      idType: typeof route.params.id
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('Failed to fetch streamer:', {
        status: response.status,
        error: errorText
      })
      error.value = `Failed to load streamer (${response.status})`
      return
    }
    
    const data = await response.json()
    console.log('Streamer data:', data)
    
    streamer.value = data
  } catch (err) {
    console.error('Error fetching streamer:', err)
    error.value = 'Network error'
  }
}
```

#### C. Fehlende Daten in Response
**Backend Check:** `app/routes/streamers.py`

```python
@router.get("/streamers/{streamer_id}")
async def get_streamer(streamer_id: str, db: Session = Depends(get_db)):
    """Get detailed streamer info"""
    
    # CRITICAL: Check if streamer exists
    streamer = db.query(Streamer).filter(
        Streamer.id == int(streamer_id)
    ).first()
    
    if not streamer:
        logger.error(f"Streamer not found: {streamer_id}")
        raise HTTPException(status_code=404, detail="Streamer not found")
    
    # CRITICAL: Return ALL required fields
    return {
        "id": streamer.id,
        "twitch_id": streamer.twitch_id,
        "username": streamer.username,
        "display_name": streamer.username,  # Frontend needs this!
        "is_live": streamer.is_live,
        "is_recording": streamer.is_recording,  # Property!
        "recording_enabled": streamer.recording_enabled,  # Property!
        "title": streamer.title,
        "category_name": streamer.category_name,
        "profile_image_url": streamer.profile_image_url,
        "viewer_count": streamer.viewer_count if streamer.is_live else None,
        # ... all other fields
    }
```

**Testing Checklist:**
- [ ] Console logging zeigt korrekte ID
- [ ] Backend returns 200 (not 404)
- [ ] Response enthält alle benötigten Felder
- [ ] Frontend rendert Streamer-Daten
- [ ] Keine "Streamer Not Found" Errors

---

## 📋 IMPLEMENTIERUNGS-REIHENFOLGE

**Empfohlene Reihenfolge:**

1. **KRITISCH:** Sidebar Light Mode Fix (1-2 Minuten)
2. **KRITISCH:** View Details Navigation Fix (10-15 Minuten)
3. **WICHTIG:** Dropdown Size Fix (5 Minuten)
4. **WICHTIG:** Grid Layout Fix (15-20 Minuten)
5. **WICHTIG:** Listen-Ansicht Alignment Fix (10 Minuten)
6. **NICE-TO-HAVE:** Dropdown Position Calculation (15 Minuten)

**Geschätzte Gesamtzeit:** 60-75 Minuten

---

## 🧪 TESTING CHECKLIST

Nach jedem Fix testen:

### Light Mode
- [ ] Sidebar active state sichtbar
- [ ] Alle Texte lesbar
- [ ] Kontrast ausreichend

### Dark Mode  
- [ ] Alle Fixes funktionieren auch in Dark Mode
- [ ] Keine Regressions

### Responsive
- [ ] Mobile (< 768px): Single column, alles lesbar
- [ ] Tablet (768px - 1024px): 2-3 Spalten
- [ ] Desktop (> 1024px): Auto-fill Grid

### Navigation
- [ ] View Details öffnet korrekte Seite
- [ ] Keine leeren Seiten
- [ ] Back-Button funktioniert

### Dropdown
- [ ] Öffnet an korrekter Position
- [ ] Schließt bei Click außerhalb
- [ ] Alle Actions funktionieren
- [ ] Delete zeigt Confirmation Dialog

---

## 📝 NOTIZEN

**Bekannte Probleme aus vorherigen Sessions:**
- ✅ Streamer.is_recording Property implementiert (committed)
- ✅ Notification Profile Images fixed (committed)
- ✅ Backend Architecture dokumentiert (committed)
- ❌ Frontend Grid Layout NICHT implementiert
- ❌ Sidebar Light Mode NICHT gefixt
- ❌ View Details Navigation BROKEN

**Next Steps:**
1. Dieses Dokument als Arbeitsgrundlage nutzen
2. Fixes Schritt für Schritt implementieren
3. Nach jedem Fix committen mit aussagekräftiger Message
4. Testing Checklist abarbeiten
5. Dokumentation updaten wenn fertig

---

**Erstellt:** 10. November 2025  
**Letzte Aktualisierung:** 10. November 2025  
**Status:** Bereit zur Implementierung
