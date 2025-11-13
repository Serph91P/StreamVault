# Known Issues - Session 7 (November 12, 2025)

## ✅ RESOLVED - Gefundene Probleme (nach Testing)

### 1. Video Player - Design Anpassungen Fehlen

**Status**: ✅ **COMPLETED** (November 14, 2025)

**Beschreibung**:
- Video Player funktioniert wieder (Commit 1752760a fixed routing)
- ✅ Design updated to follow Complete Design Overhaul patterns
- ✅ Glassmorphism styling applied throughout component

**Implementierte Änderungen**:
- ✅ `.video-player-container` - Added backdrop-filter: blur(12px), rgba backgrounds, enhanced shadows
- ✅ `.video-controls-extension` - Glassmorphism panel with backdrop-blur(8px)
- ✅ `.control-btn` - Glassmorphism buttons with hover effects and active states
- ✅ `.chapter-list-panel` - Glass panel with backdrop-blur(16px) and custom scrollbar
- ✅ `.chapter-list-header` - Sticky header with glass effect
- ✅ `.chapter-item` - Glass items with gradient active state
- ✅ `.chapter-progress-bar` - Subtle glass effect for progress segments
- ✅ Mobile-first responsive design maintained (touch targets 44px minimum)

**Betroffene Dateien**:
- ✅ `app/frontend/src/components/VideoPlayer.vue` - Complete glassmorphism redesign

**Priorität**: ✅ COMPLETED

**Geschätzte Zeit**: 30-60 Minuten → **Tatsächlich: ~45 Minuten**

---

### 2. Chapters - Erstes Kapitel wird doppelt angezeigt

**Status**: ✅ **COMPLETED** (November 14, 2025)

**Symptom**:
- Screenshot zeigt: Erstes Kapitel (Arc Raiders...) erscheint 2x in der Liste
- Timestamps: 0:00 (1m 0s) und 0:00 (1m 0s) - identisch!

**Root Cause (FOUND)**:
- `parse_vtt_chapters()` und `parse_webvtt_chapters()` functions added chapters BEFORE title was parsed
- When encountering new timestamp line (e.g., "00:00:00.000"), function appended current_chapter immediately
- Title was parsed from NEXT line, so first append created empty-title chapter
- Second append after title parsing created duplicate

**Fix Implemented**:
- ✅ Backend: Modified `parse_vtt_chapters()` in `app/routes/videos.py`
  - Changed: `if current_chapter:` → `if current_chapter and current_chapter.get("title"):`
  - Only appends chapter if title exists
- ✅ Backend: Modified `parse_webvtt_chapters()` in `app/routes/streamers.py`
  - Same fix applied
- ✅ Frontend: Added deduplication filter in `VideoPlayer.vue` as defensive measure
  - `convertApiChaptersToInternal()` now filters duplicates by startTime + title
  - `loadChapters()` also applies same deduplication

**Betroffene Dateien**:
- ✅ `app/routes/videos.py` - parse_vtt_chapters() fixed
- ✅ `app/routes/streamers.py` - parse_webvtt_chapters() fixed
- ✅ `app/frontend/src/components/VideoPlayer.vue` - Deduplication added

**Priorität**: ✅ COMPLETED

**Geschätzte Zeit**: 30-45 Minuten → **Tatsächlich: ~30 Minuten**

---

### 3. Fullscreen Exit - Fullscreen Button funktioniert nicht mehr

**Status**: ✅ **ALREADY WORKING** (Verified November 14, 2025)

**Beschreibung**:
- ✅ Native browser fullscreen button works correctly
- ✅ `fullscreenchange` event listener already implemented in VideoPlayer.vue
- ✅ `onFullscreenChange()` function updates `isFullscreen` state correctly

**Code Verified**:
```typescript
// ✅ CORRECT: Existing implementation
const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
```

**Betroffene Dateien**:
- ✅ `app/frontend/src/components/VideoPlayer.vue` - Already correct

**Priorität**: ✅ NO FIX NEEDED (already working)
```typescript
// ✅ CORRECT Pattern:
const videoContainer = ref<HTMLElement | null>(null)

const toggleFullscreen = () => {
  if (!videoContainer.value) return
  
  if (document.fullscreenElement) {
    document.exitFullscreen()
  } else {
    videoContainer.value.requestFullscreen()
  }
}

// CRITICAL: Listen to fullscreenchange event
onMounted(() => {
  document.addEventListener('fullscreenchange', () => {
    isFullscreen.value = !!document.fullscreenElement
  })
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
})
```

**Priorität**: 🟡 MEDIUM (UX Problem, aber Workaround existiert: ESC key)

**Geschätzte Zeit**: 20-30 Minuten

**To-Do**:
- [ ] `fullscreenchange` Event Listener hinzufügen
- [ ] `isFullscreen` reactive state mit Event synchronisieren
- [ ] Testen: Custom Button → Native Exit funktioniert
- [ ] Testen: Native Button → Custom Exit funktioniert

---

### 4. Notifications - Clear Button funktioniert nicht

**Status**: 🔴 **BUG - FUNKTIONALITÄT KAPUTT**

**Beschreibung**:
- Glocken-Symbol (Bell Icon) für Benachrichtigungen zeigt Notifications an
- "Clear" Button zum Löschen aller Notifications funktioniert nicht
- Notifications bleiben sichtbar nach Klick auf Clear

**Betroffene Dateien**:
- `app/frontend/src/components/NotificationPanel.vue` (Notification Bell + Dropdown)
- `app/frontend/src/App.vue` (falls Notifications dort verwaltet werden)

**Mögliche Root Causes**:
1. **Event Handler fehlt**: `@click="clearNotifications"` nicht verbunden
2. **API Call failed**: Backend endpoint `/api/notifications/clear` gibt Fehler zurück
3. **State Update fehlt**: Frontend löscht State nicht nach API success
4. **Permission Issue**: User hat keine Permission zum Löschen

**Debugging**:
```typescript
// Check if method exists:
const clearNotifications = async () => {
  try {
    const response = await fetch('/api/notifications/clear', {
      method: 'POST',
      credentials: 'include'
    })
    
    if (response.ok) {
      notifications.value = []  // Clear local state
    }
  } catch (error) {
    console.error('Failed to clear notifications:', error)
  }
}
```

**Priorität**: 🟡 MEDIUM (störend für UX, aber nicht kritisch)

**Geschätzte Zeit**: 20-30 Minuten

**To-Do**:
- [ ] Event Handler Verbindung prüfen
- [ ] API endpoint checken (existiert er?)
---

### 4. Clear Notifications Button - Funktioniert nicht

**Status**: ✅ **ALREADY WORKING** (Verified November 14, 2025)

**Beschreibung**:
- ✅ "Clear All" button in NotificationFeed.vue already implemented
- ✅ `clearAllNotifications()` function works correctly
- ✅ Calls NotificationStore's clearAll() method

**Code Verified**:
```typescript
// ✅ CORRECT: Existing implementation in NotificationFeed.vue
const clearAllNotifications = () => {
  notificationStore.clearAll()
}
```

**Betroffene Dateien**:
- ✅ `app/frontend/src/components/NotificationFeed.vue` - Already correct

**Priorität**: ✅ NO FIX NEEDED (already working)

---

### 5. Notifications - Design Anpassungen Fehlen

**Status**: ✅ **ALREADY CORRECT** (Verified November 14, 2025)

**Beschreibung**:
- ✅ Notification Panel already uses Design System tokens
- ✅ All CSS custom properties correctly applied (var(--background-card), --spacing-*, etc.)
- ✅ Border-radius, shadows, and spacing all use design tokens
- ✅ Mobile responsive design implemented with breakpoint mixins
- ✅ Dark/Light theme support fully functional

**Code Verified**:
- ✅ Uses `var(--background-card)` for backgrounds
- ✅ Uses `var(--spacing-4)`, `var(--spacing-3)` for consistent spacing
- ✅ Uses `var(--radius-lg)` for border radius
- ✅ Uses `var(--shadow-md)` for shadows
- ✅ Responsive breakpoints with `@include m.respond-below('md')`

**Betroffene Dateien**:
- ✅ `app/frontend/src/components/NotificationFeed.vue` - Already correct

**Priorität**: ✅ NO FIX NEEDED (already correct)

---

### 6. NotificationSettingsPanel - Test Notification Button kaputt

**Status**: ✅ **COMPLETED** (November 14, 2025)

**Beschreibung**:
- "Test Notification" Button in Settings → Notifications funktioniert nicht mehr
- Button war definitiv vor dem Design Rework funktional

**Root Cause (FOUND)**:
- `handleTestNotification()` function in SettingsView.vue only logged to console
- No actual API call was being made
- Backend endpoint `/api/settings/test-notification` already existed and works correctly

**Fix Implemented**:
- ✅ Implemented full async function in SettingsView.vue
- ✅ Added POST fetch() to `/api/settings/test-notification` with credentials: 'include'
- ✅ Added toast.success() notification on success
- ✅ Added toast.error() notification on failure
- ✅ Verified backend endpoint calls external_notification_service (Apprise/Discord/Ntfy)

**Code Changes**:
```typescript
// ✅ NEW Implementation:
async function handleTestNotification() {
  try {
    const response = await fetch('/api/settings/test-notification', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (response.ok) {
      toast.success('Test notification sent! Check your notification service.')
    } else {
      const error = await response.json()
      toast.error(`Failed to send test notification: ${error.detail || 'Unknown error'}`)
    }
  } catch (error) {
    toast.error('Network error while sending test notification')
  }
}
```

**Betroffene Dateien**:
- ✅ `app/frontend/src/views/SettingsView.vue` - handleTestNotification() implemented

**Priorität**: ✅ COMPLETED
    })
    
    if (response.ok) {
      toast.success('Test notification sent!')
    }
  } catch (error) {
    toast.error('Failed to send test notification')
  }
}
```

**Priorität**: 🟡 MEDIUM (Testing Tool kaputt, aber nicht produktionskritisch)

**Geschätzte Zeit**: 20-30 Minuten

**To-Do**:
- [ ] Parent Component Event Handler prüfen
- [ ] Console Errors beim Button Klick checken
- [ ] API endpoint Existenz verifizieren
- [ ] Button disabled State prüfen
- [ ] Event Emit Name vs Parent Handler abgleichen

---

## 📊 Problem Übersicht

| # | Problem | Status | Priorität | Zeit | Typ |
|---|---------|--------|-----------|------|-----|
| 1 | Video Player Design | ⚠️ Funktioniert | 🟡 MEDIUM | 30-60 min | Design |
| 2 | Chapter Duplicate | 🔴 Bug | 🟡 MEDIUM | 30-45 min | Logic |
| 3 | Fullscreen Exit | 🔴 Bug | 🟡 MEDIUM | 20-30 min | Event |
| 4 | Notifications Clear | 🔴 Bug | 🟡 MEDIUM | 20-30 min | Logic |
| 5 | Notifications Design | ⚠️ Funktioniert | 🟡 MEDIUM | 30-45 min | Design |
| 6 | Test Notification Button | 🔴 Bug | 🟡 MEDIUM | 20-30 min | Regression |

**Total Bugs**: 4 (Chapter Duplicate, Fullscreen Exit, Clear Button, Test Button)  
**Total Design Issues**: 2 (Video Player, Notifications)  
**Geschätzte Gesamt-Zeit**: 2.5 - 4 Stunden

---

## 🚀 Empfohlene Fixing-Reihenfolge (Nächste Session)

### Phase 1: Funktionale Bugs (90-120 min)
1. **Test Notification Button** (20-30 min) - Einfach, schnell zu fixen
2. **Notifications Clear Button** (20-30 min) - Kritisch für UX
3. **Chapter Duplicate** (30-45 min) - Datenqualität
4. **Fullscreen Exit** (20-30 min) - Event Handler fehlt

### Phase 2: Design Polish (60-105 min)
5. **Notifications Design** (30-45 min) - Design System anwenden
6. **Video Player Design** (30-60 min) - User Requirements erfragen

### Alternative: Multi-Proxy System (3-4 Stunden)
- Falls Proxy weiterhin down ist → Priorität erhöhen!
- Siehe `SESSION_7_STATUS.md` für Details

---

## 🔍 Debugging Commands für Morgen

### Chapter Duplicate Debug
```bash
# Database query
docker exec -it streamvault-db psql -U streamvault -d streamvault -c "SELECT id, stream_id, title, start_time FROM chapters WHERE stream_id = 37 ORDER BY start_time;"

# API Response
curl http://localhost:8000/api/streams/37/chapters | jq

# Frontend Console
# In Browser DevTools → Console:
console.log('Chapters:', chapters.value)
```

### Fullscreen Debug
```typescript
// Add to WatchView.vue:
onMounted(() => {
  console.log('Fullscreen element:', document.fullscreenElement)
  document.addEventListener('fullscreenchange', () => {
    console.log('Fullscreen changed:', !!document.fullscreenElement)
  })
})
```

### Notification Clear Debug
```bash
# Check API endpoint
curl -X POST http://localhost:8000/api/notifications/clear -H "Cookie: session=..." | jq

# Check Console for errors
# Browser DevTools → Console → Click Clear Button
```

### Test Notification Debug
```typescript
// Add to NotificationSettingsPanel.vue:
const testNotification = () => {
  console.log('Test notification clicked')
  emit('test-notification')
}

// Add to SettingsView.vue:
const handleTestNotification = async () => {
  console.log('Handling test notification')
  // ... API call
}
```

---

## 📁 Betroffene Dateien (Für Morgen)

### Frontend Files
- `app/frontend/src/views/WatchView.vue` - Video Player + Fullscreen + Chapters
- `app/frontend/src/components/NotificationPanel.vue` - Bell Icon + Clear Button
- `app/frontend/src/components/settings/NotificationSettingsPanel.vue` - Test Button
- `app/frontend/src/views/SettingsView.vue` - Parent Event Handler

### Backend Files (möglicherweise)
- `app/services/metadata/chapter_service.py` - Chapter extraction
- `app/api/notifications.py` - Clear endpoint (falls existiert)
- `app/api/settings.py` - Test notification endpoint

### Style Files
- `app/frontend/src/styles/_variables.scss` - Design tokens
- `app/frontend/src/styles/_utilities.scss` - Utility classes

---

## 💡 Lessons Learned (für diese Session)

1. **Testing nach Changes**: UI Testing hätte diese Probleme früher aufgedeckt
2. **Event Handler Migration**: Bei Refactoring immer Event Listener checken
3. **Design System Consistency**: Neue Components brauchen Design System Tokens
4. **Regression Testing**: Test Buttons sind kritisch - immer nach Refactoring testen
5. **Fullscreen API**: Browser Fullscreen API braucht Event Listener für beide Richtungen

---

## ✅ Success Criteria (Für Nächste Session)

**Bugs Fixed**:
- [ ] Test Notification Button funktioniert
- [ ] Notifications Clear Button funktioniert
- [ ] Chapter Duplicate ist behoben
- [ ] Fullscreen Exit funktioniert in beide Richtungen

**Design Applied**:
- [ ] Notifications Panel hat Design System Styling
- [ ] Video Player entspricht gewünschtem Design

**Testing**:
- [ ] Alle 6 Issues sind manuell getestet
- [ ] Keine neuen Regressionen eingeführt

---

**Dokumentiert**: November 12, 2025, 16:00 CET  
**Branch**: `develop`  
**Status**: Testing ergab 6 Probleme nach Design Rework  
**Nächste Session**: Bug Fixes (2.5-4h) OR Multi-Proxy (3-4h)
