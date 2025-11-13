# Fix Startup ImportError & Fullscreen Toggle Bug

## 🔴 Priority: CRITICAL
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 45-60 minutes  
**Sprint:** Sprint 1 (Hotfix)  
**Impact:** HIGH - Application startup failure + Player UX broken

---

## 📝 Overview

Two critical bugs discovered during production testing (November 13, 2025):

1. **Startup ImportError (CRITICAL)** - Application fails to cleanup zombie recordings on startup
2. **Fullscreen Toggle Bug (HIGH)** - Video player fullscreen button only works one-way

**Discovered During:**
- Production startup logs analysis
- User testing of video player after Issue #1 fixes

**Current Status:**
- ❌ **Bug 1:** ImportError - `event_handler_registry` not found (blocks zombie cleanup)
- ❌ **Bug 2:** Fullscreen toggle - Button only enters fullscreen, cannot exit (only ESC works)

**Session Context:**
- Recent EventSub/Recording system refactoring
- VideoPlayer glassmorphism redesign (Issue #1)
- Zombie recording cleanup mechanism added

---

## 🔍 Detailed Bug Analysis

### Bug 1: ImportError - event_handler_registry (CRITICAL)

**Priority:** 🔴 CRITICAL  
**Status:** 🔴 NOT STARTED  
**File:** `app/services/init/startup_init.py` (line 242)  
**Related:** `app/events/handler_registry.py`

#### Problem Description

Application startup fails during zombie recording cleanup:

```
2025-11-13 09:42:40,664 - streamvault - INFO - 🧹 Cleaning up zombie recordings from database with smart recovery...
2025-11-13 09:42:40,664 - streamvault - ERROR - ❌ Failed to cleanup zombie recordings: cannot import name 'event_handler_registry' from 'app.events.handler_registry' (/app/app/events/handler_registry.py)
Traceback (most recent call last):
  File "/app/app/services/init/startup_init.py", line 242, in cleanup_zombie_recordings
    from app.events.handler_registry import event_handler_registry
ImportError: cannot import name 'event_handler_registry' from 'app.events.handler_registry' (/app/app/events/handler_registry.py)
```

**Impact:**
- ✅ Application still starts (error is caught)
- ❌ Zombie recordings are NOT cleaned up
- ❌ Orphaned recordings persist in "recording" state
- ❌ Database integrity compromised (stale status)
- ❌ Future recordings may be blocked by "already recording" checks

**When This Occurs:**
- Every application startup
- After container restart
- After crash recovery

#### Root Cause Analysis

**The Problem:**
```python
# ❌ WRONG: startup_init.py line 242
from app.events.handler_registry import event_handler_registry
```

**Why It Fails:**
```python
# app/events/handler_registry.py
class EventHandlerRegistry:  # ← Class definition
    def __init__(self, connection_manager: ConnectionManager, settings=None):
        # ...

# NO MODULE-LEVEL INSTANCE EXPORTED!
# There is no:
# event_handler_registry = EventHandlerRegistry(...)
```

**The Fix Needed:**

**Option 1: Create Singleton Instance** (Recommended)
```python
# app/events/handler_registry.py (at bottom of file)

# Singleton instance for global access
_event_handler_registry = None

def get_event_handler_registry(connection_manager: ConnectionManager = None, settings=None):
    """Get or create singleton EventHandlerRegistry instance"""
    global _event_handler_registry
    if _event_handler_registry is None:
        if connection_manager is None:
            raise ValueError("ConnectionManager required for first initialization")
        _event_handler_registry = EventHandlerRegistry(connection_manager, settings)
    return _event_handler_registry

# Backward compatibility alias
event_handler_registry = get_event_handler_registry
```

**Option 2: Don't Pass Registry to StreamerService** (Quick Fix)
```python
# app/services/init/startup_init.py line 242
# ❌ BEFORE:
from app.events.handler_registry import event_handler_registry
streamer_service = StreamerService(db, websocket_manager, event_handler_registry)

# ✅ AFTER (pass None if optional):
streamer_service = StreamerService(db, websocket_manager, event_registry=None)
```

**Option 3: Import Class and Create Instance** (Verbose)
```python
# app/services/init/startup_init.py line 242
from app.events.handler_registry import EventHandlerRegistry
registry = EventHandlerRegistry(websocket_manager)
streamer_service = StreamerService(db, websocket_manager, registry)
```

#### Recommended Solution

**Use Option 2 (Quick Fix) + Option 1 (Long-term)**

**Phase 1: Immediate Fix (5 min)**
```python
# app/services/init/startup_init.py line 242
# Remove event_handler_registry dependency from zombie cleanup
streamer_service = StreamerService(db, websocket_manager, event_registry=None)
```

**Phase 2: Singleton Pattern (15 min)**
```python
# app/events/handler_registry.py (add at end of file)
_registry_instance = None

def get_event_handler_registry(connection_manager=None, settings=None):
    """Get singleton EventHandlerRegistry instance"""
    global _registry_instance
    if _registry_instance is None:
        from app.services.communication.websocket_manager import websocket_manager as default_manager
        _registry_instance = EventHandlerRegistry(
            connection_manager or default_manager, 
            settings
        )
    return _registry_instance

# Backward compatibility
event_handler_registry = get_event_handler_registry()
```

#### Verification Steps

**1. Check Import Works:**
```python
# Test in Python REPL or startup
from app.events.handler_registry import event_handler_registry
print(f"Registry: {event_handler_registry}")  # Should not raise ImportError
```

**2. Test Zombie Cleanup:**
```bash
# Restart application
docker-compose restart streamvault

# Check logs for success
docker logs streamvault-app | grep "Cleaning up zombie"
# Should show: "✅ No zombie recordings found" or "✅ Cleaned X zombie recordings"
# Should NOT show: "❌ Failed to cleanup zombie recordings: ImportError"
```

**3. Create Zombie Recording (Test):**
```sql
-- Manually create zombie recording
UPDATE recordings SET status = 'recording' WHERE id = 42;

-- Restart application
-- docker-compose restart streamvault

-- Check if cleaned up
SELECT id, status FROM recordings WHERE id = 42;
-- Should show status = 'stopped' or 'failed'
```

#### Files to Modify

**Quick Fix (Option 2):**
- ✅ `app/services/init/startup_init.py` - Remove `event_handler_registry` import and usage

**Complete Fix (Option 1 + 2):**
- ✅ `app/events/handler_registry.py` - Add singleton getter function
- ✅ `app/services/init/startup_init.py` - Use singleton getter
- ✅ All other files importing `event_handler_registry` (search codebase)

#### Testing Checklist

- [ ] Application starts without ImportError
- [ ] Zombie cleanup logs show success: "🧹 Cleaning up zombie recordings..."
- [ ] Manually created zombie recording is cleaned up on restart
- [ ] No regressions in EventSub functionality
- [ ] No regressions in recording start/stop
- [ ] Singleton pattern works across multiple imports

---

### Bug 2: Fullscreen Toggle Button (HIGH)

**Priority:** 🟡 HIGH  
**Status:** 🔴 NOT STARTED  
**File:** `app/frontend/src/components/VideoPlayer.vue` (line ~850-900)  
**Related:** Issue #1 Bug #3 (incorrectly marked as "Already Working")

#### Problem Description

**User Report:**
> "Wenn ich über den Fullscreen button also nicht am player darunter, drücke wird der player fullscreeen. Aber ich kann den player nur mit ESC verkleinern, über den Fullscreen button am player also die controls kann ich ihn nicht verkleinern."

**Translation:**
- User clicks fullscreen button → Player enters fullscreen ✅
- User clicks fullscreen button again → **Nothing happens** ❌
- Only ESC key can exit fullscreen ✅

**Expected Behavior:**
- Click fullscreen button → Enter fullscreen
- Click fullscreen button again → Exit fullscreen
- ESC key → Exit fullscreen (standard browser behavior)

**Current Behavior:**
- Click fullscreen button → Enter fullscreen ✅
- Click fullscreen button again → **Button does nothing** ❌
- ESC key → Exit fullscreen ✅ (but button doesn't update state)

#### Root Cause Analysis

**Issue #1 Bug #3 Assessment Was Incorrect:**

In Issue #1, we verified that `fullscreenchange` event listener exists:

```typescript
// ✅ Event listener EXISTS
onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange)
  document.addEventListener('mozfullscreenchange', onFullscreenChange)
  document.addEventListener('MSFullscreenChange', onFullscreenChange)
})
```

**But we MISSED the button logic:**

```typescript
// ❌ SUSPECTED BUG: toggleFullscreen() function
const toggleFullscreen = () => {
  if (!videoWrapper.value) return
  
  if (document.fullscreenElement) {
    document.exitFullscreen()  // ← This line may not work!
  } else {
    videoWrapper.value.requestFullscreen()  // ← This works
  }
}
```

**Possible Root Causes:**

**1. `videoWrapper` Ref is Wrong Element**
```typescript
// If videoWrapper.value !== document.fullscreenElement
if (document.fullscreenElement) {
  document.exitFullscreen()  // This condition is TRUE
  // But button is clicking on WRONG element
}
```

**2. Click Event Not Reaching Handler**
```vue
<!-- Button might be disabled or click blocked -->
<button @click="toggleFullscreen" :disabled="someCondition">
  {{ isFullscreen ? 'Exit Fullscreen' : 'Fullscreen' }}
</button>
```

**3. Event Handler Not Updating State Fast Enough**
```typescript
// Race condition: Button click → exitFullscreen() → But isFullscreen still true
const toggleFullscreen = () => {
  if (document.fullscreenElement) {
    document.exitFullscreen()  // Async operation!
    // isFullscreen.value is only updated when fullscreenchange fires
    // If button is clicked again before event fires, condition is still true
  }
}
```

#### Debugging Steps

**Step 1: Console Logging**
```typescript
const toggleFullscreen = () => {
  console.log('🔍 toggleFullscreen called')
  console.log('🔍 videoWrapper.value:', videoWrapper.value)
  console.log('🔍 document.fullscreenElement:', document.fullscreenElement)
  console.log('🔍 isFullscreen.value:', isFullscreen.value)
  
  if (!videoWrapper.value) {
    console.error('❌ videoWrapper is null!')
    return
  }
  
  if (document.fullscreenElement) {
    console.log('✅ Exiting fullscreen...')
    document.exitFullscreen()
  } else {
    console.log('✅ Entering fullscreen...')
    videoWrapper.value.requestFullscreen()
  }
}

const onFullscreenChange = () => {
  console.log('🔍 fullscreenchange event fired')
  console.log('🔍 document.fullscreenElement:', document.fullscreenElement)
  isFullscreen.value = !!document.fullscreenElement
  console.log('🔍 isFullscreen updated to:', isFullscreen.value)
}
```

**Step 2: Button State Verification**
```vue
<button 
  @click="toggleFullscreen"
  @click.prevent="console.log('Button clicked!')"
  :disabled="false"
  class="control-btn"
>
  {{ isFullscreen ? '🪟 Exit Fullscreen' : '⛶ Fullscreen' }}
  <!-- Debug: Show state -->
  ({{ isFullscreen ? 'TRUE' : 'FALSE' }})
</button>
```

**Step 3: Element Reference Check**
```typescript
// Verify videoWrapper points to correct element
onMounted(() => {
  console.log('🔍 videoWrapper.value:', videoWrapper.value)
  console.log('🔍 videoWrapper tagName:', videoWrapper.value?.tagName)
  // Should be DIV (video-player-container) or VIDEO element
})
```

#### Likely Fix

**Option 1: Use Correct Element Reference**
```typescript
// Ensure videoWrapper is the element that will be fullscreen
const videoWrapper = ref<HTMLDivElement | null>(null)

// In template:
<div ref="videoWrapper" class="video-player-container">
  <!-- Video and controls -->
</div>
```

**Option 2: Fix Race Condition with Debounce**
```typescript
let toggleInProgress = false

const toggleFullscreen = async () => {
  if (toggleInProgress) {
    console.log('⏳ Toggle already in progress, ignoring click')
    return
  }
  
  if (!videoWrapper.value) return
  
  toggleInProgress = true
  
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else {
      await videoWrapper.value.requestFullscreen()
    }
  } catch (error) {
    console.error('Fullscreen toggle error:', error)
  } finally {
    // Wait for fullscreenchange event
    await new Promise(resolve => setTimeout(resolve, 100))
    toggleInProgress = false
  }
}
```

**Option 3: Manual State Toggle (Immediate Feedback)**
```typescript
const toggleFullscreen = () => {
  if (!videoWrapper.value) return
  
  if (document.fullscreenElement) {
    // Immediately update state (optimistic update)
    isFullscreen.value = false
    document.exitFullscreen()
  } else {
    isFullscreen.value = true
    videoWrapper.value.requestFullscreen()
  }
}

// fullscreenchange event will correct state if needed
const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}
```

#### Recommended Solution

**Use Option 1 (Element Fix) + Option 3 (Optimistic Update)**

```typescript
// 1. Ensure correct ref
const videoWrapper = ref<HTMLDivElement | null>(null)

// 2. Optimistic state update
const toggleFullscreen = () => {
  console.log('🔍 TOGGLE_FULLSCREEN:', {
    hasWrapper: !!videoWrapper.value,
    currentElement: document.fullscreenElement,
    currentState: isFullscreen.value
  })
  
  if (!videoWrapper.value) {
    console.error('❌ videoWrapper.value is null!')
    return
  }
  
  if (document.fullscreenElement) {
    // Exiting fullscreen
    console.log('✅ Exiting fullscreen via button')
    isFullscreen.value = false  // Optimistic update
    document.exitFullscreen().catch(err => {
      console.error('Failed to exit fullscreen:', err)
      isFullscreen.value = true  // Revert on error
    })
  } else {
    // Entering fullscreen
    console.log('✅ Entering fullscreen via button')
    isFullscreen.value = true  // Optimistic update
    videoWrapper.value.requestFullscreen().catch(err => {
      console.error('Failed to enter fullscreen:', err)
      isFullscreen.value = false  // Revert on error
    })
  }
}

// 3. Event listener corrects state if needed
const onFullscreenChange = () => {
  const newState = !!document.fullscreenElement
  console.log('🔍 FULLSCREEN_CHANGE:', {
    from: isFullscreen.value,
    to: newState
  })
  isFullscreen.value = newState
}
```

#### Verification Steps

**Manual Testing:**
1. Open video player
2. Click "⛶ Fullscreen" button
3. ✅ Player enters fullscreen
4. ✅ Button text changes to "🪟 Exit Fullscreen"
5. Click "🪟 Exit Fullscreen" button
6. ✅ Player exits fullscreen
7. ✅ Button text changes back to "⛶ Fullscreen"
8. Repeat cycle 3 times → All work correctly

**Console Testing:**
```javascript
// Open browser DevTools → Console
// Watch for logs:
// ✅ "🔍 TOGGLE_FULLSCREEN: { hasWrapper: true, ... }"
// ✅ "✅ Entering fullscreen via button"
// ✅ "🔍 FULLSCREEN_CHANGE: { from: false, to: true }"
// ✅ "✅ Exiting fullscreen via button"
// ✅ "🔍 FULLSCREEN_CHANGE: { from: true, to: false }"
```

**ESC Key Testing:**
1. Enter fullscreen via button
2. Press ESC key
3. ✅ Player exits fullscreen
4. ✅ Button text updates to "⛶ Fullscreen"
5. ✅ Console shows: "🔍 FULLSCREEN_CHANGE: { from: true, to: false }"

#### Files to Modify

- ✅ `app/frontend/src/components/VideoPlayer.vue` - Fix `toggleFullscreen()` function

#### Testing Checklist

- [ ] Click fullscreen button → Enters fullscreen
- [ ] Click fullscreen button again → Exits fullscreen
- [ ] Button text toggles correctly
- [ ] ESC key exits fullscreen
- [ ] Button updates after ESC key
- [ ] No console errors
- [ ] Works in Chrome, Firefox, Safari
- [ ] Works on mobile (if fullscreen supported)
- [ ] No race conditions (rapid clicking)
- [ ] State synchronized with actual fullscreen state

---

## 📊 Summary - Both Bugs

| # | Bug | Priority | Status | Time | Impact |
|---|-----|----------|--------|------|--------|
| 1 | ImportError - event_handler_registry | 🔴 CRITICAL | 🔴 NOT STARTED | 20min | Zombie cleanup fails |
| 2 | Fullscreen Toggle Button | 🟡 HIGH | 🔴 NOT STARTED | 25min | UX broken |

**Total Estimated Time:** 45 minutes  
**Priority:** CRITICAL (Bug #1 blocks production reliability)  
**Sprint:** Sprint 1 Hotfix (fix before next deployment)

---

## 📂 Files to Modify

### Bug 1: ImportError
**Quick Fix:**
- ✅ `app/services/init/startup_init.py` (line 242) - Remove `event_handler_registry` import

**Complete Fix:**
- ✅ `app/events/handler_registry.py` - Add singleton getter
- ✅ `app/services/init/startup_init.py` - Use singleton getter
- ✅ Search for all `from app.events.handler_registry import event_handler_registry` usages

### Bug 2: Fullscreen Toggle
- ✅ `app/frontend/src/components/VideoPlayer.vue` - Fix `toggleFullscreen()` function

---

## ✅ Acceptance Criteria

### Bug 1: ImportError
- [ ] Application starts without ImportError
- [ ] Zombie cleanup runs successfully on startup
- [ ] Logs show: "🧹 Cleaning up zombie recordings..." → "✅ No zombie recordings found"
- [ ] Manually created zombie recording is cleaned up on restart
- [ ] No regressions in EventSub functionality

### Bug 2: Fullscreen Toggle
- [ ] Click fullscreen button → Player enters fullscreen
- [ ] Click fullscreen button again → Player exits fullscreen
- [ ] Button text toggles: "⛶ Fullscreen" ↔ "🪟 Exit Fullscreen"
- [ ] ESC key exits fullscreen
- [ ] Button state updates after ESC key
- [ ] No console errors
- [ ] Works in Chrome, Firefox, Safari
- [ ] No race conditions with rapid clicking

### General
- [ ] No console errors in browser DevTools
- [ ] No startup errors in Docker logs
- [ ] No regressions in recording functionality
- [ ] No regressions in video player
- [ ] All changes follow coding standards

---

## 🧪 Testing Checklist

### Bug 1: ImportError Testing

**1. Startup Test:**
```bash
# Restart application
docker-compose down
docker-compose up -d

# Check logs
docker logs streamvault-app 2>&1 | grep -A 5 "Cleaning up zombie"

# Expected output:
# ✅ "🧹 Cleaning up zombie recordings from database with smart recovery..."
# ✅ "✅ No zombie recordings found" OR "✅ Cleaned X zombie recordings"
# ❌ NOT: "❌ Failed to cleanup zombie recordings: ImportError"
```

**2. Zombie Recording Test:**
```sql
-- Create zombie recording
UPDATE recordings SET status = 'recording', end_time = NULL WHERE id = 42;

-- Restart application
-- docker-compose restart streamvault

-- Verify cleanup
SELECT id, status, end_time FROM recordings WHERE id = 42;
-- Should show: status = 'stopped' or 'failed', end_time NOT NULL
```

**3. Import Test:**
```bash
# Test import in Python container
docker exec -it streamvault-app python3 -c "
from app.events.handler_registry import event_handler_registry
print(f'✅ Import successful: {event_handler_registry}')
"

# Should print: "✅ Import successful: <EventHandlerRegistry object at 0x...>"
# Should NOT print: "ImportError: cannot import name 'event_handler_registry'"
```

**4. Regression Test:**
```bash
# Test EventSub still works
# 1. Add streamer via UI
# 2. Streamer goes live on Twitch
# 3. Check logs for: "🎬 STREAM_ONLINE_EVENT"
# 4. Recording starts automatically
# 5. No ImportError in logs
```

### Bug 2: Fullscreen Toggle Testing

**1. Basic Functionality:**
- [ ] Open video player (`/watch/{stream_id}`)
- [ ] Click "⛶ Fullscreen" button
- [ ] ✅ Player enters fullscreen mode
- [ ] ✅ Button text changes to "🪟 Exit Fullscreen"
- [ ] Click "🪟 Exit Fullscreen" button
- [ ] ✅ Player exits fullscreen mode
- [ ] ✅ Button text changes to "⛶ Fullscreen"

**2. ESC Key Integration:**
- [ ] Click "⛶ Fullscreen" button → Enters fullscreen
- [ ] Press ESC key
- [ ] ✅ Player exits fullscreen
- [ ] ✅ Button text updates to "⛶ Fullscreen"

**3. Rapid Clicking (Race Condition Test):**
- [ ] Click "⛶ Fullscreen" button 3 times rapidly
- [ ] ✅ No errors in console
- [ ] ✅ Player enters fullscreen (not stuck in transition)
- [ ] Click "🪟 Exit Fullscreen" button 3 times rapidly
- [ ] ✅ No errors in console
- [ ] ✅ Player exits fullscreen (not stuck)

**4. Console Verification:**
```javascript
// Open DevTools → Console
// Expected logs when clicking button:
// ✅ "🔍 TOGGLE_FULLSCREEN: { hasWrapper: true, currentElement: null, currentState: false }"
// ✅ "✅ Entering fullscreen via button"
// ✅ "🔍 FULLSCREEN_CHANGE: { from: false, to: true }"

// When clicking button again:
// ✅ "🔍 TOGGLE_FULLSCREEN: { hasWrapper: true, currentElement: <div>, currentState: true }"
// ✅ "✅ Exiting fullscreen via button"
// ✅ "🔍 FULLSCREEN_CHANGE: { from: true, to: false }"
```

**5. Cross-Browser Testing:**
- [ ] Chrome: Fullscreen toggle works both ways
- [ ] Firefox: Fullscreen toggle works both ways
- [ ] Safari: Fullscreen toggle works both ways (if supported)
- [ ] Edge: Fullscreen toggle works both ways

**6. Mobile Testing (if applicable):**
- [ ] Mobile Chrome: Fullscreen toggle works
- [ ] Mobile Safari: Fullscreen toggle works (if supported)
- [ ] Touch-friendly button (44px minimum)

### Regression Testing

**Video Player:**
- [ ] Video playback works correctly
- [ ] Chapter navigation works
- [ ] Previous/Next chapter buttons work
- [ ] Chapter list panel opens/closes
- [ ] Video controls visible in fullscreen
- [ ] Loading overlay works
- [ ] Error overlay works

**Recording System:**
- [ ] EventSub subscriptions work
- [ ] Stream online → Recording starts
- [ ] Stream offline → Recording stops
- [ ] Post-processing runs correctly
- [ ] No zombie recordings created

**Application Startup:**
- [ ] Application starts without errors
- [ ] All services initialize correctly
- [ ] Background queue starts
- [ ] WebSocket connections work
- [ ] Database migrations run (if any)

---

## 📖 Documentation References

**Bug 1: ImportError**
- `app/events/handler_registry.py` - EventHandlerRegistry class definition
- `app/services/init/startup_init.py` - Startup initialization and zombie cleanup
- `app/services/streamer_service.py` - StreamerService that requires event_registry
- **Pattern:** Singleton pattern for global service instances
- **Similar Issue:** WebSocket manager uses singleton pattern (`websocket_manager` instance)

**Bug 2: Fullscreen Toggle**
- `app/frontend/src/components/VideoPlayer.vue` - Video player component
- **MDN Docs:** [Fullscreen API](https://developer.mozilla.org/en-US/docs/Web/API/Fullscreen_API)
- **Related Issue:** Issue #1 Bug #3 (incorrectly marked as working)
- **Design System:** `.control-btn` styles, glassmorphism pattern
- **PWA Requirements:** Touch-friendly controls (44px minimum)

**Testing References:**
- `docs/KNOWN_ISSUES_SESSION_7.md` - Previous bug fixes and testing
- `docs/MASTER_TASK_LIST.md` - Task tracking and progress
- `.github/instructions/frontend.instructions.md` - Frontend patterns
- `.github/instructions/backend.instructions.md` - Backend patterns

---

## 🤖 Copilot Instructions for Future Similar Issues

### Pattern: Missing Module-Level Exports

**Problem:** Importing instance that doesn't exist at module level

```python
# ❌ WRONG: Importing non-existent instance
from app.services.some_service import some_service

# Module only defines class, not instance
class SomeService:
    pass
```

**Solution:** Create singleton getter or export instance

```python
# ✅ CORRECT: Export singleton instance
class SomeService:
    pass

_instance = None

def get_some_service():
    global _instance
    if _instance is None:
        _instance = SomeService()
    return _instance

# Backward compatibility
some_service = get_some_service()
```

**Prevention:**
- Always check if module exports what you're importing
- Use `dir(module)` to list available exports
- Create singleton getters for global services
- Document module exports in docstrings

### Pattern: Fullscreen API Best Practices

**Problem:** Button works one way but not the other

**Root Causes:**
1. Wrong element reference (`videoWrapper` vs `document.fullscreenElement`)
2. Race condition (click before `fullscreenchange` fires)
3. Event listener not updating state
4. Button disabled or click blocked

**Solution:** Optimistic updates + event listener correction

```typescript
// 1. Optimistic update for immediate feedback
const toggleFullscreen = () => {
  if (!element.value) return
  
  if (document.fullscreenElement) {
    isFullscreen.value = false  // Optimistic
    document.exitFullscreen().catch(err => {
      isFullscreen.value = true  // Revert on error
    })
  } else {
    isFullscreen.value = true  // Optimistic
    element.value.requestFullscreen().catch(err => {
      isFullscreen.value = false  // Revert on error
    })
  }
}

// 2. Event listener corrects state (source of truth)
const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

// 3. Listen to all browser prefixes
onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('webkitfullscreenchange', onFullscreenChange)
  document.addEventListener('mozfullscreenchange', onFullscreenChange)
})
```

**Testing:**
- Test button click (both enter and exit)
- Test ESC key (native exit)
- Test rapid clicking (race conditions)
- Test all browsers (Chrome, Firefox, Safari)
- Console log state transitions

### Pattern: Startup Error Handling

**Problem:** Critical services fail silently on startup

**Prevention:**
```python
async def initialize_critical_service():
    try:
        # Service initialization
        await service.start()
        logger.info("✅ Service initialized")
    except Exception as e:
        logger.error(f"❌ CRITICAL: Service failed to start: {e}", exc_info=True)
        # Decide: Raise exception (halt startup) or continue
        raise  # For CRITICAL services
        # OR: return False  # For optional services
```

**Testing:**
- Check startup logs for all services
- Test with missing dependencies
- Test with invalid configuration
- Verify graceful degradation

### Self-Check Questions

**Before fixing import errors:**
- [ ] Does the module export what I'm importing?
- [ ] Is it a class or an instance?
- [ ] Do I need a singleton pattern?
- [ ] Are there other files with similar imports?

**Before fixing fullscreen issues:**
- [ ] Does the button click event fire?
- [ ] Is the element reference correct?
- [ ] Does the state update immediately?
- [ ] Does the event listener fire?
- [ ] Are there race conditions?

**After fixing:**
- [ ] Did I test all browsers?
- [ ] Did I test rapid clicking?
- [ ] Did I add console logs for debugging?
- [ ] Did I test ESC key behavior?
- [ ] Did I check for regressions?

---

**Documented:** November 13, 2025  
**Discovered By:** Production logs + User testing  
**Related Issues:** Issue #1 (Bug #3 incorrectly marked as working)  
**Priority:** CRITICAL (Bug #1) + HIGH (Bug #2)  
**Next Steps:** 
1. Fix ImportError (20 min)
2. Fix Fullscreen Toggle (25 min)
3. Deploy hotfix
4. Update Issue #1 Bug #3 status
