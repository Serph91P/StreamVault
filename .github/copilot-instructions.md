# StreamVault - Copilot Instructions

## Project Overview

StreamVault is a self-hosted Twitch stream recording application built with Python FastAPI (backend) and Vue 3 TypeScript (frontend). It automatically records live streams, manages metadata, and provides a Progressive Web App (PWA) interface for stream management.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL, Streamlink
- Frontend: Vue 3, TypeScript, Composition API, SCSS
- Architecture: REST API + WebSocket, Background task queues

## Repository Structure

```
app/
├── api/              # API endpoints and routes
├── services/         # Business logic (recording, cleanup, metadata)
├── models.py         # SQLAlchemy database models
├── frontend/
│   ├── src/
│   │   ├── components/  # Vue components
│   │   ├── views/       # Page views
│   │   ├── styles/      # SCSS design system
│   │   ├── composables/ # Reusable Vue logic
│   │   └── services/    # API clients
migrations/           # Database migration scripts
docker/              # Docker configuration
docs/                # Project documentation
```

## 🏗️ Backend Architecture

**For complete production architecture documentation, see:** [**ARCHITECTURE.md**](.github/ARCHITECTURE.md)

**Key Topics Covered:**
- **Recording Flow:** EventSub → Streamlink → Post-Processing
- **Concurrent Processing:** Multi-threaded recording management
- **Segment Rotation:** Automatic 24h segment splitting for long streams
- **Recovery Mechanisms:** Zombie state cleanup, startup resumption
- **Notification System:** Profile image handling, external service integration
- **Database Patterns:** Properties vs columns, eager loading, timezone handling

**Quick Reference - Critical Production Patterns:**
1. **Duplicate Prevention:** Always check `state_manager.get_active_recording()` before starting
2. **Fail-Forward Cleanup:** Use `finally` blocks + `.pop(key, None)` for process cleanup
3. **Zombie Detection:** Startup cleanup for stale `status='recording'` entries
4. **Timezone Awareness:** Use `datetime.now(timezone.utc)` for all timestamps
5. **Profile Images:** Always use HTTP URLs for notifications (no local paths)

## Commit Message Convention

**CRITICAL**: This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic semantic versioning.

**LANGUAGE REQUIREMENT**: All commit messages **MUST** be written in **English** for international collaboration and understanding.

### Commit Message Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**❌ WRONG (German):**
```
feat: füge YouTube Recording hinzu
refactor: eliminiere hardcoded Colors
docs: erstelle Design-System Dokumentation
```

**✅ CORRECT (English):**
```
feat: add YouTube recording support
refactor: eliminate hardcoded colors in components
docs: create design system documentation
```

### Commit Types and Version Impact

When generating commit messages, **ALWAYS** use these prefixes:

#### Minor Version Bump (1.0.x → 1.1.0) - Use for:
- `feat:` - New features
- `feature:` - New features (alternative)
- `add:` - Adding new functionality
- `refactor:` - Code refactoring/restructuring
- `perf:` - Performance improvements

#### Patch Version Bump (1.0.0 → 1.0.1) - Use for:
- `fix:` - Bug fixes
- `bugfix:` - Bug fixes (alternative)
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks, dependency updates
- `style:` - Code formatting, no logic changes
- `test:` - Adding or updating tests
- `ci:` - CI/CD pipeline changes

#### Major Version Bump (1.x.x → 2.0.0) - Use for:
- `BREAKING CHANGE:` in commit body
- `<type>!:` - Any type with ! suffix (e.g., `feat!:`)

### Examples for Common Scenarios

#### Adding a new feature:
```
feat: add automatic YouTube recording support

- Implemented YouTube API integration
- Added quality selection for YouTube streams
- Updated UI with YouTube platform option
```

#### Improving code quality:
```
refactor: optimize database queries and fix memory leaks

- Fixed 31 bare except blocks with specific exception handling
- Optimized 18 N+1 queries using joinedload()
- Replaced unbounded dicts with TTLCache to prevent memory leaks
- Centralized 30+ magic numbers in configuration

New Dependencies: cachetools==5.5.0
```

#### Fixing a bug:
```
fix: resolve memory leak in notification manager

The notification debounce dictionary was growing unboundedly.
Replaced with TTLCache with 5-minute expiration.
```

#### Updating dependencies:
```
chore: update Python dependencies

- Updated FastAPI to 0.110.0
- Updated SQLAlchemy to 2.0.27
- Updated all security patches
```

#### Breaking changes:
```
feat!: migrate to PostgreSQL 16

BREAKING CHANGE: Minimum PostgreSQL version is now 16.0
Users must upgrade their database before updating StreamVault.

Migration guide: docs/upgrade-pg16.md
```

### Scopes (Optional but Recommended)

Use scopes to indicate which part of the codebase is affected:

```
feat(api): add new recording endpoints
fix(ui): resolve dashboard loading issue
perf(db): add database indexes for streams table
docs(docker): update compose examples
chore(deps): update Python dependencies
```

### Rules for Copilot

1. **ALWAYS** analyze the changes first to determine the correct type
2. **PREFER** `refactor:` over `fix:` for code quality improvements
3. **USE** `feat:` for any new functionality, not just user-facing features
4. **USE** multiline commits for complex changes (body + footer)
5. **MENTION** breaking changes explicitly with `BREAKING CHANGE:`
6. **LIST** new dependencies in the commit body
7. **REFERENCE** issue numbers with `Fixes #123` or `Closes #456`

### Common Patterns in StreamVault

#### Code Quality Improvements → `refactor:`
```
refactor: improve exception handling in recording service

- Replaced bare except with specific exception types
- Added proper error logging with context
- Improved error recovery logic
```

#### Database Optimizations → `perf:`
```
perf: optimize stream queries with eager loading

- Added joinedload() for Stream.streamer relationships
- Reduced N+1 queries from 30 to 1
- 50-70% faster API response times
```

#### Docker/Infrastructure → `chore:` or `ci:`
```
chore(docker): optimize image build process

- Multi-stage build reduces image size by 40%
- Fixed Windows CRLF line ending issues
- Improved layer caching
```

#### Bug Fixes → `fix:`
```
fix: resolve recording status persistence issue

Recording states were not properly restored after restart.
Added state persistence service with graceful recovery.

Fixes #234
```

### What NOT to do

❌ **Bad:**
```
update stuff
changes
wip
fixed things
```

✅ **Good:**
```
feat: add thumbnail generation service
fix: resolve memory leak in event handler
refactor: extract configuration constants
chore: update Docker base image
```

## Path-Specific Instructions

This repository uses path-specific instructions for detailed guidelines:

- **Frontend**: See `.github/instructions/frontend.instructions.md` for Vue/TypeScript/SCSS guidelines
- **Backend**: See `.github/instructions/backend.instructions.md` for Python/FastAPI patterns
- **API**: See `.github/instructions/api.instructions.md` for endpoint design
- **Migrations**: See `.github/instructions/migrations.instructions.md` for database changes
- **Docker**: See `.github/instructions/docker.instructions.md` for containerization

## Documentation Language Policy

**CRITICAL**: All documentation and commit messages **MUST** be written in **English** for international collaboration.

### What MUST be in English:
- ✅ **Commit messages** - All types (feat, fix, refactor, docs, etc.)
- ✅ **Code comments** - Inline comments, docstrings, JSDoc
- ✅ **Documentation files** - README, ARCHITECTURE, design docs
- ✅ **Git commit bodies** - Detailed explanations, breaking changes
- ✅ **TODO comments** - In-code task markers
- ✅ **Error messages** - User-facing and developer-facing

### Examples:

**❌ WRONG (German):**
```typescript
// Prüfe ob Benutzer eingeloggt ist
if (!user) {
  throw new Error('Benutzer nicht gefunden')
}

/**
 * Lädt alle Streamer aus der Datenbank
 * @returns Liste von Streamern
 */
```

**✅ CORRECT (English):**
```typescript
// Check if user is logged in
if (!user) {
  throw new Error('User not found')
}

/**
 * Loads all streamers from database
 * @returns List of streamers
 */
```

### Rationale:
- **International collaboration** - Contributors worldwide can understand code
- **Industry standard** - English is lingua franca of software development
- **Tooling support** - Better IDE/AI support for English documentation
- **Future-proofing** - Easy onboarding for non-German speakers

## Security Guidelines - CRITICAL

### ⚠️ MANDATORY SECURITY REQUIREMENTS

**ALWAYS** apply these security checks when working with file paths, user input, or external data:

#### � Session Authentication - credentials:'include' (CRITICAL)

**CRITICAL RULE**: ALL fetch() calls MUST include `credentials: 'include'` to send session cookies!

**Why this is critical:**
- HTTP cookies (session tokens) are NOT sent by default in fetch() requests
- Without `credentials: 'include'`, the browser doesn't send the session cookie
- Backend returns 401 Unauthorized → Empty data → TypeErrors on array operations

**Symptoms of missing credentials:**
```javascript
// 401 errors in console
Failed to fetch streamers status {}
Failed to fetch streams status {}
TypeError: v.value.filter is not a function  // Empty {} instead of []
```

**ALWAYS include credentials in ALL fetch calls:**

```typescript
// ✅ CORRECT: Login/Auth endpoints
const response = await fetch('/auth/login', {
  method: 'POST',
  credentials: 'include',  // CRITICAL!
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
})

// ✅ CORRECT: API endpoints (GET)
const response = await fetch('/api/streamers', {
  credentials: 'include'  // CRITICAL!
})

// ✅ CORRECT: API endpoints (POST/PUT/DELETE)
const response = await fetch('/api/settings', {
  method: 'POST',
  credentials: 'include',  // CRITICAL!
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data)
})

// ✅ CORRECT: Router auth guards
const authResponse = await fetch('/auth/check', {
  credentials: 'include',  // CRITICAL!
  headers: { 'X-Requested-With': 'XMLHttpRequest' }
})
```

**❌ NEVER omit credentials:**
```typescript
// ❌ WRONG: No credentials = No session cookie sent
await fetch('/api/streamers')  // Returns 401!

// ❌ WRONG: Will fail auth even after successful login
await fetch('/api/settings', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
  // Missing credentials: 'include'!
})
```

**Checklist for new API calls:**
- [ ] Added `credentials: 'include'` to fetch options
- [ ] Tested login → API call → Data loads
- [ ] Tested page refresh → Session persists
- [ ] No 401 errors in dev console
- [ ] No TypeErrors on .filter()/.sort() (empty data)

**Login Redirect Pattern:**
```typescript
// ✅ CORRECT: Delay before redirect to ensure cookie persistence
if (response.ok) {
  await new Promise(resolve => setTimeout(resolve, 100))
  window.location.href = '/'  // Full page reload with session
}

// ❌ WRONG: Immediate redirect can cause blank page
if (response.ok) {
  window.location.href = '/'  // Cookie not yet persisted!
}
```

**Affected Files Checklist:**
- ✅ `LoginView.vue` - Login request
- ✅ `router/index.ts` - /auth/check, /auth/setup
- ✅ `useAuth.ts` - Auth composable
- ✅ `useSystemAndRecordingStatus.ts` - All status endpoints
- ✅ `useStreamers.ts` - Streamer CRUD
- ✅ `useStreams.ts` - Stream history
- ✅ `useRecordingSettings.ts` - Recording config (11 calls!)
- ✅ `useNotificationSettings.ts` - Notification config
- ✅ `usePWA.ts` - Push notifications
- ✅ `useBackgroundQueue.ts` - Task management
- ✅ `useCategoryImages.ts` - Image fetching
- ✅ `useFilenamePresets.ts` - Filename templates

**Related Issues:**
- Commits: c37d167f (initial fix), 06bc13b1 (composables), 66b90ced (login delay)
- Production bug: Empty Home/Streamers/Settings after login
- Root cause: 41 fetch() calls missing credentials flag

#### �🔒 Path Traversal Prevention (CRITICAL)
All file path operations MUST be validated against path traversal attacks:

```python
import os
from app.config.settings import get_settings

# ALWAYS validate user-provided paths
def validate_path_security(user_path: str, operation_type: str = "access") -> str:
    """
    SECURITY: Validate path against traversal attacks
    Returns normalized, validated path or raises exception
    """
    settings = get_settings()
    safe_base = os.path.realpath(settings.RECORDING_DIRECTORY)
    
    try:
        # Normalize and resolve the path
        normalized_path = os.path.realpath(os.path.abspath(user_path))
    except (OSError, ValueError) as e:
        logger.error(f"🚨 SECURITY: Invalid path provided: {user_path} - {e}")
        raise HTTPException(status_code=400, detail=f"Invalid path: {user_path}")
    
    # CRITICAL: Ensure path is within safe directory
    if not normalized_path.startswith(safe_base + os.sep) and normalized_path != safe_base:
        logger.error(f"🚨 SECURITY: Path traversal blocked: {user_path} -> {normalized_path}")
        raise HTTPException(status_code=403, detail="Access denied: Path outside allowed directory")
    
    # Verify path exists for operations that require it
    if operation_type in ["read", "write", "delete"] and not os.path.exists(normalized_path):
        raise HTTPException(status_code=404, detail=f"Path not found: {user_path}")
    
    return normalized_path
```

#### 🛡️ NEVER DO - Security Anti-Patterns
```python
# ❌ NEVER: Direct path operations with user input
os.walk(user_provided_path)                    # Path traversal vulnerability
os.path.join(base, user_input)                # Can be bypassed with ../
open(user_filename, 'w')                      # Arbitrary file access
shutil.rmtree(user_directory)                 # Directory traversal risk

# ❌ NEVER: Unsanitized SQL queries
cursor.execute(f"SELECT * FROM {user_table}")  # SQL injection
query = "WHERE name = " + user_input           # SQL injection

# ❌ NEVER: Eval or exec with user data  
eval(user_code)                                # Code injection
exec(user_script)                              # Remote code execution
```

#### ✅ ALWAYS DO - Security Best Practices
```python
# ✅ ALWAYS: Validate paths before operations
safe_path = validate_path_security(user_path, "read")
with open(safe_path, 'r') as f:
    content = f.read()

# ✅ ALWAYS: Use parameterized queries
session.query(Stream).filter(Stream.name == user_input)
cursor.execute("SELECT * FROM streams WHERE name = %s", (user_input,))

# ✅ ALWAYS: Sanitize user input
import html
safe_html = html.escape(user_input)
safe_filename = re.sub(r'[^\w\-_\.]', '_', user_filename)

# ✅ ALWAYS: Validate file extensions
ALLOWED_EXTENSIONS = {'.mp4', '.mkv', '.ts', '.m3u8'}
if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
    raise ValueError("Invalid file type")
```

### 🔐 Input Validation Requirements

#### API Endpoints - MANDATORY Validation
```python
# BEST PRACTICE: Don't accept file paths as parameters at all
@router.post("/admin/cleanup")
async def cleanup_files():
    # SECURITY: Use configured directory, no user input
    from app.config.settings import get_settings
    safe_path = get_settings().RECORDING_DIRECTORY
    return await cleanup_service.cleanup_files(safe_path)

# If you MUST accept paths, validate thoroughly
@router.post("/admin/process-file")
async def process_file(file_path: str = Query(...)):
    # SECURITY: Always validate before processing
    safe_path = validate_path_security(file_path, "read")
    return await file_service.process(safe_path)

# For file uploads
@router.post("/upload")  
async def upload_file(file: UploadFile):
    # SECURITY: Validate file type and size
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large")
    
    safe_filename = secure_filename(file.filename)
    if not safe_filename:
        raise HTTPException(400, "Invalid filename")
```

#### Database Queries - SQL Injection Prevention
```python
# ✅ ALWAYS: Use SQLAlchemy ORM or parameterized queries
streams = session.query(Stream).filter(
    Stream.streamer_name.ilike(f"%{search_term}%")  # Safe with ORM
).all()

# ✅ For raw SQL (avoid when possible)
cursor.execute(
    "SELECT * FROM streams WHERE created_at > %s", 
    (start_date,)
)
```

### 🔍 Security Code Review Checklist

Before committing ANY code that handles:

- [ ] **File paths**: Applied `validate_path_security()` 
- [ ] **User input**: Sanitized and validated all parameters
- [ ] **File operations**: Confirmed paths are within safe directories
- [ ] **Database queries**: Used ORM or parameterized queries
- [ ] **API endpoints**: Added input validation and proper error handling
- [ ] **External commands**: Avoided shell injection with proper escaping
- [ ] **File uploads**: Validated file types, sizes, and filenames
- [ ] **Configuration**: No secrets in code, used environment variables

### 🚨 Security Incident Response

If you discover a security vulnerability:

1. **DO NOT** commit the fix to main branch immediately
2. **CREATE** a security branch: `security/fix-description`
3. **ADD** detailed security impact assessment to commit message
4. **TEST** the fix thoroughly in isolated environment
5. **REFERENCE** this pattern in commit:

```
security: fix path traversal in cleanup service

SECURITY IMPACT: High - Remote file access outside recordings directory
VULNERABILITY: CWE-22 Path Traversal via recordings_root parameter
ATTACK VECTOR: Admin API endpoint accepting arbitrary file paths

- Added path normalization and containment validation
- Implemented safe base directory checking
- Added security logging for blocked attempts

Testing: Verified ../../../etc/passwd attacks are blocked
Affects: All cleanup endpoints accepting file paths
```

## 📝 Documentation & Learning Protocol

**CRITICAL**: After fixing production bugs or discovering new patterns, **ALWAYS** document lessons learned.

### When to Update Instructions
Update `.github/instructions/*.instructions.md` when you:

1. **Fix a production bug** → Document the root cause and prevention pattern
2. **Discover a missing pattern** → Add to Common Patterns section
3. **Find a framework quirk** → Document the workaround
4. **Resolve a silent failure** → Add validation requirement
5. **Implement a duplicate check** → Add to duplicate prevention patterns
6. **Add startup cleanup** → Document zombie state detection

### Documentation Workflow

```
Production Bug → Root Cause Analysis → Pattern Extraction → Documentation Update
```

**Example:**
```
Bug: WebSocket connections fail with "WebSocketState is not defined"
Root Cause: Missing import from starlette.websockets
Pattern: Always verify ALL required imports for library features
Documentation: → backend.instructions.md "Missing Import Prevention" section
```

### What to Document

**In `backend.instructions.md`:**
- Production patterns (duplicate prevention, zombie cleanup, startup validation)
- Framework-specific requirements (imports, configuration, dependencies)
- Silent failure prevention (connectivity checks, validation)
- State management patterns

**In `frontend.instructions.md`:**
- Component patterns
- State management anti-patterns
- PWA-specific requirements
- Mobile-first gotchas

**In `security.instructions.md`:**
- Security vulnerabilities discovered
- Attack vectors found in code review
- Validation requirements

**In `copilot-instructions.md`:**
- Meta-patterns (like this documentation protocol)
- Cross-cutting concerns
- Project-wide standards

### Self-Improvement Loop

```
1. Encounter problem
2. Solve problem
3. Extract pattern
4. Document pattern
5. Apply pattern proactively in future
```

This creates institutional knowledge that persists across sessions.

## Key Principles

### Backend
- Use type hints and specific exception types  
- Eager load relationships with `joinedload()` to avoid N+1 queries
- Services should be stateless; use dependency injection
- **NO MAGIC NUMBERS**: Extract all constants to `app/config/constants.py` (see Constants section)
- **BREAKING CHANGES**: Document behavior changes in comments and commit messages
- **EXTERNAL SERVICE FAILURES**: Always check connectivity before using external services (proxies, APIs)
- **FAIL FAST**: Validate preconditions early, don't let processes silently fail
- **MISSING IMPORTS**: Verify ALL imports when using framework features (WebSocketState, etc.)
- **DUPLICATE PREVENTION**: Check for existing operations before starting new ones
- **STARTUP CLEANUP**: Clean zombie/stale state on application startup
- **SECURITY**: Always validate file paths and user input
- **SECURITY**: Use parameterized queries, never string concatenation

### Backend Constants (`app/config/constants.py`)

**CRITICAL**: All magic numbers, timeouts, and thresholds MUST be extracted to constants:

```python
from app.config.constants import (
    ASYNC_DELAYS,         # Sleep times, polling intervals
    RETRY_CONFIG,         # Retry counts and delays
    TIMEOUTS,             # Subprocess, API, process timeouts
    CACHE_CONFIG,         # Cache sizes and TTL values
    FILE_SIZE_THRESHOLDS, # File size limits in bytes
    METADATA_CONFIG       # Parsing depth limits
)

# Usage examples:
await asyncio.sleep(ASYNC_DELAYS.ERROR_RECOVERY_DELAY)  # 5.0s
max_retries = RETRY_CONFIG.DEFAULT_MAX_RETRIES          # 3
timeout = TIMEOUTS.GRACEFUL_SHUTDOWN                    # 30s
cache = TTLCache(
    maxsize=CACHE_CONFIG.DEFAULT_CACHE_SIZE,            # 1000
    ttl=CACHE_CONFIG.NOTIFICATION_DEBOUNCE_TTL          # 300s
)
```

**When adding constants:**
- Choose appropriate dataclass (ASYNC_DELAYS, RETRY_CONFIG, etc.)
- Add descriptive comment explaining the value
- Use semantic names (e.g., `ERROR_RECOVERY_DELAY` not `DELAY_5`)
- Update `backend.instructions.md` if adding new category

### Frontend (PWA - Mobile-First)
- Use Composition API with `<script setup lang="ts">`
- **NEVER** override global `.btn` or `.status-border-*` classes
- All tables must transform to cards on mobile
- Use SCSS variables from `_variables.scss`
- Touch targets: minimum 44x44px
- **NO MAGIC NUMBERS**: Extract timing delays, thresholds, and limits to `app/frontend/src/config/constants.ts`
- **USE VUE LIFECYCLE**: Prefer `nextTick()` over `setTimeout()` for deferred operations
- **SECURITY**: Sanitize all user input before display
- **SECURITY**: Validate file uploads on client and server side

### Frontend Styling - CRITICAL Rules

**⚠️ MANDATORY: Work in Global SCSS Files, NOT Per-Component!**

When fixing styling issues (font sizes, input styles, spacing, touch targets, etc.), **ALWAYS** make changes in global SCSS files:

**Global SCSS Files:**
- `app/frontend/src/styles/main.scss` - Base HTML elements (input, button, a, body, html)
- `app/frontend/src/styles/_variables.scss` - Design tokens (colors, spacing, typography, breakpoints)
- `app/frontend/src/styles/_mixins.scss` - Reusable patterns (breakpoints, flex-center, truncate-text)
- `app/frontend/src/styles/_utilities.scss` - Utility classes (.text-center, .mt-4, .flex, .grid)

**Decision Rule:**
- Pattern used in **3+ components**? → Use global SCSS
- Affects **base HTML elements** (input, button, select)? → Add to `main.scss`
- Is a **design token** (color, spacing, border-radius)? → Use `_variables.scss`
- Is **responsive/accessibility** (iOS zoom, touch targets)? → Use breakpoint mixins in `main.scss`

**Examples:**

❌ **WRONG - Per-Component Fixes:**
```scss
// LoginView.vue - DON'T DO THIS
input { font-size: 16px; }  // iOS zoom prevention

// SetupView.vue - DON'T DO THIS
input { font-size: 16px; }  // Same fix repeated!

// AddStreamerView.vue - DON'T DO THIS
input { font-size: 16px; }  // Duplicated 3rd time!
```

✅ **CORRECT - Global Fix:**
```scss
// app/frontend/src/styles/main.scss - DO THIS
input, select, textarea {
  @include m.respond-below('md') {  // < 768px (mobile)
    font-size: 16px !important;  // iOS zoom prevention - applies globally
  }
}
```

**Result**: Fixed everywhere automatically! All inputs in LoginView, SetupView, AddStreamerView, Settings, etc.

**See `.github/instructions/frontend.instructions.md` → "Global SCSS Changes" section for complete guide.**

### Frontend Constants (`app/frontend/src/config/constants.ts`)

**CRITICAL**: All magic numbers, delays, and thresholds MUST be extracted to constants:

```typescript
import { IMAGE_LOADING, API, UI } from '@/config/constants'

// Image loading configuration
const preloadCount = IMAGE_LOADING.VISIBLE_CATEGORIES_PRELOAD_COUNT  // 20

// API configuration
const timeout = API.DEFAULT_TIMEOUT  // 30000ms

// UI configuration
const debounce = UI.SEARCH_DEBOUNCE_MS    // 300ms
const toastDuration = UI.TOAST_DURATION_MS  // 3000ms
```

**When adding constants:**
- Choose appropriate group (IMAGE_LOADING, API, UI)
- Add JSDoc comment explaining the value
- Use `as const` for type safety
- Update `frontend.instructions.md` if adding new category

**Categories:**
- `IMAGE_LOADING` - Image preload counts, lazy load thresholds
- `API` - API timeouts, retry delays, polling intervals
- `UI` - Debounce delays, animation durations, toast timings

### Code Quality Standards
1. **No Magic Numbers**: 
   - Extract all numeric literals to named constants
   - Define constants at module/component level with descriptive names
   - Example: `STALE_RECORDING_THRESHOLD_HOURS = 24` instead of `24 * 60 * 60 * 1000`

2. **Explicit Logic Changes**:
   - Add comments explaining why query logic changed (e.g., filter by `ended_at` vs `recording_path`)
   - Document if change affects data processing (e.g., includes streams without files)
   - Explain trade-offs in behavior

3. **Breaking Changes**:
   - Document in code comments with `BREAKING CHANGE:` prefix
   - Explain previous vs new behavior
   - Note trade-offs (e.g., "Stream history lost but prevents database bloat")
   - Mention alternatives (e.g., "Use preserve_favorites to keep important streams")

4. **Deferred Operations**:
   - Use `nextTick()` in Vue instead of `setTimeout()`
   - Use `requestIdleCallback()` for non-critical operations
   - If `setTimeout()` is necessary, extract delay to constant with rationale

5. **External Service Error Handling**:
   - **Check connectivity BEFORE** starting long-running operations
   - **Fail fast** with clear error messages when external services are unavailable
   - **Never let processes fail silently** - always log errors and propagate exceptions
   - **Example**: Check proxy connectivity before starting Streamlink recording
   - **Pattern**: Validate → Log → Raise exception with actionable error message

### Testing
- Unit tests for business logic
- Integration tests for API endpoints
- Mock external APIs (Twitch, Streamlink)
- **SECURITY**: Test path traversal attacks and input validation
- **SECURITY**: Verify all security controls with negative tests

## Build Error Resolution & Debugging

### SCSS Build Errors (Frontend)

**Common Error Pattern**: Undefined variables, missing imports, mixed declarations

**Systematic Debugging Workflow:**

1. **Read error carefully** → Identify file, line number, variable/property name
2. **Check imports** → Ensure `@use 'variables' as v;` is at top of file
3. **Check namespaces** → All variables need `v.$` prefix in Sass module system
4. **Check variable existence** → Variable must be defined in `_variables.scss`
5. **Fix and rebuild** → Errors are sequential, fixing one reveals next
6. **Verify clean build** → Should show `✓ built in X.XXs` with no warnings

**Quick Fixes:**

```bash
# Missing namespace on many variables (batch fix)
cd app/frontend/src/styles
sed -i 's/\$spacing-/v.\$spacing-/g' _utilities.scss
sed -i 's/\$shadow-/v.\$shadow-/g' _utilities.scss
sed -i 's/\$border-radius-/v.\$border-radius-/g' _utilities.scss

# Add missing import at top of file
sed -i '1i@use '\''variables'\'' as v;' _utilities.scss

# Fix Sass mixed-decls deprecation (wrap in & {})
# See frontend.instructions.md for detailed examples
```

**Error Types:**

| Error Message | Root Cause | Solution |
|--------------|------------|----------|
| `Undefined variable $name` | Missing import or namespace | Add `@use 'variables' as v;` + namespace all vars |
| `Undefined variable $duration-250` | Variable doesn't exist | Add missing variable to `_variables.scss` |
| `Invalid end tag` in .vue file | Duplicate `</style>` tags | Delete orphaned CSS between tags |
| `Deprecation Warning: mixed-decls` | Declaration after nested rule | Wrap in `& {}` or move before nested rules |

**See `frontend.instructions.md` for complete SCSS debugging guide.**

### Python Build/Runtime Errors (Backend)

**Common Error Pattern**: Missing imports, undefined names, attribute errors

**Quick Checks:**

```python
# Missing import (NameError: name 'WebSocketState' is not defined)
# ❌ Wrong:
from fastapi import WebSocket
if websocket.client_state == WebSocketState.CONNECTED:  # NameError!

# ✅ Correct:
from fastapi import WebSocket
from starlette.websockets import WebSocketState  # Import ALL required classes
if websocket.client_state == WebSocketState.CONNECTED:
```

**Debugging Steps:**

1. **Check imports** → Verify ALL classes/constants are imported
2. **Check type hints** → Ensure imported types match usage
3. **Check for circular imports** → Move imports inside functions if needed
4. **Run tests** → `pytest tests/` to catch errors early
5. **Check logs** → `tail -f logs/streamvault.log` for runtime errors

**See `backend.instructions.md` for comprehensive debugging patterns.**

### Production Build Validation

**Before committing, ALWAYS run:**

```bash
# Frontend build check
cd app/frontend
rm -rf dist/
npm run build  # Should show: ✓ built in X.XXs (no errors, no warnings)

# Backend startup check (catches missing imports)
cd ../..
python -m pytest tests/test_application_startup.py -v

# Full test suite
pytest tests/ -v
```

**Clean build output should show:**
- Frontend: `✓ built in 2-3s`, no errors, no warnings
- Backend: All tests pass, no import errors
- Logs: No ERROR or WARNING messages on startup

## Libraries and Frameworks

- **Backend**: FastAPI, SQLAlchemy, Pydantic, Streamlink, psycopg2
- **Frontend**: Vue 3, TypeScript, Vite, SCSS, Axios
- **Database**: PostgreSQL
- **Testing**: pytest (backend), Vitest (frontend)

## Coding Standards

- **Python**: PEP 8, type hints required, Google-style docstrings
- **TypeScript**: Strict mode, Composition API with `<script setup>`
- **SCSS**: Use design tokens from `_variables.scss`, never hard-code colors
- **Commits**: Conventional Commits for semantic versioning

## Frontend Component Patterns

### API Response Format Normalization

**Backend Convention**: All list endpoints return data wrapped in an object:

```python
@router.get("/api/streamers")
async def get_streamers(...):
    return {"streamers": streamers_list}  # ✅ Correct

# ❌ WRONG: Don't return raw arrays
return streamers_list
```

**Frontend Pattern**: Extract from wrapper object:

```typescript
// ✅ CORRECT: Extract from response object
const response = await fetch('/api/streamers', { credentials: 'include' })
const data = await response.json()
streamers.value = data.streamers || []  // Use wrapper key

// ❌ WRONG: Old pattern (caused "No Streamers" bug)
streamers.value = response.data || []  // response.data is undefined
```

**Verified Endpoints:**
- `/api/streamers` → `{streamers: [...]}`
- `/api/streamers/{id}/streams` → `{streams: [...]}`
- `/api/categories` → `{categories: [...]}`

### Actions Dropdown Pattern

For cards with multiple actions, use dropdown menus instead of multiple buttons:

**Component Structure:**

```vue
<template>
  <div class="card">
    <!-- Primary action visible -->
    <button v-if="isLive" @click.stop="handleWatch">Watch</button>
    
    <!-- More actions in dropdown -->
    <button @click.stop="toggleActions" class="btn-more">More</button>
    
    <div v-if="showActions" class="actions-dropdown" @click.stop>
      <button @click="handleForceRecord">Force Record</button>
      <button @click="handleViewDetails">View Details</button>
      <button @click="handleDelete" class="action-danger">Delete</button>
    </div>
  </div>
</template>

<script setup lang="ts">
const showActions = ref(false)

const toggleActions = () => {
  showActions.value = !showActions.value
}

const emit = defineEmits<{
  watch: [item: Item]
  forceRecord: [item: Item]
  delete: [item: Item]
}>()

const handleForceRecord = () => {
  showActions.value = false  // Close dropdown
  emit('forceRecord', props.item)
}

const handleDelete = () => {
  showActions.value = false
  emit('delete', props.item)
}
</script>
```

**Parent View Event Handling:**

```vue
<template>
  <ItemCard
    @force-record="handleForceRecord"
    @delete="handleDelete"
    @watch="handleWatch"
  />
</template>

<script setup lang="ts">
async function handleForceRecord(item: any) {
  await fetch(`/api/items/${item.id}/force-action`, {
    method: 'POST',
    credentials: 'include'
  })
  await refreshList()  // Refresh after action
}

async function handleDelete(item: any) {
  if (!confirm(`Delete ${item.name}? This cannot be undone.`)) {
    return
  }
  
  const response = await fetch(`/api/items/${item.id}`, {
    method: 'DELETE',
    credentials: 'include'
  })
  
  if (response.ok) {
    await refreshList()
  }
}
</script>
```

**Styling Best Practices:**

```scss
.actions-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  z-index: 1000;  // Above other elements
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  
  button {
    display: block;
    width: 100%;
    text-align: left;
    padding: 8px 12px;
    border: none;
    background: none;
    cursor: pointer;
    
    &:hover {
      background: var(--bg-hover);
    }
    
    &.action-danger {
      color: var(--danger-color);
      
      &:hover {
        background: rgba(255, 0, 0, 0.1);
      }
    }
  }
}
```

### Confirmation Dialogs for Destructive Actions

**ALWAYS** confirm before DELETE operations:

```typescript
// ✅ CORRECT: Confirm with clear message
async function handleDelete(item: any) {
  if (!confirm(`Delete ${item.display_name}? This action cannot be undone.`)) {
    return  // User cancelled
  }
  
  // Proceed with deletion
  await deleteItem(item.id)
}

// ❌ WRONG: No confirmation
async function handleDelete(item: any) {
  await deleteItem(item.id)  // Too easy to accidentally delete!
}
```

**Message Guidelines:**
- State what will be deleted
- Mention if data will be lost
- Use "cannot be undone" for permanent deletions
- Keep under 80 characters

### Live Stream Info Display

When showing live streamer information, follow this pattern:

**Backend Normalization:**

```python
@router.get("/api/streamers")
async def get_streamers(...):
    return {
        "streamers": [{
            "id": streamer.id,
            "username": streamer.username,
            "display_name": streamer.username,  # Frontend needs this
            "is_live": streamer.is_live,
            # Only show when live:
            "title": streamer.title if streamer.is_live else None,
            "category_name": streamer.category_name if streamer.is_live else None,
            "viewer_count": streamer.viewer_count if streamer.is_live else None
        }]
    }
```

**Frontend Display:**

```vue
<template>
  <div class="streamer-card" :class="{ 'is-live': streamer.is_live }">
    <div class="status-badge" v-if="streamer.is_live">
      <span class="live-dot"></span> LIVE
    </div>
    
    <!-- Only show when live -->
    <div v-if="streamer.is_live && streamer.title" class="stream-info">
      <h3>{{ truncateText(streamer.title, 50) }}</h3>
      <p class="game-name">{{ streamer.category_name }}</p>
      <span class="viewers">{{ streamer.viewer_count }} viewers</span>
    </div>
    
    <!-- Show when offline -->
    <div v-else class="offline-info">
      <p>Offline - {{ streamer.vods_count || 0 }} VODs</p>
    </div>
  </div>
</template>

<script setup lang="ts">
function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}
</script>

<style scoped>
.is-live {
  .status-badge {
    background: rgba(255, 0, 0, 0.1);
    color: #ff0000;
    font-weight: bold;
  }
  
  .live-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ff0000;
    animation: pulse 2s ease-in-out infinite;
  }
  
  .viewers {
    color: #ff0000;
    font-weight: bold;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
```

### Login Redirect Delay Pattern

**CRITICAL**: After successful login, delay redirect to ensure session cookie persistence:

```typescript
// ✅ CORRECT: Delay before redirect
if (response.ok) {
  // Wait for cookie to be set
  await new Promise(resolve => setTimeout(resolve, 100))
  
  // Full page reload to ensure session is active
  window.location.href = '/'
}

// ❌ WRONG: Immediate redirect can cause blank page
if (response.ok) {
  window.location.href = '/'  // Cookie not yet persisted!
}
```

**Why this is necessary:**
- Browser needs time to persist HTTP-only cookie
- Immediate redirect can happen before cookie is written
- Results in blank page / 401 errors on first load after login

**Related Commit:** 66b90ced

---

**Remember**: The commit type determines the version bump! Choose wisely:
- New functionality? → `feat:` → Minor bump (1.0 → 1.1)
- Code improvement? → `refactor:` → Minor bump (1.0 → 1.1)
- Bug fix? → `fix:` → Patch bump (1.0.0 → 1.0.1)
