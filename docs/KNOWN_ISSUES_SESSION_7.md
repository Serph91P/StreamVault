# Known Issues - Session 7 (November 12, 2025)

## 🐛 Gefundene Probleme (nach Testing)

### 1. Video Player - Design Anpassungen Fehlen

**Status**: ⚠️ **FUNKTIONIERT, ABER DESIGN FEHLT**

**Beschreibung**:
- Video Player funktioniert wieder (Commit 1752760a fixed routing)
- Design entspricht noch nicht dem gewünschten Look
- Styling/Theme muss angepasst werden

**Betroffene Dateien**:
- `app/frontend/src/views/WatchView.vue` (Video Player View)
- Möglicherweise auch `app/frontend/src/components/VideoPlayer.vue` (falls existiert)

**Priorität**: 🟡 MEDIUM (funktioniert, aber UX/Design nicht ideal)

**Geschätzte Zeit**: 30-60 Minuten (Design System Tokens anwenden)

**To-Do**:
- [ ] Design Requirements vom User erfragen
- [ ] CSS Variablen aus Design System anwenden
- [ ] Responsive Layout checken (mobile vs desktop)
- [ ] Dark/Light Theme Support verifizieren

---

### 2. Chapters - Erstes Kapitel wird doppelt angezeigt

**Status**: 🔴 **BUG - DUPLICATE ENTRY**

**Symptom**:
- Screenshot zeigt: Erstes Kapitel (Arc Raiders...) erscheint 2x in der Liste
- Timestamps: 0:00 (1m 0s) und 0:00 (1m 0s) - identisch!
- Aktuelles Kapitel: 4:57 (korrekt highlighted)

**Screenshot Referenz**: Screen2 (User bereitgestellt)

**Mögliche Root Causes**:
1. **Duplicate Insertion**: Chapter wird beim Erstellen 2x eingefügt
2. **Query Problem**: Database query gibt Chapter 2x zurück
3. **Frontend Rendering**: Vue component rendert Chapter 2x (v-for key issue)

**Betroffene Dateien**:
- Backend: `app/services/metadata/chapter_service.py` (Chapter extraction)
- Backend: `app/api/videos.py` oder ähnlich (Chapter API endpoint)
- Frontend: `app/frontend/src/views/WatchView.vue` (Chapter list rendering)
- Frontend: `app/frontend/src/components/ChapterList.vue` (falls existiert)

**Debugging Steps**:
```bash
# 1. Check database for duplicates
# SQL Query:
SELECT * FROM chapters WHERE stream_id = <stream_id> ORDER BY start_time;

# 2. Check API response
curl http://localhost:8000/api/streams/<stream_id>/chapters

# 3. Check frontend v-for key
# Look for: <div v-for="chapter in chapters" :key="chapter.id">
# Bad: :key="index" (causes duplicates)
# Good: :key="chapter.id" (unique identifier)
```

**Priorität**: 🟡 MEDIUM (funktional störend, aber nicht kritisch)

**Geschätzte Zeit**: 30-45 Minuten

**To-Do**:
- [ ] Database query auf Duplicates prüfen
- [ ] API endpoint response checken
- [ ] Frontend v-for :key Attribut verifizieren
- [ ] Chapter insertion logic reviewen

---

### 3. Fullscreen Exit - Fullscreen Button funktioniert nicht mehr

**Status**: 🔴 **BUG - FUNKTIONALITÄT KAPUTT**

**Beschreibung**:
- Szenario:
  1. User klickt Fullscreen Button (custom Button im Player)
  2. Video geht in Fullscreen
  3. User klickt Verkleinerungs-Button im nativen Video Player
  4. ❌ Video verlässt Fullscreen NICHT!

**Root Cause**:
- Custom Fullscreen Button verwendet wahrscheinlich `element.requestFullscreen()`
- Native Browser Fullscreen Button triggert eigenes Event
- Event Handler für `fullscreenchange` fehlt oder ist nicht korrekt verbunden

**Betroffene Dateien**:
- `app/frontend/src/views/WatchView.vue` (Fullscreen logic)

**Code Pattern (Expected)**:
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
- [ ] State update nach success implementieren
- [ ] Error handling hinzufügen

---

### 5. Notifications - Design Anpassungen Fehlen

**Status**: ⚠️ **FUNKTIONIERT, ABER DESIGN FEHLT**

**Beschreibung**:
- Notification Panel funktioniert
- Design entspricht nicht dem gewünschten Look
- Vermutlich wurden globale Design System Tokens nicht angewendet

**Betroffene Dateien**:
- `app/frontend/src/components/NotificationPanel.vue`
- `app/frontend/src/styles/_variables.scss` (Design tokens)

**Design Checklist**:
- [ ] CSS custom properties verwenden (var(--background-card), etc.)
- [ ] Spacing mit Design System Tokens (var(--spacing-md))
- [ ] Border-radius konsistent (var(--border-radius))
- [ ] Schatten konsistent (var(--shadow-md))
- [ ] Mobile Responsive Design (Breakpoint Mixins)
- [ ] Dark/Light Theme Support

**Priorität**: 🟡 MEDIUM (funktioniert, aber UX nicht ideal)

**Geschätzte Zeit**: 30-45 Minuten

---

### 6. NotificationSettingsPanel - Test Notification Button kaputt

**Status**: 🔴 **BUG - REGRESSION**

**Beschreibung**:
- "Test Notification" Button in Settings → Notifications funktioniert nicht mehr
- Button war definitiv vor dem Design Rework funktional
- Vermutlich während Design System Migration kaputt gegangen

**Betroffene Datei**:
- `app/frontend/src/components/settings/NotificationSettingsPanel.vue`

**Current Code (line ~372)**:
```typescript
const testNotification = () => {
  emit('test-notification')
}
```

**Possible Issues**:
1. **Parent Handler fehlt**: SettingsView.vue fängt Event nicht ab
2. **API endpoint changed**: Backend URL geändert oder deprecated
3. **Event Name mismatch**: Emit Name stimmt nicht mit Parent @handler überein
4. **Button disabled**: CSS oder disabled Attribut blockiert Klick

**Debugging Checklist**:
```typescript
// Check in SettingsView.vue:
<NotificationSettingsPanel
  @test-notification="handleTestNotification"  // ← Existiert das?
  ...
/>

// Check method exists:
const handleTestNotification = async () => {
  try {
    const response = await fetch('/api/settings/test-notification', {
      method: 'POST',
      credentials: 'include'
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
