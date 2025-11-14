# Extract Magic Numbers to Constants

## 🟢 Priority: MEDIUM
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 3-4 hours  
**Sprint:** Sprint 3: Polish & Enhancements  
**Impact:** MEDIUM - Code maintainability, readability, easier performance tuning

---

## 📝 Problem Description

### Current Issue: Magic Numbers Throughout Codebase

**Definition:** Magic numbers are literal numeric values in code without context or meaning.

**Examples Found in Backend:**
```python
await asyncio.sleep(5.0)           # Why 5 seconds? Error recovery? Rate limiting?
if file_size > 1073741824:         # What is 1073741824? (Answer: 1GB in bytes)
max_retries = 3                    # Why 3? Is this optimal?
timeout = 30                       # 30 seconds? Minutes? What operation?
cache = TTLCache(maxsize=1000, ttl=300)  # Why 1000? Why 300 seconds?
```

**Examples Found in Frontend:**
```typescript
setTimeout(() => fetch(), 300)     # Debounce delay? Animation timing?
if (categories.length > 20) {      # Preload threshold? Why 20?
const TOAST_DURATION = 3000        # Milliseconds? Why 3 seconds?
await new Promise(r => setTimeout(r, 100))  # Why 100ms delay?
```

---

## 🎯 Impact & Problems

### 1. Maintainability Issues
**Problem:** Changing a value requires searching entire codebase
- Want to increase error recovery delay from 5s to 10s?
- Must find all `await asyncio.sleep(5.0)` instances
- Risk missing occurrences or changing wrong values
- No single source of truth

### 2. Readability Issues
**Problem:** Numbers lack context and meaning
- `if file_size > 1073741824` → What is this checking?
- Reader must calculate: 1073741824 = 1024³ = 1GB
- Cognitive load for code reviewers
- Slows down debugging

### 3. Inconsistency Issues
**Problem:** Same concept, different values across codebase
- Error recovery delay: `5.0` in one file, `5` in another, `6.0` in third
- Retry counts: `3` in one service, `5` in another
- Timeout values: `30`, `60`, `45` for similar operations
- No consistency = unpredictable behavior

### 4. Performance Tuning Difficulty
**Problem:** Hard to experiment with different values
- Want to A/B test retry counts?
- Must modify multiple files
- Difficult to revert if experiment fails
- No centralized configuration

---

## 🎯 Solution Requirements

### Goal: Centralized Constants with Semantic Names

**Backend:** `app/config/constants.py` (ALREADY EXISTS - extend it)  
**Frontend:** `app/frontend/src/config/constants.ts` (ALREADY EXISTS - extend it)

### Requirements:
1. **Extract all magic numbers** to named constants
2. **Add documentation** explaining each value
3. **Group by category** (delays, timeouts, file sizes, etc.)
4. **Use type safety** (dataclasses in Python, const objects in TypeScript)
5. **Replace usage** throughout codebase
6. **No behavior changes** (pure refactor)

---

## 📋 Scope of Work

### Backend Magic Numbers to Extract

**Files with Magic Numbers:**
- `app/services/recording/process_manager.py`
- `app/services/recording/recording_service.py`
- `app/services/events/eventsub_service.py`
- `app/services/cleanup/cleanup_service.py`
- `app/services/notifications/notification_manager.py`
- `app/tasks/background_tasks.py`
- `app/utils/streamlink_utils.py`
- `app/routes/*.py` (pagination limits, timeouts)

**Categories of Magic Numbers:**

1. **Timing Delays (asyncio.sleep):**
   - Error recovery delays
   - Graceful shutdown delays
   - EventSub reconnect delays
   - Polling intervals

2. **Retry Configuration:**
   - Maximum retry attempts
   - Retry delays
   - Exponential backoff multipliers

3. **Timeout Values:**
   - Subprocess timeouts
   - API request timeouts
   - WebSocket timeouts
   - Database query timeouts

4. **File Size Thresholds:**
   - Minimum valid recording size (e.g., 1KB)
   - Large file threshold (e.g., 1GB)
   - Maximum upload size (e.g., 5GB)

5. **Cache Configuration:**
   - Cache sizes (maxsize parameter)
   - TTL (time-to-live) values
   - Debounce intervals

6. **Metadata Limits:**
   - Title max length
   - Description max length
   - Username max length
   - Parsing depth limits

---

### Frontend Magic Numbers to Extract

**Files with Magic Numbers:**
- `app/frontend/src/composables/useStreamers.ts`
- `app/frontend/src/composables/useStreams.ts`
- `app/frontend/src/composables/useCategoryImages.ts`
- `app/frontend/src/components/**/*.vue` (setTimeout, animation durations)
- `app/frontend/src/views/**/*.vue` (pagination, polling)

**Categories of Magic Numbers:**

1. **Image Loading:**
   - Preload counts (how many to preload)
   - Lazy load thresholds (distance from viewport)
   - Image cache sizes

2. **API Configuration:**
   - Default timeouts
   - Retry delays
   - Polling intervals

3. **UI Timing:**
   - Debounce delays (search input, form validation)
   - Toast notification durations
   - Animation durations
   - Transition timings

4. **Pagination:**
   - Default page sizes
   - Maximum results per page
   - Infinite scroll thresholds

---

## 🏗️ Implementation Strategy

### Phase 1: Audit & Identify (30 minutes)

**Search Patterns to Find Magic Numbers:**

**Backend:**
```bash
# Find numeric literals in Python files
grep -rn '\b[0-9]\+\(\.[0-9]\+\)\?\b' app/ --include="*.py" \
  | grep -v 'test_' \
  | grep -v '__pycache__' \
  | grep -E '(sleep|timeout|retry|size|count|delay|limit)' \
  > backend_magic_numbers.txt
```

**Frontend:**
```bash
# Find numeric literals in TypeScript/Vue files
grep -rn '\b[0-9]\+\b' app/frontend/src/ --include="*.ts" --include="*.vue" \
  | grep -E '(setTimeout|setInterval|duration|delay|threshold|limit|count)' \
  > frontend_magic_numbers.txt
```

**Manual Review:**
- Review generated lists
- Identify which numbers should be constants
- Group by category
- Note current usage context

---

### Phase 2: Extend Constants Files (1 hour)

**Backend: Add to `app/config/constants.py`**

**Current Structure (Partial):**
```python
@dataclass(frozen=True)
class AsyncDelays:
    ERROR_RECOVERY_DELAY: float = 5.0
    GRACEFUL_SHUTDOWN_DELAY: float = 2.0
    # ... more delays
```

**Needs to Add:**
- More timing categories
- File size constants
- Metadata length limits
- Polling intervals
- Cache configurations

**Frontend: Add to `app/frontend/src/config/constants.ts`**

**Current Structure (Partial):**
```typescript
export const IMAGE_LOADING = {
  VISIBLE_CATEGORIES_PRELOAD_COUNT: 20,
  LAZY_LOAD_THRESHOLD: 100,
} as const
```

**Needs to Add:**
- UI timing constants
- Debounce delays
- Toast durations
- Pagination limits
- API timeouts

---

### Phase 3: Replace Usage (1.5-2 hours)

**Process:**
1. Import constants at top of file
2. Replace magic number with named constant
3. Verify no behavior changes (tests still pass)
4. Commit per-file or per-category

**Files to Update (Backend):**
- ~15-20 Python files

**Files to Update (Frontend):**
- ~10-15 TypeScript/Vue files

---

### Phase 4: Verification (30 minutes)

**Checklist:**
- [ ] All tests pass (no behavior changes)
- [ ] Build succeeds (no import errors)
- [ ] Application starts correctly
- [ ] No regressions in functionality
- [ ] Code review for missed magic numbers

---

## ✅ Acceptance Criteria

### Code Quality
- [ ] All magic numbers extracted to constants files
- [ ] Constants grouped by category (delays, timeouts, sizes, etc.)
- [ ] Each constant has documentation comment explaining purpose
- [ ] Constants use semantic names (ERROR_RECOVERY_DELAY not DELAY_1)
- [ ] Type safety maintained (dataclasses, const objects)

### Maintainability
- [ ] Single source of truth for all numeric constants
- [ ] Easy to find and modify values
- [ ] Consistent naming conventions
- [ ] Clear categories and organization

### No Regressions
- [ ] All existing tests pass
- [ ] Application behavior unchanged
- [ ] No performance degradation
- [ ] No new imports break anything

### Documentation
- [ ] Each constant has comment explaining:
  - What it controls
  - Why this value was chosen
  - Units (seconds, bytes, milliseconds, etc.)

---

## 🧪 Testing Requirements

### Automated Testing
```bash
# Backend: Run full test suite
pytest tests/ -v

# Frontend: Build and type-check
cd app/frontend
npm run build
npm run type-check
```

### Manual Verification
- [ ] Application starts successfully
- [ ] Error recovery delays still work
- [ ] Retry logic still functions
- [ ] File size validations still apply
- [ ] UI animations still smooth
- [ ] Toast notifications still appear/disappear correctly

### Regression Checklist
- [ ] Recording process still works
- [ ] EventSub reconnection still works
- [ ] Cleanup service still runs
- [ ] Notifications still send
- [ ] WebSocket polling still functions
- [ ] Image preloading still works

---

## 📖 References

**Existing Constants Files:**
- `app/config/constants.py` - Backend constants (ALREADY EXISTS)
- `app/frontend/src/config/constants.ts` - Frontend constants (ALREADY EXISTS)

**Project Documentation:**
- `docs/MASTER_TASK_LIST.md` - Task #9 (Extract Magic Numbers)
- `.github/instructions/backend.instructions.md` - Backend patterns
- `.github/instructions/frontend.instructions.md` - Frontend patterns

**Related Issues:**
- Issue #7: Optimize N+1 Queries (performance tuning)
- Issue #2: Multi-Proxy System (timeout configurations)

---

## 📋 Implementation Tasks

### 1. Backend Constants Extraction (2 hours)

**File:** `app/config/constants.py` (ALREADY EXISTS - extend it)

**Current Structure:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class AsyncDelays:
    """Timing delays for async operations"""
    ERROR_RECOVERY_DELAY: float = 5.0  # Wait after error before retry
    GRACEFUL_SHUTDOWN_DELAY: float = 2.0
    EVENTSUB_RECONNECT_DELAY: float = 1.0

@dataclass(frozen=True)
class RetryConfig:
    """Retry attempt configuration"""
    DEFAULT_MAX_RETRIES: int = 3
    TWITCH_API_RETRIES: int = 5
    
@dataclass(frozen=True)
class Timeouts:
    """Timeout values in seconds"""
    SUBPROCESS_TIMEOUT: int = 30
    GRACEFUL_SHUTDOWN: int = 30
    
@dataclass(frozen=True)
class CacheConfig:
    """Cache sizing and TTL"""
    DEFAULT_CACHE_SIZE: int = 1000
    NOTIFICATION_DEBOUNCE_TTL: int = 300  # 5 minutes

@dataclass(frozen=True)
class FileSizeThresholds:
    """File size limits in bytes"""
    MIN_VALID_FILE_SIZE: int = 1024  # 1KB
    LARGE_FILE_THRESHOLD: int = 1073741824  # 1GB
    MAX_UPLOAD_SIZE: int = 5368709120  # 5GB

ASYNC_DELAYS = AsyncDelays()
RETRY_CONFIG = RetryConfig()
TIMEOUTS = Timeouts()
CACHE_CONFIG = CacheConfig()
FILE_SIZE_THRESHOLDS = FileSizeThresholds()
```

**Find and Replace:**

```bash
# Find all magic numbers in backend
grep -rn '\b[0-9]\+\(\.[0-9]\+\)\?\b' app/ --include="*.py" | \
  grep -v 'test_' | \
  grep -v '__pycache__' | \
  grep -E '(sleep|timeout|retry|size|count|delay)' > magic_numbers_backend.txt
```

**Example Refactoring:**

**Before:**
```python
# app/services/recording/process_manager.py
await asyncio.sleep(5.0)  # Wait after error
max_retries = 3
timeout = 30
```

**After:**
```python
from app.config.constants import ASYNC_DELAYS, RETRY_CONFIG, TIMEOUTS

await asyncio.sleep(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)
max_retries = RETRY_CONFIG.DEFAULT_MAX_RETRIES
timeout = TIMEOUTS.SUBPROCESS_TIMEOUT
```

**Files to Update:**
- `app/services/recording/process_manager.py`
- `app/services/recording/recording_service.py`
- `app/services/events/eventsub_service.py`
- `app/services/cleanup/cleanup_service.py`
- `app/services/notifications/notification_manager.py`
- `app/tasks/background_tasks.py`

---

### 2. Frontend Constants Extraction (1-2 hours)

**File:** `app/frontend/src/config/constants.ts` (ALREADY EXISTS - extend it)

**Current Structure:**
```typescript
/**
 * Image Loading Configuration
 */
export const IMAGE_LOADING = {
  /** Number of visible categories to preload images for */
  VISIBLE_CATEGORIES_PRELOAD_COUNT: 20,
  
  /** Threshold for lazy loading (pixels from viewport) */
  LAZY_LOAD_THRESHOLD: 100,
} as const

/**
 * API Configuration
 */
export const API = {
  /** Default API request timeout (ms) */
  DEFAULT_TIMEOUT: 30000,
  
  /** WebSocket reconnect delay (ms) */
  WS_RECONNECT_DELAY: 3000,
} as const

/**
 * UI Configuration
 */
export const UI = {
  /** Search input debounce delay (ms) */
  SEARCH_DEBOUNCE_MS: 300,
  
  /** Toast notification duration (ms) */
  TOAST_DURATION_MS: 3000,
  
  /** Modal animation duration (ms) */
  MODAL_ANIMATION_MS: 200,
  
  /** Auto-hide success message delay (ms) */
  AUTO_HIDE_SUCCESS_MS: 5000,
} as const
```

**Find and Replace:**

```bash
# Find magic numbers in frontend
grep -rn '\b[0-9]\+\b' app/frontend/src --include="*.ts" --include="*.vue" | \
  grep -E '(setTimeout|setInterval|debounce|duration|delay|threshold)' > magic_numbers_frontend.txt
```

**Example Refactoring:**

**Before:**
```typescript
// useCategoryImages.ts
const VISIBLE_CATEGORIES_PRELOAD_COUNT = 20  // Duplicate definition!

// useStreamers.ts
setTimeout(() => refresh(), 300)  // Debounce unclear
```

**After:**
```typescript
import { IMAGE_LOADING, UI } from '@/config/constants'

const preloadCount = IMAGE_LOADING.VISIBLE_CATEGORIES_PRELOAD_COUNT

setTimeout(() => refresh(), UI.SEARCH_DEBOUNCE_MS)
```

**Files to Update:**
- `app/frontend/src/composables/useCategoryImages.ts`
- `app/frontend/src/composables/useStreamers.ts`
- `app/frontend/src/composables/useToast.ts`
- `app/frontend/src/components/modals/*.vue` (animation durations)
- `app/frontend/src/views/*.vue` (any setTimeout calls)

---

### 3. Documentation (30 minutes)

**Update Backend Instructions:**

**File:** `.github/instructions/backend.instructions.md`

Add section:
```markdown
## Constants Management

**CRITICAL**: Never use magic numbers in code.

**Rule:** If a number has meaning, extract it to `app/config/constants.py`

### When to Extract:
- ✅ Timing delays (sleep, timeout, debounce)
- ✅ Retry counts and intervals
- ✅ File size thresholds
- ✅ Cache sizes and TTL values
- ✅ Buffer sizes
- ✅ Polling intervals

### When NOT to Extract:
- ❌ Loop indices (i = 0, range(10))
- ❌ Mathematical constants (x / 2, + 1)
- ❌ HTTP status codes (200, 404)
- ❌ Single-use local calculations

### Usage Pattern:
```python
from app.config.constants import ASYNC_DELAYS, TIMEOUTS

await asyncio.sleep(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)
```
```

**Update Frontend Instructions:**

**File:** `.github/instructions/frontend.instructions.md`

Add section:
```markdown
## Constants Management

**CRITICAL**: Extract all timing, threshold, and configuration values to constants.

### Frontend Constants Location:
`app/frontend/src/config/constants.ts`

### Categories:
- **IMAGE_LOADING**: Preload counts, lazy load thresholds
- **API**: Timeouts, retry delays, WebSocket config
- **UI**: Debounce, animation duration, toast timings

### Usage:
```typescript
import { UI, API } from '@/config/constants'

setTimeout(() => search(), UI.SEARCH_DEBOUNCE_MS)
const timeout = API.DEFAULT_TIMEOUT
```
```

---

## 📂 Files to Modify

**Backend:**
- `app/config/constants.py` (extend existing dataclasses)
- `app/services/recording/process_manager.py`
- `app/services/recording/recording_service.py`
- `app/services/events/eventsub_service.py`
- `app/services/cleanup/cleanup_service.py`
- `app/services/notifications/notification_manager.py`
- `app/tasks/background_tasks.py`

**Frontend:**
- `app/frontend/src/config/constants.ts` (extend existing)
- `app/frontend/src/composables/useCategoryImages.ts`
- `app/frontend/src/composables/useStreamers.ts`
- `app/frontend/src/composables/useToast.ts`
- `app/frontend/src/components/**/*.vue` (timeouts, durations)

**Documentation:**
- `.github/instructions/backend.instructions.md`
- `.github/instructions/frontend.instructions.md`

---

## ✅ Acceptance Criteria

**Backend:**
- [ ] All sleep/delay values use `ASYNC_DELAYS`
- [ ] All retry counts use `RETRY_CONFIG`
- [ ] All timeouts use `TIMEOUTS`
- [ ] All file size checks use `FILE_SIZE_THRESHOLDS`
- [ ] All cache configs use `CACHE_CONFIG`
- [ ] No magic numbers in services (search `await asyncio.sleep([0-9])`)

**Frontend:**
- [ ] All setTimeout/setInterval use `UI.*_MS` constants
- [ ] All API timeouts use `API.DEFAULT_TIMEOUT`
- [ ] All debounce delays use `UI.SEARCH_DEBOUNCE_MS`
- [ ] All animation durations use `UI.*_ANIMATION_MS`
- [ ] No duplicate constant definitions across files

**Documentation:**
- [ ] Backend instructions updated with constants guide
- [ ] Frontend instructions updated with constants guide
- [ ] Constants files have JSDoc/docstrings explaining each value
- [ ] Commit message documents all extracted constants

**Code Quality:**
- [ ] No regressions (all tests pass)
- [ ] Constants grouped logically by category
- [ ] Naming is descriptive and consistent
- [ ] Type safety maintained (TypeScript, Python type hints)

---

## 🧪 Testing Checklist

**Backend Testing:**
```bash
# Verify no magic numbers remain
grep -rn 'asyncio.sleep([0-9])' app/services/

# Check constants file syntax
python -c "from app.config.constants import *; print(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)"

# Run tests
pytest tests/ -v
```

**Frontend Testing:**
```bash
# Verify no magic setTimeout values
grep -rn 'setTimeout.*[0-9]\{3,\}' app/frontend/src/

# Check constants file syntax
cd app/frontend
npm run type-check

# Build succeeds
npm run build
```

**Functional Testing:**
- [ ] Recording delays work as before
- [ ] Retry logic unchanged
- [ ] WebSocket reconnect timing correct
- [ ] UI animations smooth
- [ ] Toast notifications display correct duration

**Edge Cases:**
- [ ] Imports work correctly
- [ ] Constants are immutable (frozen dataclasses, `as const`)
- [ ] Type hints correct
- [ ] No circular import issues

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md` (Task #7)  
**Backend Guide:** `.github/instructions/backend.instructions.md`  
**Frontend Guide:** `.github/instructions/frontend.instructions.md`  
**Constants Files:** `app/config/constants.py`, `app/frontend/src/config/constants.ts`

---

## 🤖 Copilot Instructions

**Context:**
Extract magic numbers from codebase to centralized constants files for maintainability. Currently ~30+ magic numbers scattered across backend and frontend making code hard to maintain and tune.

**Critical Patterns:**
1. **Backend constant usage:**
   ```python
   from app.config.constants import ASYNC_DELAYS
   await asyncio.sleep(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)
   ```

2. **Frontend constant usage:**
   ```typescript
   import { UI } from '@/config/constants'
   setTimeout(() => {}, UI.SEARCH_DEBOUNCE_MS)
   ```

3. **Dataclass pattern (Backend):**
   ```python
   @dataclass(frozen=True)  # Immutable
   class AsyncDelays:
       ERROR_RECOVERY_DELAY: float = 5.0  # Comment explaining value
   ```

4. **As const pattern (Frontend):**
   ```typescript
   export const UI = {
     DEBOUNCE_MS: 300,  // Comment
   } as const  // Type safety
   ```

**Strategy:**
1. Search for magic numbers: `grep -rn '\b[0-9]\+\b'`
2. Identify meaningful values (ignore loop indices, math)
3. Group by category (delays, timeouts, sizes, etc.)
4. Add to appropriate constants file
5. Replace usage throughout codebase
6. Update documentation

**Files to Read First:**
- `app/config/constants.py` (see existing structure)
- `app/frontend/src/config/constants.ts` (see existing categories)
- `.github/copilot-instructions.md` (Constants sections)

**Testing Strategy:**
1. Verify all imports work
2. Run full test suite (no regressions)
3. Build frontend successfully
4. Test key workflows (recording, WebSocket, UI interactions)
5. Search codebase for remaining magic numbers

**Success Criteria:**
All magic numbers extracted to constants, grouped logically, documented with comments, no behavioral changes, tests pass.

**Common Pitfalls:**
- ❌ Extracting loop indices (i = 0) - don't do this
- ❌ Extracting mathematical operations (x / 2) - keep inline
- ❌ Missing imports after extraction
- ❌ Not using `as const` in TypeScript (loses type safety)
- ❌ Not freezing dataclasses in Python (allows mutation)
- ❌ Forgetting to document *why* a value is what it is
