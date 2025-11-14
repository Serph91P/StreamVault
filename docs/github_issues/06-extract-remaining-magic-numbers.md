# Issue #6: Extract Remaining Magic Numbers to Constants

**Priority:** MEDIUM  
**Estimated Time:** 2-3 hours  
**Sprint:** Sprint 3 - Polish & Enhancements  
**Agent:** refactor-specialist  

---

## Problem Description

StreamVault hat bereits **60+ Constants extrahiert** in `app/config/constants.py` (225 Zeilen), aber es gibt noch **14+ hardcoded magic numbers** verstreut im Codebase:

### Current Status: constants.py (Bereits Extrahiert)

**✅ 7 Dataclasses mit 60+ Constants:**
1. **AsyncDelays** (18 constants) - Generic delays, queue intervals, websocket delays
2. **RetryConfig** (7 constants) - Retry counts, retry delays
3. **Timeouts** (15 constants) - Process timeouts, queue timeouts, subprocess timeouts
4. **CacheConfig** (8 constants) - Cache sizes, TTL values
5. **FileSizeThresholds** (4 constants) - Byte conversions (KB, MB, GB)
6. **MetadataConfig** (2 constants) - Atom nesting depth limits
7. **CodecConfig** - H.265/AV1 codec options

### Remaining Hardcoded Magic Numbers

**❌ Backend: 14 magic numbers gefunden:**

#### Recording Services (6 instances):
1. **file_operations.py:58** - `await asyncio.sleep(5)  # Wait a bit`
   - Aktuell: `5` seconds hardcoded
   - Zweck: Wait for MP4 file stability check before deleting TS
   - Vorschlag: `ASYNC_DELAYS.FILE_STABILITY_CHECK = 5.0`

2. **process_manager.py:415** - `await asyncio.sleep(5)`
   - Aktuell: `5` seconds hardcoded
   - Zweck: Wait before retry after process start failure
   - Vorschlag: Already covered by `ASYNC_DELAYS.ERROR_RECOVERY_DELAY = 5.0`

3. **recording_lifecycle_manager.py:879** - `timeout=300  # 5 minute timeout`
   - Aktuell: `300` seconds hardcoded
   - Zweck: FFmpeg concatenation process start timeout
   - Vorschlag: Already covered by `TIMEOUTS.RECORDING_REMUX_SMALL = 300`

4. **recording_lifecycle_manager.py:884** - `timeout=600  # 10 minute timeout for large files`
   - Aktuell: `600` seconds hardcoded
   - Zweck: FFmpeg concatenation communicate timeout
   - Vorschlag: Already covered by `TIMEOUTS.RECORDING_REMUX_LARGE = 600`

5. **segment_concatenation_task.py:159** - `timeout=30  # 30 seconds to start`
   - Aktuell: `30` seconds hardcoded
   - Zweck: FFmpeg segment concatenation process start
   - Vorschlag: Already covered by `TIMEOUTS.SEGMENT_CONCAT_START = 30`

6. **segment_concatenation_task.py:164** - `timeout=600  # 10 minutes for concatenation`
   - Aktuell: `600` seconds hardcoded
   - Zweck: FFmpeg segment concatenation communicate
   - Vorschlag: Already covered by `TIMEOUTS.SEGMENT_CONCAT_COMPLETE = 600`

#### Core Services (3 instances):
7. **startup_init.py:113** - `await asyncio.sleep(5)  # Give queue workers time to start`
   - Aktuell: `5` seconds hardcoded
   - Zweck: Wait for queue worker startup
   - Vorschlag: Already covered by `ASYNC_DELAYS.QUEUE_WORKER_START_DELAY = 5.0`

8. **state_persistence_service.py:323** - `await asyncio.sleep(5)  # Wait before retrying`
   - Aktuell: `5` seconds hardcoded
   - Zweck: Wait before retry on persistence error
   - Vorschlag: Already covered by `ASYNC_DELAYS.ERROR_RECOVERY_DELAY = 5.0`

9. **automatic_queue_recovery_service.py:85** - `await asyncio.sleep(10)  # Wait longer on error`
   - Aktuell: `10` seconds hardcoded
   - Zweck: Wait after queue recovery error
   - Vorschlag: Already covered by `ASYNC_DELAYS.AUTO_RECOVERY_ERROR_WAIT = 10.0`

#### Image Services (1 instance):
10. **image_sync_service.py:244** - `await asyncio.sleep(30)`
    - Aktuell: `30` seconds hardcoded
    - Zweck: Image sync interval
    - Vorschlag: Already covered by `ASYNC_DELAYS.IMAGE_SYNC_INTERVAL = 30.0`

#### Test/Dev Services (4 instances):
11. **development_test_runner.py:417** - `timeout=30`
    - Aktuell: `30` seconds hardcoded
    - Zweck: Subprocess test command timeout
    - Vorschlag: Already covered by `TIMEOUTS.GRACEFUL_SHUTDOWN = 30`

12. **development_test_runner.py:510** - `timeout=30`
    - Aktuell: `30` seconds hardcoded
    - Zweck: Remux command timeout
    - Vorschlag: Already covered by `TIMEOUTS.GRACEFUL_SHUTDOWN = 30`

13. **test_service.py:204** - `timeout=30`
    - Aktuell: `30` seconds hardcoded
    - Zweck: Test command subprocess timeout
    - Vorschlag: Already covered by `TIMEOUTS.GRACEFUL_SHUTDOWN = 30`

14. **test_service.py:259** - `timeout=30`
    - Aktuell: `30` seconds hardcoded
    - Zweck: Create command subprocess timeout
    - Vorschlag: Already covered by `TIMEOUTS.GRACEFUL_SHUTDOWN = 30`

#### File Size Threshold (1 instance):
15. **file_operations.py:61** - `new_mp4_size > 1024 * 1024`
    - Aktuell: `1048576` bytes hardcoded (1 MB)
    - Zweck: Minimum MP4 file size for stability check
    - Vorschlag: Already covered by `FILE_SIZE_THRESHOLDS.MB = 1048576`

**❌ Frontend: 3 magic numbers gefunden:**

#### WebSocket Reconnection (2 instances):
1. **useWebSocket.ts:166** - `const baseDelay = 1000 * Math.pow(2, this.reconnectAttempts - 1)`
   - Aktuell: `1000` ms base delay hardcoded
   - Zweck: Exponential backoff base delay
   - Vorschlag: `WEBSOCKET.BASE_RECONNECT_DELAY_MS = 1000`

2. **useWebSocket.ts:168** - `const delay = Math.min(baseDelay + jitter, 30000)`
   - Aktuell: `30000` ms max delay hardcoded
   - Zweck: Maximum reconnection delay (30 seconds)
   - Vorschlag: `WEBSOCKET.MAX_RECONNECT_DELAY_MS = 30000`

#### Stream Refresh (1 instance):
3. **useStreams.ts:48** - `const REFRESH_DELAY_MS = 1000`
   - Aktuell: `1000` ms hardcoded
   - Zweck: Delay after stream deletion before refresh
   - Vorschlag: `UI.STREAM_REFRESH_DELAY_MS = 1000`

---

## Solution Overview

### Phase 1: Analyse (30 min)
- ✅ **COMPLETED:** Audit bereits durchgeführt
- ✅ **COMPLETED:** 14 backend + 3 frontend magic numbers identifiziert
- ✅ **IMPORTANT FINDING:** **12 von 14 backend constants existieren bereits!**
  - Nur **2 neue Constants** nötig (FILE_STABILITY_CHECK + Frontend constants)

### Phase 2: Backend - Add Missing Constants (30 min)

**Nur 1 neues Backend-Constant nötig:**

```python
# app/config/constants.py - Add to AsyncDelays dataclass

@dataclass(frozen=True)
class AsyncDelays:
    # ... existing 18 constants ...
    
    FILE_STABILITY_CHECK: float = 5.0  # Seconds - Wait for MP4 file stability before cleanup
```

**Alle anderen Backend-Values nutzen bereits existierende Constants:**
- `ERROR_RECOVERY_DELAY` - Covers 3 instances (process_manager, state_persistence, others)
- `QUEUE_WORKER_START_DELAY` - Covers startup_init.py
- `IMAGE_SYNC_INTERVAL` - Covers image_sync_service.py
- `AUTO_RECOVERY_ERROR_WAIT` - Covers automatic_queue_recovery_service.py
- `RECORDING_REMUX_SMALL/LARGE` - Covers recording_lifecycle_manager.py timeouts
- `SEGMENT_CONCAT_START/COMPLETE` - Covers segment_concatenation_task.py timeouts
- `GRACEFUL_SHUTDOWN` - Covers 4 test/dev service timeouts
- `FILE_SIZE_THRESHOLDS.MB` - Covers file_operations.py size check

### Phase 3: Backend - Replace Hardcoded Values (45 min)

**Replace 14 backend magic numbers with constant imports:**

#### Files Requiring Import Updates (10 files):
1. `app/services/recording/file_operations.py` - Add `ASYNC_DELAYS, FILE_SIZE_THRESHOLDS`
2. `app/services/recording/process_manager.py` - Add `ASYNC_DELAYS`
3. `app/services/recording/recording_lifecycle_manager.py` - Add `TIMEOUTS` (already has `ASYNC_DELAYS`)
4. `app/services/recording/segment_concatenation_task.py` - Add `TIMEOUTS`
5. `app/services/init/startup_init.py` - Add `ASYNC_DELAYS`
6. `app/services/core/state_persistence_service.py` - Add `ASYNC_DELAYS`
7. `app/services/automatic_queue_recovery_service.py` - Add `ASYNC_DELAYS`
8. `app/services/images/image_sync_service.py` - Add `ASYNC_DELAYS`
9. `app/services/system/development_test_runner.py` - Add `TIMEOUTS`
10. `app/services/core/test_service.py` - Add `TIMEOUTS`

### Phase 4: Frontend - Create Constants File (20 min)

**Create new file:** `app/frontend/src/config/constants.ts`

**Structure:**

```typescript
/**
 * Centralized Configuration Constants for Frontend
 * 
 * All magic numbers, delays, limits should be defined here for:
 * - Easy tuning and maintenance
 * - Single source of truth
 * - Clear documentation
 */

/**
 * WebSocket reconnection configuration
 */
export const WEBSOCKET = {
  /** Base delay in milliseconds for exponential backoff */
  BASE_RECONNECT_DELAY_MS: 1000,
  
  /** Maximum delay in milliseconds between reconnection attempts */
  MAX_RECONNECT_DELAY_MS: 30000,
} as const

/**
 * UI interaction delays and timing
 */
export const UI = {
  /** Delay in milliseconds after stream deletion before refreshing list */
  STREAM_REFRESH_DELAY_MS: 1000,
  
  /** Debounce delay in milliseconds for search inputs */
  SEARCH_DEBOUNCE_MS: 300,
  
  /** Toast notification duration in milliseconds */
  TOAST_DURATION_MS: 3000,
} as const

/**
 * Image loading configuration
 */
export const IMAGE_LOADING = {
  /** Number of categories to preload images for */
  VISIBLE_CATEGORIES_PRELOAD_COUNT: 20,
  
  /** Lazy load threshold in pixels */
  LAZY_LOAD_THRESHOLD_PX: 200,
} as const

/**
 * API configuration
 */
export const API = {
  /** Default API request timeout in milliseconds */
  DEFAULT_TIMEOUT_MS: 30000,
  
  /** Retry delay in milliseconds for failed requests */
  RETRY_DELAY_MS: 1000,
  
  /** Maximum number of retry attempts */
  MAX_RETRY_ATTEMPTS: 3,
} as const
```

### Phase 5: Frontend - Replace Hardcoded Values (15 min)

**Replace 3 frontend magic numbers with constant imports:**

#### Files to Modify (2 files):
1. `app/frontend/src/composables/useWebSocket.ts` - Replace 2 hardcoded values
2. `app/frontend/src/composables/useStreams.ts` - Replace 1 hardcoded value

---

## Current Implementation Status

### ✅ Backend Constants (Already Exists)
**File:** `app/config/constants.py` (225 lines)

**7 Dataclasses mit 60+ Constants:**
- **AsyncDelays** (18) - Delays for various operations
- **RetryConfig** (7) - Retry counts and delays
- **Timeouts** (15) - Process, queue, subprocess timeouts
- **CacheConfig** (8) - Cache sizes and TTL values
- **FileSizeThresholds** (4) - Byte conversions
- **MetadataConfig** (2) - Atom nesting limits
- **CodecConfig** - Codec options dictionary

**Architecture:**
- Frozen dataclasses (immutable)
- Global singleton instances
- Type hints on all fields
- Comprehensive docstrings

### ❌ Missing Constants
1. **Backend:** 1 new constant needed (`FILE_STABILITY_CHECK`)
2. **Frontend:** New file needed (`constants.ts` with 4 categories)

### ❌ Not Using Existing Constants
- **10 Backend files** have hardcoded values but constants exist
- **2 Frontend files** have hardcoded values, no constants file

---

## Required Changes

### Backend Changes

#### 1. Add Missing Constant to constants.py

**File:** `app/config/constants.py`

**Change:**
```python
@dataclass(frozen=True)
class AsyncDelays:
    # ... existing 18 constants ...
    
    # New constant
    FILE_STABILITY_CHECK: float = 5.0  # Seconds to wait for MP4 file stability before cleanup
```

#### 2. Replace Hardcoded Values in 10 Files

**Pattern for each file:**
1. Add import: `from app.config.constants import ASYNC_DELAYS, TIMEOUTS, FILE_SIZE_THRESHOLDS`
2. Replace hardcoded number with constant reference
3. Keep inline comment explaining context

**Example - file_operations.py:**
```python
# Before:
await asyncio.sleep(5)  # Wait a bit

# After:
from app.config.constants import ASYNC_DELAYS, FILE_SIZE_THRESHOLDS
await asyncio.sleep(ASYNC_DELAYS.FILE_STABILITY_CHECK)  # Wait for MP4 file stability
```

**Example - segment_concatenation_task.py:**
```python
# Before:
timeout=30  # 30 seconds to start

# After:
from app.config.constants import TIMEOUTS
timeout=TIMEOUTS.SEGMENT_CONCAT_START
```

**Example - file_operations.py size check:**
```python
# Before:
if new_mp4_size > 1024 * 1024:  # Stable and > 1MB

# After:
if new_mp4_size > FILE_SIZE_THRESHOLDS.MB:  # Stable and > 1MB
```

#### Files Requiring Changes (10 files):

**Recording Services (4 files):**
1. `app/services/recording/file_operations.py`
   - Line 58: Replace `5` → `ASYNC_DELAYS.FILE_STABILITY_CHECK`
   - Line 61: Replace `1024 * 1024` → `FILE_SIZE_THRESHOLDS.MB`

2. `app/services/recording/process_manager.py`
   - Line 415: Replace `5` → `ASYNC_DELAYS.ERROR_RECOVERY_DELAY`

3. `app/services/recording/recording_lifecycle_manager.py`
   - Line 879: Replace `300` → `TIMEOUTS.RECORDING_REMUX_SMALL`
   - Line 884: Replace `600` → `TIMEOUTS.RECORDING_REMUX_LARGE`

4. `app/services/recording/segment_concatenation_task.py`
   - Line 159: Replace `30` → `TIMEOUTS.SEGMENT_CONCAT_START`
   - Line 164: Replace `600` → `TIMEOUTS.SEGMENT_CONCAT_COMPLETE`

**Core Services (3 files):**
5. `app/services/init/startup_init.py`
   - Line 113: Replace `5` → `ASYNC_DELAYS.QUEUE_WORKER_START_DELAY`

6. `app/services/core/state_persistence_service.py`
   - Line 323: Replace `5` → `ASYNC_DELAYS.ERROR_RECOVERY_DELAY`

7. `app/services/automatic_queue_recovery_service.py`
   - Line 85: Replace `10` → `ASYNC_DELAYS.AUTO_RECOVERY_ERROR_WAIT`

**Image Services (1 file):**
8. `app/services/images/image_sync_service.py`
   - Line 244: Replace `30` → `ASYNC_DELAYS.IMAGE_SYNC_INTERVAL`

**Test/Dev Services (2 files):**
9. `app/services/system/development_test_runner.py`
   - Line 417: Replace `timeout=30` → `timeout=TIMEOUTS.GRACEFUL_SHUTDOWN`
   - Line 510: Replace `timeout=30` → `timeout=TIMEOUTS.GRACEFUL_SHUTDOWN`

10. `app/services/core/test_service.py`
    - Line 204: Replace `timeout=30` → `timeout=TIMEOUTS.GRACEFUL_SHUTDOWN`
    - Line 259: Replace `timeout=30` → `timeout=TIMEOUTS.GRACEFUL_SHUTDOWN`

### Frontend Changes

#### 1. Create Constants File

**New File:** `app/frontend/src/config/constants.ts`

**Content:**
- WEBSOCKET configuration (base delay, max delay)
- UI configuration (refresh delays, debounce, toast duration)
- IMAGE_LOADING configuration (preload counts, thresholds)
- API configuration (timeouts, retries)

**Structure:**
- Use `as const` for type safety
- JSDoc comments for each constant
- Group related constants in objects
- Export as named exports

#### 2. Replace Hardcoded Values in 2 Files

**Files to Modify:**

1. `app/frontend/src/composables/useWebSocket.ts`
   - Line 166: Replace `1000` → `WEBSOCKET.BASE_RECONNECT_DELAY_MS`
   - Line 168: Replace `30000` → `WEBSOCKET.MAX_RECONNECT_DELAY_MS`

**Change:**
```typescript
// Before:
const baseDelay = 1000 * Math.pow(2, this.reconnectAttempts - 1)
const delay = Math.min(baseDelay + jitter, 30000)

// After:
import { WEBSOCKET } from '@/config/constants'
const baseDelay = WEBSOCKET.BASE_RECONNECT_DELAY_MS * Math.pow(2, this.reconnectAttempts - 1)
const delay = Math.min(baseDelay + jitter, WEBSOCKET.MAX_RECONNECT_DELAY_MS)
```

2. `app/frontend/src/composables/useStreams.ts`
   - Line 48: Replace `1000` → `UI.STREAM_REFRESH_DELAY_MS`

**Change:**
```typescript
// Before:
const REFRESH_DELAY_MS = 1000

// After:
import { UI } from '@/config/constants'
const REFRESH_DELAY_MS = UI.STREAM_REFRESH_DELAY_MS
```

---

## Files to Create

### Frontend
1. `app/frontend/src/config/constants.ts` - New constants file with 4 categories

---

## Files to Modify

### Backend (10 files)
1. `app/config/constants.py` - Add 1 new constant (FILE_STABILITY_CHECK)
2. `app/services/recording/file_operations.py` - Replace 2 hardcoded values
3. `app/services/recording/process_manager.py` - Replace 1 hardcoded value
4. `app/services/recording/recording_lifecycle_manager.py` - Replace 2 hardcoded values
5. `app/services/recording/segment_concatenation_task.py` - Replace 2 hardcoded values
6. `app/services/init/startup_init.py` - Replace 1 hardcoded value
7. `app/services/core/state_persistence_service.py` - Replace 1 hardcoded value
8. `app/services/automatic_queue_recovery_service.py` - Replace 1 hardcoded value
9. `app/services/images/image_sync_service.py` - Replace 1 hardcoded value
10. `app/services/system/development_test_runner.py` - Replace 2 hardcoded values
11. `app/services/core/test_service.py` - Replace 2 hardcoded values

### Frontend (2 files)
1. `app/frontend/src/composables/useWebSocket.ts` - Replace 2 hardcoded values
2. `app/frontend/src/composables/useStreams.ts` - Replace 1 hardcoded value

---

## Acceptance Criteria

### Backend Constants
- [ ] `FILE_STABILITY_CHECK` added to `AsyncDelays` dataclass
- [ ] All 10 backend files import from `app.config.constants`
- [ ] All 14 hardcoded numbers replaced with constant references
- [ ] Inline comments preserved explaining context
- [ ] No behavioral changes (same timeout/delay values)
- [ ] Backend tests pass (`pytest app/`)

### Frontend Constants
- [ ] `constants.ts` file created in `app/frontend/src/config/`
- [ ] 4 constant categories defined (WEBSOCKET, UI, IMAGE_LOADING, API)
- [ ] All constants use `as const` for type safety
- [ ] JSDoc comments added for all constants
- [ ] 2 frontend files import from `@/config/constants`
- [ ] All 3 hardcoded numbers replaced
- [ ] Frontend builds without errors (`npm run build`)

### Code Quality
- [ ] All imports alphabetically sorted
- [ ] Type hints maintained on all modified code
- [ ] Descriptive constant names (no DELAY_1, TIMEOUT_2, etc.)
- [ ] Comments explain purpose of each constant
- [ ] No magic numbers left in modified files

### Documentation
- [ ] `constants.py` docstrings updated if needed
- [ ] Frontend `constants.ts` has module-level JSDoc
- [ ] Inline comments explain why constants are used
- [ ] Backend instructions reference new constants pattern

---

## Testing Checklist

### Backend Testing

#### Unit Tests
- [ ] Run full test suite: `pytest app/ -v`
- [ ] All tests pass without modification
- [ ] No new errors or warnings
- [ ] Import statements don't break existing code

#### Integration Testing
- [ ] Start application: `python run_local.py`
- [ ] Check logs for startup errors
- [ ] Verify recording starts successfully
- [ ] Check queue workers start correctly
- [ ] Verify image sync service runs
- [ ] Check automatic recovery service works

#### Behavior Verification
- [ ] Recording starts with same delays (process_manager)
- [ ] File cleanup waits correct duration (file_operations)
- [ ] Segment concatenation uses correct timeouts
- [ ] Queue workers wait correct intervals
- [ ] Image sync runs on correct interval (30s)
- [ ] State persistence retry delays unchanged (5s)

#### Timeout Testing
- [ ] FFmpeg concatenation times out correctly (300s/600s)
- [ ] Segment concatenation times out correctly (30s/600s)
- [ ] Test commands time out correctly (30s)

#### Edge Cases
- [ ] Constants imported correctly in all 10 files
- [ ] No circular import issues
- [ ] Constants accessible via singleton instances
- [ ] Type hints work correctly in IDEs

### Frontend Testing

#### Build Testing
- [ ] Build frontend: `cd app/frontend && npm run build`
- [ ] No TypeScript errors
- [ ] No build warnings
- [ ] Bundle size unchanged (constants minimal impact)

#### Runtime Testing
- [ ] Start dev server: `npm run dev`
- [ ] Open browser console, no errors
- [ ] WebSocket reconnects with correct delays
- [ ] Stream deletion → refresh waits 1000ms
- [ ] Verify exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (max)

#### WebSocket Reconnection Testing
- [ ] Disconnect internet → Check reconnect delay progression
- [ ] First attempt: ~1000ms delay
- [ ] Second attempt: ~2000ms delay
- [ ] Third attempt: ~4000ms delay
- [ ] Fourth+ attempts: capped at 30000ms
- [ ] Jitter adds randomness (verify in logs)

#### UI Interaction Testing
- [ ] Delete stream → List refreshes after 1000ms
- [ ] Verify no immediate refresh (delay works)
- [ ] Search input debounces correctly (if using constants)

#### Constants Import Testing
- [ ] Import in useWebSocket.ts works: `import { WEBSOCKET } from '@/config/constants'`
- [ ] Import in useStreams.ts works: `import { UI } from '@/config/constants'`
- [ ] TypeScript autocomplete suggests constants
- [ ] VSCode shows JSDoc comments on hover

### Cross-Cutting Testing

#### Performance
- [ ] No performance degradation from constant lookups
- [ ] Application starts in same time
- [ ] Recording latency unchanged

#### Maintainability
- [ ] Constants easy to find and modify
- [ ] Single source of truth for all timing values
- [ ] Clear which constant controls which behavior

---

## Documentation References

### Existing Documentation
- **Backend Constants:** `app/config/constants.py` (225 lines, 7 dataclasses)
- **Backend Instructions:** `.github/instructions/backend.instructions.md` (mentions constants.py)
- **Copilot Instructions:** `.github/copilot-instructions.md` (lines about NO MAGIC NUMBERS)

### Related Features
- **Recording Services:** Use AsyncDelays, Timeouts for process management
- **Queue Management:** Uses RetryConfig, AsyncDelays for task processing
- **Image Services:** Use CacheConfig for TTL, AsyncDelays for intervals

### Architecture Patterns
- **Frozen Dataclasses:** Immutable configuration objects
- **Singleton Instances:** Global access via module-level variables
- **Type Safety:** Type hints on all constant fields
- **Documentation:** Inline comments explain purpose of each constant

---

## Best Practices

### Constant Naming
- ✅ Use descriptive names: `FILE_STABILITY_CHECK` not `DELAY_5`
- ✅ Include units in name: `_MS` for milliseconds, `_SECONDS` for seconds
- ✅ Group related constants in dataclasses
- ✅ Use UPPER_SNAKE_CASE for constant names

### Documentation
- ✅ Add inline comments explaining purpose
- ✅ Document units (seconds, milliseconds, bytes)
- ✅ Explain why value is set to specific number
- ✅ Add JSDoc for frontend constants

### Architecture
- ✅ Use frozen dataclasses for immutability (backend)
- ✅ Use `as const` for type safety (frontend)
- ✅ Create singleton instances for easy import
- ✅ Maintain existing category structure

### When to Extract
- ✅ Extract if value used in multiple places
- ✅ Extract if value might need tuning
- ✅ Extract if value has business meaning
- ❌ Don't extract obvious constants (0, 1, 100)
- ❌ Don't extract values that are truly magic (algorithm constants)

### Testing Strategy
- ✅ Replace constants without changing values
- ✅ Verify behavior unchanged after extraction
- ✅ Run full test suite after each file modification
- ✅ Test edge cases (timeouts, retries)

### Import Organization
- ✅ Group constant imports together
- ✅ Alphabetically sort imports
- ✅ Use specific imports: `from app.config.constants import ASYNC_DELAYS`
- ✅ Avoid wildcard imports: `from constants import *`

---

## Security Considerations

### No Security Impact
- Constants extraction is refactoring only
- No changes to business logic
- No exposure of sensitive data

### Best Practices
- ✅ Keep timeout values reasonable (prevent DoS)
- ✅ Document why specific values chosen
- ✅ Avoid extremely long timeouts (resource exhaustion)
- ✅ Use constants for rate limiting values

---

## Copilot Instructions

### Context Before Starting

**Read These Files First:**
1. `app/config/constants.py` - Existing patterns and structure (225 lines)
2. `.github/instructions/backend.instructions.md` - Backend patterns
3. `.github/instructions/frontend.instructions.md` - Frontend patterns
4. `.github/copilot-instructions.md` - Project-wide standards

**Understand Current Architecture:**
- Backend uses frozen dataclasses with singleton instances
- 60+ constants already extracted across 7 categories
- Global imports: `from app.config.constants import ASYNC_DELAYS, TIMEOUTS`
- Usage pattern: `ASYNC_DELAYS.BRIEF_PAUSE`, `TIMEOUTS.GRACEFUL_SHUTDOWN`

**Key Findings:**
- 12 of 14 backend magic numbers have existing constants (just need import + replace)
- Only 1 new backend constant needed (`FILE_STABILITY_CHECK`)
- Frontend has no constants file yet (need to create)

### Implementation Order

#### Phase 1: Backend Constants (45 min)

**Step 1: Add Missing Constant (5 min)**
```python
# app/config/constants.py - Add to AsyncDelays dataclass

FILE_STABILITY_CHECK: float = 5.0  # Seconds to wait for MP4 file stability before cleanup
```

**Step 2: Update 10 Backend Files (40 min)**

**For each file:**
1. Find hardcoded magic number (use grep search results from audit)
2. Add appropriate import: `from app.config.constants import ASYNC_DELAYS, TIMEOUTS, FILE_SIZE_THRESHOLDS`
3. Replace number with constant reference
4. Keep inline comment explaining context
5. Run tests: `pytest app/services/recording/ -v` (for recording files)

**Priority Order:**
1. **Recording services first** (4 files) - Most critical for production
   - file_operations.py, process_manager.py, recording_lifecycle_manager.py, segment_concatenation_task.py
2. **Core services** (3 files) - Important for startup
   - startup_init.py, state_persistence_service.py, automatic_queue_recovery_service.py
3. **Image services** (1 file) - Medium priority
   - image_sync_service.py
4. **Test/Dev services** (2 files) - Lower priority
   - development_test_runner.py, test_service.py

**Example Pattern:**
```python
# BEFORE:
await asyncio.sleep(5)  # Wait before retry

# AFTER:
from app.config.constants import ASYNC_DELAYS
await asyncio.sleep(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)  # Wait before retry
```

**Test After Each File:**
```bash
# Quick validation
python -c "from app.services.recording.file_operations import *"
python -c "from app.config.constants import ASYNC_DELAYS; print(ASYNC_DELAYS.FILE_STABILITY_CHECK)"

# Full test suite (after all changes)
pytest app/ -v
```

#### Phase 2: Frontend Constants (35 min)

**Step 1: Create constants.ts (15 min)**
```typescript
// app/frontend/src/config/constants.ts

/**
 * Centralized Configuration Constants for Frontend
 */

export const WEBSOCKET = {
  BASE_RECONNECT_DELAY_MS: 1000,
  MAX_RECONNECT_DELAY_MS: 30000,
} as const

export const UI = {
  STREAM_REFRESH_DELAY_MS: 1000,
  SEARCH_DEBOUNCE_MS: 300,
  TOAST_DURATION_MS: 3000,
} as const

export const IMAGE_LOADING = {
  VISIBLE_CATEGORIES_PRELOAD_COUNT: 20,
  LAZY_LOAD_THRESHOLD_PX: 200,
} as const

export const API = {
  DEFAULT_TIMEOUT_MS: 30000,
  RETRY_DELAY_MS: 1000,
  MAX_RETRY_ATTEMPTS: 3,
} as const
```

**Step 2: Update useWebSocket.ts (10 min)**
```typescript
// app/frontend/src/composables/useWebSocket.ts

import { WEBSOCKET } from '@/config/constants'

// BEFORE:
const baseDelay = 1000 * Math.pow(2, this.reconnectAttempts - 1)
const delay = Math.min(baseDelay + jitter, 30000)

// AFTER:
const baseDelay = WEBSOCKET.BASE_RECONNECT_DELAY_MS * Math.pow(2, this.reconnectAttempts - 1)
const delay = Math.min(baseDelay + jitter, WEBSOCKET.MAX_RECONNECT_DELAY_MS)
```

**Step 3: Update useStreams.ts (10 min)**
```typescript
// app/frontend/src/composables/useStreams.ts

import { UI } from '@/config/constants'

// BEFORE:
const REFRESH_DELAY_MS = 1000

// AFTER:
const REFRESH_DELAY_MS = UI.STREAM_REFRESH_DELAY_MS
```

**Test Frontend:**
```bash
cd app/frontend
npm run build  # Should complete without errors
npm run dev    # Test in browser
```

### Testing Strategy

**After Each Backend File Change:**
```bash
# Verify import works
python -c "from app.services.recording.file_operations import *"

# Run specific test
pytest app/services/recording/ -v -k "test_file_operations"
```

**After All Backend Changes:**
```bash
# Full test suite
pytest app/ -v

# Start application
python run_local.py  # Check logs for errors
```

**After Frontend Changes:**
```bash
cd app/frontend

# Build test
npm run build  # Must succeed with 0 errors

# Type check
npm run type-check  # Verify TypeScript types

# Dev server
npm run dev  # Test in browser
```

**Behavior Verification:**
1. Start recording → Check process_manager uses correct delays
2. Wait for file cleanup → Verify 5s delay (file_operations)
3. Check queue workers → Verify 5s startup delay (startup_init)
4. Disconnect WebSocket → Verify exponential backoff (1s, 2s, 4s, ...)

### Common Pitfalls

#### Backend Pitfalls

**❌ WRONG: Importing wrong constant**
```python
from app.config.constants import ASYNC_DELAYS
await asyncio.sleep(ASYNC_DELAYS.BRIEF_PAUSE)  # 1.0s - Wrong value!
# Should use ERROR_RECOVERY_DELAY (5.0s)
```

**✅ CORRECT: Use exact matching constant**
```python
from app.config.constants import ASYNC_DELAYS
await asyncio.sleep(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)  # 5.0s - Correct!
```

**❌ WRONG: Breaking existing import**
```python
# File already imports constants
from app.config.constants import ASYNC_DELAYS

# Don't add duplicate import!
from app.config.constants import TIMEOUTS, ASYNC_DELAYS  # ❌ Duplicate ASYNC_DELAYS
```

**✅ CORRECT: Extend existing import**
```python
# File already imports constants
from app.config.constants import ASYNC_DELAYS, TIMEOUTS  # ✅ Combined import
```

**❌ WRONG: Removing context comment**
```python
# BEFORE:
await asyncio.sleep(5)  # Wait for MP4 file stability

# AFTER (WRONG):
await asyncio.sleep(ASYNC_DELAYS.FILE_STABILITY_CHECK)  # Lost context!
```

**✅ CORRECT: Preserve context comment**
```python
# BEFORE:
await asyncio.sleep(5)  # Wait for MP4 file stability

# AFTER (CORRECT):
await asyncio.sleep(ASYNC_DELAYS.FILE_STABILITY_CHECK)  # Wait for MP4 file stability
```

#### Frontend Pitfalls

**❌ WRONG: Mutable export**
```typescript
export const WEBSOCKET = {
  BASE_RECONNECT_DELAY_MS: 1000,
}  // Missing 'as const' - TypeScript infers number, not literal
```

**✅ CORRECT: Immutable with 'as const'**
```typescript
export const WEBSOCKET = {
  BASE_RECONNECT_DELAY_MS: 1000,
} as const  // TypeScript infers literal type 1000
```

**❌ WRONG: Wrong import path**
```typescript
import { WEBSOCKET } from '../config/constants'  // Relative path fragile
```

**✅ CORRECT: Use path alias**
```typescript
import { WEBSOCKET } from '@/config/constants'  // Path alias robust
```

**❌ WRONG: Importing everything**
```typescript
import * as CONSTANTS from '@/config/constants'
const delay = CONSTANTS.WEBSOCKET.BASE_RECONNECT_DELAY_MS  // Verbose
```

**✅ CORRECT: Named import**
```typescript
import { WEBSOCKET } from '@/config/constants'
const delay = WEBSOCKET.BASE_RECONNECT_DELAY_MS  // Clean
```

### Debugging Tips

**Backend Issues:**

**Problem: Import error "cannot import name 'ASYNC_DELAYS'"**
```bash
# Solution: Check constants.py syntax
python -c "from app.config.constants import ASYNC_DELAYS; print(ASYNC_DELAYS)"

# Verify global instance exists
grep "ASYNC_DELAYS = AsyncDelays()" app/config/constants.py
```

**Problem: Tests fail after constant extraction**
```bash
# Solution: Verify values unchanged
python -c "from app.config.constants import ASYNC_DELAYS; print(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)"
# Should print: 5.0

# Check if constant used correctly
grep -n "ERROR_RECOVERY_DELAY" app/services/recording/process_manager.py
```

**Problem: Recording behavior changed**
```bash
# Solution: Compare old vs new values
# BEFORE: await asyncio.sleep(5)
# AFTER: await asyncio.sleep(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)

# Verify constant value
python -c "from app.config.constants import ASYNC_DELAYS; print(ASYNC_DELAYS.ERROR_RECOVERY_DELAY == 5.0)"
# Should print: True
```

**Frontend Issues:**

**Problem: TypeScript error "Cannot find module '@/config/constants'"**
```bash
# Solution: Verify file exists
ls app/frontend/src/config/constants.ts

# Check tsconfig.json path aliases
grep -A5 "paths" app/frontend/tsconfig.json
```

**Problem: Build error "Property 'BASE_RECONNECT_DELAY_MS' does not exist"**
```typescript
// Solution: Check export syntax
export const WEBSOCKET = {
  BASE_RECONNECT_DELAY_MS: 1000,  // Typo in name?
} as const
```

**Problem: WebSocket reconnect delays changed**
```javascript
// Solution: Log constant values in browser console
import { WEBSOCKET } from '@/config/constants'
console.log(WEBSOCKET.BASE_RECONNECT_DELAY_MS)  // Should print: 1000
console.log(WEBSOCKET.MAX_RECONNECT_DELAY_MS)   // Should print: 30000
```

### Success Criteria Checklist

**Backend Complete When:**
- [ ] 1 new constant added to `constants.py`
- [ ] 10 files updated with constant imports
- [ ] 14 hardcoded numbers replaced
- [ ] `pytest app/ -v` passes (all tests green)
- [ ] Application starts without errors
- [ ] Recording starts with same behavior

**Frontend Complete When:**
- [ ] `constants.ts` file created with 4 categories
- [ ] 2 files updated with constant imports
- [ ] 3 hardcoded numbers replaced
- [ ] `npm run build` succeeds (0 errors)
- [ ] TypeScript types correct (IDE autocomplete works)
- [ ] WebSocket reconnects with correct delays

**Documentation Complete When:**
- [ ] Inline comments preserved
- [ ] JSDoc added for frontend constants
- [ ] Import statements alphabetically sorted
- [ ] No magic numbers left in modified files

---

## Related Documentation

### Project Standards
- `.github/copilot-instructions.md` - NO MAGIC NUMBERS policy
- `.github/instructions/backend.instructions.md` - Backend constants pattern
- `.github/instructions/frontend.instructions.md` - Frontend constants pattern

### Existing Code
- `app/config/constants.py` - Current backend constants (225 lines, 7 dataclasses)
- `app/services/queues/task_queue_manager.py` - Example of proper constant usage
- `app/services/recording/recording_lifecycle_manager.py` - Example of partial constant usage

### Related Issues
- Issue #3: H.265/AV1 Codec Support - Added CodecConfig to constants.py
- MASTER_TASK_LIST.md - Magic numbers mentioned as code quality issue

---

## Timeline Estimate

### Backend Work: 1.5 hours
- Add 1 constant to constants.py: 5 minutes
- Update 10 files with imports and replacements: 60 minutes (6 min/file avg)
- Testing and validation: 25 minutes

### Frontend Work: 35 minutes
- Create constants.ts file: 15 minutes
- Update 2 files with imports: 10 minutes
- Testing and validation: 10 minutes

### Total: 2 hours 5 minutes

**Breakdown by Priority:**
- **Critical (Recording Services):** 30 minutes - 4 files
- **High (Core Services):** 20 minutes - 3 files
- **Medium (Image Services):** 10 minutes - 1 file
- **Low (Test/Dev Services):** 15 minutes - 2 files
- **Frontend:** 35 minutes - 3 files (1 new, 2 modified)
- **Validation:** 25 minutes - Full testing

---

## Notes

### Why This Matters
- **Maintainability:** Single source of truth for all timing values
- **Tunability:** Easy to adjust timeouts/delays without code diving
- **Clarity:** Descriptive names explain purpose (not just `5` or `30`)
- **Consistency:** Same pattern used across backend and frontend
- **Documentation:** Constants self-document their purpose

### Scope Boundaries
- **In Scope:** Extract identified magic numbers to constants
- **In Scope:** Create frontend constants file
- **Out of Scope:** Extract every single number in codebase
- **Out of Scope:** Change values of constants (keep existing behavior)
- **Out of Scope:** Refactor constant structure (maintain existing pattern)

### Post-Completion
- Update MASTER_TASK_LIST.md to mark task complete
- Create GitHub issue with this documentation
- Consider audit for remaining magic numbers in other areas (events/, middleware/, etc.)
