# Toast vs WebSocket - Best Practices for StreamVault

## TL;DR: Use BOTH (Different Purposes)

**Toast** = UI feedback for **user-initiated actions**  
**WebSocket** = Real-time updates for **server-initiated events**

---

## When to Use Toast Notifications

### ✅ Use Toast For:

1. **Settings Save Confirmation**
   - User clicks "Save" → Immediate visual feedback
   - Example: "Settings saved successfully" (green toast)
   - Example: "Failed to save settings" (red toast)

2. **User Action Results**
   - "Streamer added successfully"
   - "Recording forced"
   - "Proxy deleted"
   - "Test notification sent"

3. **Form Validation Errors**
   - "Invalid proxy URL format"
   - "Username cannot be empty"
   - "Port must be between 1-65535"

4. **Client-Side Operations**
   - "Copied to clipboard"
   - "Filter applied"
   - "Settings reset to defaults"

### Why Toast for User Actions?

- ✅ **Zero server dependency**: Works even if WebSocket disconnected
- ✅ **Immediate feedback**: User clicks → instant visual confirmation
- ✅ **Low overhead**: Pure client-side, no network calls needed
- ✅ **User expectation**: Users expect feedback on button clicks
- ✅ **No state synchronization**: Toast → display → dismiss

---

## When to Use WebSocket Notifications

### ✅ Use WebSocket For:

1. **Recording Failures** (Server Event)
   - Streamlink crashes 5 minutes after start
   - Proxy connection fails mid-recording
   - Out of disk space during recording
   - **Pattern**: Server detects issue → broadcasts to all clients

2. **Stream Status Changes**
   - Streamer went live (EventSub webhook)
   - Streamer went offline
   - Stream title/category changed

3. **Background Task Completion**
   - "Cleanup completed: 50 files deleted"
   - "Segment merge finished"
   - "Metadata extraction completed"

4. **Real-Time Updates**
   - New recording started by another user
   - Settings changed by admin
   - System health status changes

### Why WebSocket for Server Events?

- ✅ **Real-time propagation**: Event → all connected clients instantly
- ✅ **Asynchronous**: Event happens minutes/hours after user action
- ✅ **Multi-device sync**: Desktop + Mobile both get notified
- ✅ **Centralized state**: Server is source of truth
- ✅ **Push notifications**: No polling needed

---

## The Recommended Pattern: WebSocket → Toast

**Best Practice**: WebSocket delivers the event, Toast displays it to user.

### Example 1: Recording Failure

```typescript
// composables/useRecordingStatus.ts
import { useWebSocket } from '@/composables/useWebSocket'
import { useToast } from '@/composables/useToast'

const websocket = useWebSocket()
const toast = useToast()

// WebSocket receives server event
websocket.on('recording_failed', (data) => {
  // Display toast notification to user
  toast.error(`Recording failed: ${data.streamer_name}`)
  
  // Update local state
  updateRecordingStatus(data.recording_id, 'failed')
  
  // BONUS: External notification via Apprise (server-side)
  // User also gets Discord/Telegram/Ntfy notification
})
```

**Flow:**
1. Streamlink crashes (server detects)
2. Server broadcasts WebSocket event: `recording_failed`
3. Frontend receives event → Shows Toast
4. User sees: "❌ Recording failed: xQc"
5. User also gets Apprise notification on phone (if enabled)

### Example 2: Settings Save

```typescript
// composables/useRecordingSettings.ts
import { useToast } from '@/composables/useToast'

const toast = useToast()

async function saveSettings(settings: RecordingSettings) {
  try {
    // Show loading state
    isSaving.value = true
    
    // API call
    const response = await fetch('/api/settings', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    })
    
    if (response.ok) {
      // User action → Toast feedback
      toast.success('Settings saved successfully')
    } else {
      toast.error('Failed to save settings')
    }
  } catch (error) {
    toast.error('Network error: Could not save settings')
  } finally {
    isSaving.value = false
  }
}
```

**Flow:**
1. User clicks "Save Settings"
2. Button shows spinner (loading state)
3. API request completes
4. Toast appears: "✅ Settings saved successfully"
5. Button re-enabled
6. **NO WebSocket needed** - this is a direct user action

---

## Comparison Table

| Aspect | Toast | WebSocket |
|--------|-------|-----------|
| **Trigger** | User clicks button | Server event happens |
| **Timing** | Immediate (0-500ms) | Asynchronous (seconds to hours) |
| **Network** | None (client-side only) | Required (WebSocket connection) |
| **Reliability** | Always works | Depends on connection |
| **Multi-device** | No (local to browser) | Yes (broadcasts to all clients) |
| **Use Case** | Save, delete, copy, reset | Recording fails, stream live, task done |
| **State Sync** | Not needed | Critical (server is source of truth) |
| **Overhead** | Minimal (DOM manipulation) | Medium (WebSocket message) |

---

## StreamVault Implementation Strategy

### Toast Notification System (`useToast.ts`)

```typescript
// app/frontend/src/composables/useToast.ts
export interface Toast {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  duration: number
}

export function useToast() {
  const toasts = ref<Toast[]>([])
  
  function show(message: string, type: ToastType, duration = 3000) {
    const id = crypto.randomUUID()
    toasts.value.push({ id, type, message, duration })
    
    setTimeout(() => {
      remove(id)
    }, duration)
  }
  
  return {
    toasts,
    success: (msg: string) => show(msg, 'success'),
    error: (msg: string) => show(msg, 'error'),
    warning: (msg: string) => show(msg, 'warning'),
    info: (msg: string) => show(msg, 'info')
  }
}
```

### WebSocket Event Handling (`useSystemAndRecordingStatus.ts`)

```typescript
// Listen for server events
websocket.on('recording_failed', (data) => {
  // Show toast
  toast.error(`Recording failed: ${data.streamer_name}`)
  
  // Update state
  recordings.value = recordings.value.map(r => 
    r.id === data.recording_id 
      ? { ...r, status: 'failed', error: data.error_message }
      : r
  )
})

websocket.on('recording_started', (data) => {
  toast.success(`Recording started: ${data.streamer_name}`)
  recordings.value.push(data.recording)
})

websocket.on('recording_completed', (data) => {
  toast.info(`Recording completed: ${data.streamer_name}`)
})
```

### Settings Components Pattern

**All settings panels follow this pattern:**

```vue
<template>
  <div class="settings-panel">
    <button 
      @click="saveSettings" 
      :disabled="isSaving"
      class="btn-primary"
    >
      <span v-if="isSaving">Saving...</span>
      <span v-else>Save Settings</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const isSaving = ref(false)

async function saveSettings() {
  isSaving.value = true
  
  try {
    const response = await fetch('/api/settings', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings.value)
    })
    
    if (response.ok) {
      toast.success('Settings saved successfully')
    } else {
      const error = await response.json()
      toast.error(`Failed to save: ${error.detail}`)
    }
  } catch (error) {
    toast.error('Network error: Could not save settings')
  } finally {
    isSaving.value = false
  }
}
</script>
```

---

## Integration with Apprise (External Notifications)

**The Complete Flow:**

```
Recording Failure
    ↓
Server detects (process_manager.py)
    ↓
Update database (status='failed')
    ↓
Broadcast WebSocket ('recording_failed')
    ↓
Send Apprise notification (if enabled)
    ↓
Frontend receives WebSocket event
    ↓
Display Toast notification
    ↓
User sees: Toast + Discord/Telegram/Ntfy
```

**Why This Works:**
- **Toast**: Immediate visual feedback in browser
- **WebSocket**: Real-time event delivery
- **Apprise**: Persistent notification on phone/desktop app
- **All 3 layers**: Ensures user ALWAYS knows about critical failures

---

## Performance Considerations

### Toast Overhead (Minimal)

```
Toast creation: ~1ms (DOM manipulation)
Toast animation: ~200ms (CSS transitions)
Toast removal: ~1ms (DOM cleanup)
Total overhead: ~2ms per toast
```

**Acceptable load**: Even 100 toasts/minute = 0.2s overhead (negligible)

### WebSocket Overhead (Medium)

```
WebSocket message: ~10-50ms (network latency)
JSON parsing: ~1ms
State update: ~5ms (Vue reactivity)
Total overhead: ~15-60ms per event
```

**Acceptable load**: 10 events/second = 600ms overhead (acceptable)

### When NOT to Use Toast

❌ **Don't use Toast for:**
- High-frequency updates (100+ per minute)
- Data polling results (use live data display instead)
- Background operations user didn't trigger
- Events that need to persist (use notification history)

---

## Decision Flowchart

```
┌──────────────────────────────────┐
│ Event/Action happened            │
└───────────┬──────────────────────┘
            │
            ▼
    ┌───────────────┐
    │ Who triggered │
    │ the event?    │
    └───┬───────────┘
        │
┌───────┴────────┐
│                │
▼                ▼
USER            SERVER
│                │
▼                ▼
Use Toast       Use WebSocket
                    │
                    ▼
            Show Toast too
            (for visibility)
```

**Examples:**
- User clicks "Save" → **Toast only**
- Recording fails → **WebSocket + Toast**
- Stream goes live → **WebSocket + Toast**
- User copies text → **Toast only**
- Background task completes → **WebSocket + Toast**

---

## Conclusion

**The Golden Rule:**
- **User clicks button** → Use Toast (immediate feedback)
- **Server event happens** → Use WebSocket → Display Toast (real-time + visibility)

**The Magic:**
WebSocket delivers the event, Toast shows it to user. Best of both worlds!

**For StreamVault:**
- ✅ Toast for: Save settings, delete streamer, force record confirmation
- ✅ WebSocket for: Recording failures, stream status, background tasks
- ✅ Combined: Recording fails → WebSocket event → Toast display + Apprise notification

**Result:** Users get instant feedback on actions AND real-time notifications on critical events.
