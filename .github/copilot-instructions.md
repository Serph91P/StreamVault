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

## Commit Message Convention

**IMPORTANT**: This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic semantic versioning.

### Commit Message Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
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

## Security Guidelines - CRITICAL

### ⚠️ MANDATORY SECURITY REQUIREMENTS

**ALWAYS** apply these security checks when working with file paths, user input, or external data:

#### 🔒 Path Traversal Prevention (CRITICAL)
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
- **NO MAGIC NUMBERS**: Extract all constants to configuration or module-level constants
- **BREAKING CHANGES**: Document behavior changes in comments and commit messages
- **EXTERNAL SERVICE FAILURES**: Always check connectivity before using external services (proxies, APIs)
- **FAIL FAST**: Validate preconditions early, don't let processes silently fail
- **MISSING IMPORTS**: Verify ALL imports when using framework features (WebSocketState, etc.)
- **DUPLICATE PREVENTION**: Check for existing operations before starting new ones
- **STARTUP CLEANUP**: Clean zombie/stale state on application startup
- **SECURITY**: Always validate file paths and user input
- **SECURITY**: Use parameterized queries, never string concatenation

### Frontend (PWA - Mobile-First)
- Use Composition API with `<script setup lang="ts">`
- **NEVER** override global `.btn` or `.status-border-*` classes
- All tables must transform to cards on mobile
- Use SCSS variables from `_variables.scss`
- Touch targets: minimum 44x44px
- **NO MAGIC NUMBERS**: Extract timing delays, thresholds, and limits to constants
- **USE VUE LIFECYCLE**: Prefer `nextTick()` over `setTimeout()` for deferred operations
- **SECURITY**: Sanitize all user input before display
- **SECURITY**: Validate file uploads on client and server side

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

---

**Remember**: The commit type determines the version bump! Choose wisely:
- New functionality? → `feat:` → Minor bump (1.0 → 1.1)
- Code improvement? → `refactor:` → Minor bump (1.0 → 1.1)
- Bug fix? → `fix:` → Patch bump (1.0.0 → 1.0.1)
