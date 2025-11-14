# Security Audit: Path Traversal Prevention

## 🟡 Priority: HIGH
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 3-4 hours  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** CRITICAL - Security vulnerability (CWE-22), could lead to data breach

---

## 📝 Problem Description

### Security Vulnerability: Path Traversal (CWE-22)

**Definition:** Path traversal attacks allow attackers to access files and directories outside the intended directory by manipulating file paths with special sequences like `../`

**Example Attack:**
```
User Request: GET /api/recordings/download?file=../../../etc/passwd
Backend: os.path.join("/recordings", "../../../etc/passwd")
Result: /etc/passwd (SECURITY BREACH!)
```

**Real-World Impact:**
- **System File Access:** `../../../etc/passwd`, `../../.ssh/id_rsa`
- **Environment Variables:** `../app/config/.env` (leaks database credentials, API keys)
- **Database Access:** `../../database/streamvault.db` (entire database stolen)
- **Source Code Access:** `../app/routes/auth.py` (reveals security logic)
- **Arbitrary File Read/Write/Delete:** Depending on endpoint permissions

---

## 🔍 Current Vulnerable Areas

### 1. Cleanup Service
**File:** `app/services/cleanup/cleanup_service.py`

**Vulnerability:**
- Accepts `recordings_root` parameter from user input
- Uses `os.walk()` directly on user-provided path
- Could scan/delete system directories

**Attack Scenario:**
```
Admin Panel → Cleanup → "Cleanup Directory: ../../.."
Result: Deletes files from parent directories!
```

---

### 2. File Download Endpoint
**File:** `app/routes/recordings.py` or `app/routes/streams.py`

**Vulnerability:**
- Accepts filename from query parameter
- Constructs full path with `os.path.join()`
- Serves file without path validation

**Attack Scenario:**
```
GET /api/recordings/download?file=../../../etc/passwd
Result: Downloads system files!
```

---

### 3. Recording Management
**File:** `app/routes/recordings.py`

**Vulnerability:**
- Delete recording endpoint accepts file path
- No validation that path is within recordings directory
- Could delete arbitrary files

**Attack Scenario:**
```
DELETE /api/recordings/123?path=../../important_file.txt
Result: Deletes unrelated files!
```

---

### 4. VOD Streaming
**File:** `app/routes/videos.py` or similar

**Vulnerability:**
- Serves video files based on user-provided path
- Could stream system files or other users' data

**Attack Scenario:**
```
GET /api/stream/video?path=../../other_user/private_video.mp4
Result: Access to other users' content!
```

---

### 5. Thumbnail/Image Serving
**File:** `app/routes/images.py` or static file serving

**Vulnerability:**
- Serves images based on filename parameter
- Could serve arbitrary images or files

**Attack Scenario:**
```
GET /api/thumbnails?file=../../../sensitive_image.png
Result: Leaks sensitive images!
```

---

## 🎯 Solution Requirements

### Goal: Implement Path Validation & Sanitization

**Requirements:**
1. **Create `validate_path_security()` utility** - Validates all user-provided paths
2. **Apply to all file operations** - Read, write, delete, list
3. **Use path normalization** - Resolve `..`, `.`, symlinks
4. **Verify containment** - Ensure path within allowed directory
5. **Add security logging** - Log all blocked attempts
6. **Test with attack payloads** - Verify protection works

---

## 📋 Attack Vectors to Block

### Path Traversal Patterns

**Simple Traversal:**
- `../../etc/passwd`
- `..\..\..\windows\system32\config\sam` (Windows)

**URL-Encoded:**
- `..%2F..%2F..%2Fetc%2Fpasswd`
- `%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd`

**Double-Encoded:**
- `%252e%252e%252f` (becomes `../` after double decode)

**Null Byte Injection:**
- `../../etc/passwd%00.txt` (historical attack, check for null bytes)

**Absolute Paths:**
- `/etc/passwd`
- `C:\Windows\System32\config\sam`

**Symlink Attacks:**
- Create symlink in recordings dir pointing to `/etc`
- Request file through symlink

---

## 🏗️ Implementation Requirements

### Phase 1: Create Security Utility

**File:** `app/utils/security.py` (NEW or use existing `app/utils/security_enhanced.py`)

**Required Functions:**

1. **`validate_path_security(user_path: str, operation_type: str) -> str`**
   - Normalize path (resolve `..`, `.`, symlinks)
   - Check containment within safe directory
   - Verify path exists (for read/write/delete operations)
   - Log blocked attempts
   - Raise HTTPException (400/403/404) on failure
   - Return validated absolute path

2. **`sanitize_filename(filename: str) -> str`**
   - Remove path separators (`/`, `\`)
   - Remove special characters
   - Remove leading dots (prevent hidden files)
   - Limit length to 255 characters
   - Return sanitized filename only (no path components)

3. **`validate_file_extension(filename: str, allowed_extensions: set) -> None`**
   - Extract file extension
   - Check against whitelist
   - Raise HTTPException if not allowed

---

### Phase 2: Audit All File Operations

**Files to Audit:**
- `app/services/cleanup/cleanup_service.py`
- `app/routes/recordings.py`
- `app/routes/streams.py`
- `app/routes/streamers.py`
- `app/routes/videos.py`
- `app/routes/images.py` (if exists)
- Any file using `os.path.join()`, `open()`, `Path()`, `os.walk()` with user input

**Search Patterns:**
```bash
# Find file operations with user input
grep -rn 'os\.path\.join\|open(\|Path(\|os\.walk\|shutil\.' app/ --include="*.py"
```

---

### Phase 3: Apply Validation

**Pattern to Apply:**

**Before (VULNERABLE):**
```python
@router.get("/download")
async def download_file(filename: str):
    file_path = os.path.join(RECORDING_DIR, filename)
    return FileResponse(file_path)
```

**After (SECURE):**
```python
from app.utils.security import validate_path_security

@router.get("/download")
async def download_file(filename: str):
    file_path = os.path.join(RECORDING_DIR, filename)
    safe_path = validate_path_security(file_path, "read")  # Validates!
    return FileResponse(safe_path)
```

---

### Phase 4: Add Security Tests

**File:** `tests/security/test_path_traversal.py` (NEW)

**Test Cases:**
- [ ] Test `../../etc/passwd` blocked
- [ ] Test `..%2F..%2Fetc%2Fpasswd` blocked (URL-encoded)
- [ ] Test absolute paths blocked (`/etc/passwd`)
- [ ] Test null byte injection blocked
- [ ] Test valid paths allowed
- [ ] Test paths within recordings dir allowed
- [ ] Test symlink traversal blocked
- [ ] Test nested traversal blocked (`a/../../b/../../c`)

---

## ✅ Acceptance Criteria

### Security Requirements
- [ ] All file operations use `validate_path_security()`
- [ ] All path traversal attack patterns blocked
- [ ] All blocked attempts logged with 🚨 prefix
- [ ] Appropriate HTTP status codes returned (400/403/404)
- [ ] Symlink attacks prevented (use `os.path.realpath()`)
- [ ] Null byte injection prevented

### Code Coverage
- [ ] Cleanup service validated
- [ ] File download endpoints validated
- [ ] Recording delete endpoints validated
- [ ] VOD streaming validated
- [ ] Image/thumbnail serving validated
- [ ] Any other file operations validated

### Testing Requirements
- [ ] Security test suite passes (20+ test cases)
- [ ] Penetration testing with attack payloads
- [ ] Manual testing with Burp Suite or OWASP ZAP
- [ ] Verify logs show blocked attempts
- [ ] Verify valid paths still work

### Documentation
- [ ] Security utility functions documented
- [ ] Attack patterns documented
- [ ] Security instructions updated (`.github/instructions/security.instructions.md`)
- [ ] Known blocked patterns listed

---

## 🧪 Testing Requirements

### Automated Security Tests

**Attack Payload Test Cases:**
```python
# tests/security/test_path_traversal.py
ATTACK_PAYLOADS = [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\config\\sam",
    "..%2F..%2F..%2Fetc%2Fpasswd",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "/etc/passwd",
    "C:\\Windows\\System32\\config\\sam",
    "../../.env",
    "../app/config/.env",
    "recordings/../../etc/passwd",
    "a/../../../etc/passwd",
]

for payload in ATTACK_PAYLOADS:
    # Should raise HTTPException (403 or 400)
    with pytest.raises(HTTPException):
        validate_path_security(payload, "read")
```

### Manual Penetration Testing

**Tools:**
- OWASP ZAP (automated scanner)
- Burp Suite (manual testing)
- `curl` with attack payloads

**Test Scenarios:**
1. Try to download `/etc/passwd`
2. Try to delete files outside recordings directory
3. Try to access other users' recordings
4. Try symlink attacks
5. Try null byte injection
6. Try double URL encoding

---

## 📖 References

**Security Standards:**
- [CWE-22: Path Traversal](https://cwe.mitre.org/data/definitions/22.html)
- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)

**Project Documentation:**
- `docs/MASTER_TASK_LIST.md` - Task #10 (Security Audit)
- `.github/instructions/security.instructions.md` - Security guidelines
- `.github/ARCHITECTURE.md` - Security patterns

**Existing Security Code:**
- Check if `app/utils/security.py` or `app/utils/security_enhanced.py` already exists
- Review existing validation patterns

**Related Issues:**
- Issue #2: Multi-Proxy System (input validation for proxy URLs)
- Issue #6: Extract Magic Numbers (file size thresholds)

---

## 🎯 Solution: Implement Path Validation

### Security Pattern

```python
import os
from pathlib import Path
from fastapi import HTTPException

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

---

## 📋 Implementation Tasks

### 1. Create Security Utility Module (1 hour)

**File:** `app/utils/security.py` (NEW)

```python
"""
Security utilities for path validation and sanitization
"""
import os
import logging
from pathlib import Path
from typing import Literal
from fastapi import HTTPException

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

def validate_path_security(
    user_path: str,
    operation_type: Literal["access", "read", "write", "delete"] = "access"
) -> str:
    """
    SECURITY: Validate path against traversal attacks
    
    Args:
        user_path: Path provided by user (untrusted input)
        operation_type: Type of operation ("access", "read", "write", "delete")
    
    Returns:
        Normalized, validated path within safe directory
    
    Raises:
        HTTPException: 400 for invalid path, 403 for traversal attempt, 404 if not found
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
    
    logger.debug(f"✅ SECURITY: Path validated: {user_path} -> {normalized_path}")
    return normalized_path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and invalid characters
    
    Args:
        filename: User-provided filename
    
    Returns:
        Sanitized filename (no path separators or special chars)
    """
    import re
    
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove special characters (keep alphanumeric, dash, underscore, dot)
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Remove leading dots (hidden files)
    filename = filename.lstrip('.')
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    
    if not filename:
        raise ValueError("Invalid filename: Empty after sanitization")
    
    return filename


def validate_file_extension(filename: str, allowed_extensions: set[str]) -> None:
    """
    Validate file has allowed extension
    
    Args:
        filename: Filename to check
        allowed_extensions: Set of allowed extensions (e.g., {'.mp4', '.mkv'})
    
    Raises:
        HTTPException: 400 if extension not allowed
    """
    ext = Path(filename).suffix.lower()
    
    if ext not in allowed_extensions:
        logger.error(f"🚨 SECURITY: Invalid file extension: {ext} (allowed: {allowed_extensions})")
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(allowed_extensions)}"
        )
```

---

### 2. Secure Cleanup Service (1 hour)

**File:** `app/services/cleanup/cleanup_service.py`

**Before (VULNERABLE):**
```python
async def cleanup_old_recordings(recordings_root: str = None):
    """Cleanup old recordings"""
    if not recordings_root:
        recordings_root = get_settings().RECORDING_DIRECTORY
    
    # VULNERABLE: No validation!
    for root, dirs, files in os.walk(recordings_root):
        for file in files:
            file_path = os.path.join(root, file)
            os.remove(file_path)  # Can delete anything!
```

**After (SECURE):**
```python
from app.utils.security import validate_path_security

async def cleanup_old_recordings(recordings_root: str = None):
    """Cleanup old recordings"""
    settings = get_settings()
    
    if not recordings_root:
        recordings_root = settings.RECORDING_DIRECTORY
    
    # SECURITY: Validate path before operations
    safe_root = validate_path_security(recordings_root, "access")
    
    for root, dirs, files in os.walk(safe_root):
        for file in files:
            file_path = os.path.join(root, file)
            
            # SECURITY: Validate each file path
            try:
                safe_file_path = validate_path_security(file_path, "delete")
                os.remove(safe_file_path)
                logger.info(f"Deleted: {safe_file_path}")
            except HTTPException as e:
                logger.error(f"🚨 SECURITY: Blocked deletion: {file_path} - {e.detail}")
                continue
```

---

### 3. Secure File Download Endpoint (30 minutes)

**File:** `app/routes/streams.py`

**Before (VULNERABLE):**
```python
@router.get("/api/streams/{id}/download")
async def download_stream(id: int, session: Session = Depends(get_db)):
    stream = session.query(Stream).filter(Stream.id == id).first()
    
    if not stream or not stream.recording_path:
        raise HTTPException(404)
    
    # VULNERABLE: No path validation!
    return FileResponse(stream.recording_path, filename=stream.filename)
```

**After (SECURE):**
```python
from app.utils.security import validate_path_security, validate_file_extension

@router.get("/api/streams/{id}/download")
async def download_stream(id: int, session: Session = Depends(get_db)):
    stream = session.query(Stream).filter(Stream.id == id).first()
    
    if not stream or not stream.recording_path:
        raise HTTPException(404, detail="Stream not found")
    
    # SECURITY: Validate file path
    safe_path = validate_path_security(stream.recording_path, "read")
    
    # SECURITY: Validate file extension
    ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.ts', '.m3u8'}
    validate_file_extension(safe_path, ALLOWED_VIDEO_EXTENSIONS)
    
    return FileResponse(safe_path, filename=stream.filename)
```

---

### 4. Secure VOD Streaming (30 minutes)

**File:** `app/routes/streams.py`

**Before (VULNERABLE):**
```python
@router.get("/api/streams/{id}/watch")
async def watch_stream(id: int):
    stream = get_stream(id)
    
    # VULNERABLE: Streams arbitrary file!
    return FileResponse(stream.recording_path, media_type="video/mp4")
```

**After (SECURE):**
```python
from app.utils.security import validate_path_security, validate_file_extension

@router.get("/api/streams/{id}/watch")
async def watch_stream(id: int, session: Session = Depends(get_db)):
    stream = session.query(Stream).filter(Stream.id == id).first()
    
    if not stream or not stream.recording_path:
        raise HTTPException(404)
    
    # SECURITY: Validate file path and extension
    safe_path = validate_path_security(stream.recording_path, "read")
    validate_file_extension(safe_path, {'.mp4', '.mkv', '.ts'})
    
    # Determine media type
    ext = Path(safe_path).suffix.lower()
    media_types = {'.mp4': 'video/mp4', '.mkv': 'video/x-matroska', '.ts': 'video/mp2t'}
    media_type = media_types.get(ext, 'video/mp4')
    
    return FileResponse(safe_path, media_type=media_type)
```

---

### 5. Secure Recording Deletion (30 minutes)

**File:** `app/routes/recordings.py`

**Before (VULNERABLE):**
```python
@router.delete("/api/recordings/{id}")
async def delete_recording(id: int):
    recording = get_recording(id)
    
    # VULNERABLE: Deletes any file!
    os.remove(recording.output_path)
```

**After (SECURE):**
```python
from app.utils.security import validate_path_security

@router.delete("/api/recordings/{id}")
async def delete_recording(id: int, session: Session = Depends(get_db)):
    recording = session.query(Recording).filter(Recording.id == id).first()
    
    if not recording:
        raise HTTPException(404)
    
    # SECURITY: Validate path before deletion
    safe_path = validate_path_security(recording.output_path, "delete")
    
    try:
        os.remove(safe_path)
        session.delete(recording)
        await session.commit()
        logger.info(f"✅ Deleted recording: {safe_path}")
    except Exception as e:
        logger.error(f"Failed to delete: {safe_path} - {e}")
        raise HTTPException(500, detail="Failed to delete recording")
```

---

## 📂 Files to Create

- `app/utils/security.py` (NEW - security utilities)

## 📂 Files to Modify

- `app/services/cleanup/cleanup_service.py`
- `app/routes/streams.py` (download, watch endpoints)
- `app/routes/recordings.py` (delete endpoint)
- `.github/instructions/security.instructions.md` (add patterns)
- `.github/instructions/backend.instructions.md` (add security checklist)

---

## ✅ Acceptance Criteria

**Path Validation:**
- [ ] All file operations use `validate_path_security()`
- [ ] Path traversal attempts blocked (403 error)
- [ ] Invalid paths rejected (400 error)
- [ ] Non-existent paths handled (404 error)
- [ ] Security events logged

**File Operations:**
- [ ] Download endpoint validates paths
- [ ] Watch endpoint validates paths and extensions
- [ ] Delete endpoint validates paths
- [ ] Cleanup service validates all paths
- [ ] No arbitrary file access possible

**Security Logging:**
- [ ] Traversal attempts logged with 🚨 prefix
- [ ] Valid paths logged with ✅ prefix
- [ ] User input included in logs
- [ ] Normalized path shown in logs

**Testing:**
- [ ] Attack tests verify blocking
- [ ] Valid paths still work
- [ ] Error messages user-friendly (no internal paths exposed)
- [ ] Performance not degraded

---

## 🧪 Testing Checklist

**Attack Simulation:**

```python
# tests/test_security.py
import pytest
from fastapi.testclient import TestClient

def test_path_traversal_blocked(client: TestClient):
    """Path traversal attacks should be blocked"""
    
    # Attack: Access system file
    response = client.get("/api/streams/1/download?file=../../../etc/passwd")
    assert response.status_code == 403
    
    # Attack: Access config file
    response = client.get("/api/streams/1/download?file=../../.env")
    assert response.status_code == 403
    
    # Attack: Access database
    response = client.get("/api/streams/1/download?file=../database/streamvault.db")
    assert response.status_code == 403

def test_valid_paths_allowed(client: TestClient):
    """Valid paths within recordings directory should work"""
    
    # Create test stream
    stream = create_test_stream(recording_path="/recordings/test.mp4")
    
    # Valid access
    response = client.get(f"/api/streams/{stream.id}/download")
    assert response.status_code == 200

def test_filename_sanitization():
    """Filenames should be sanitized"""
    from app.utils.security import sanitize_filename
    
    assert sanitize_filename("../../etc/passwd") == "__..__..__etc__passwd"
    assert sanitize_filename("test<>.mp4") == "test__.mp4"
    assert sanitize_filename("normal-file_123.mp4") == "normal-file_123.mp4"

def test_file_extension_validation():
    """Only allowed extensions should pass"""
    from app.utils.security import validate_file_extension
    
    # Valid
    validate_file_extension("test.mp4", {'.mp4', '.mkv'})
    
    # Invalid
    with pytest.raises(HTTPException) as exc:
        validate_file_extension("test.exe", {'.mp4', '.mkv'})
    assert exc.value.status_code == 400
```

**Manual Testing:**

```bash
# Test path traversal blocking
curl -v "http://localhost:8000/api/streams/1/download?file=../../../etc/passwd"
# Expected: 403 Forbidden

# Test valid file access
curl -v "http://localhost:8000/api/streams/1/download"
# Expected: 200 OK (if stream exists)

# Check security logs
grep "🚨 SECURITY" logs/streamvault.log
```

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md` (Task #9)  
**Security Guide:** `.github/instructions/security.instructions.md`  
**Backend Guide:** `.github/instructions/backend.instructions.md`

**Update Security Instructions:**

Add to `.github/instructions/security.instructions.md`:

```markdown
## Path Traversal Prevention Examples

**ALWAYS validate user-provided paths:**

```python
from app.utils.security import validate_path_security

# ✅ CORRECT: Validate before operations
safe_path = validate_path_security(user_path, "read")
with open(safe_path, 'r') as f:
    content = f.read()

# ❌ WRONG: Direct usage of user input
with open(user_path, 'r') as f:  # Path traversal vulnerability!
    content = f.read()
```

**Sanitize filenames:**

```python
from app.utils.security import sanitize_filename

# ✅ CORRECT: Sanitize before using
safe_filename = sanitize_filename(user_filename)
path = os.path.join(BASE_DIR, safe_filename)

# ❌ WRONG: Direct join with user input
path = os.path.join(BASE_DIR, user_filename)  # Can be "../../../etc/passwd"
```
```

---

## 🤖 Copilot Instructions

**Context:**
Implement path traversal prevention to fix CWE-22 vulnerability. Currently, file operations accept unsanitized user input allowing access to arbitrary files outside recordings directory.

**Critical Patterns:**
1. **Path validation:**
   ```python
   from app.utils.security import validate_path_security
   
   safe_path = validate_path_security(user_path, "read")
   with open(safe_path, 'r') as f:
       content = f.read()
   ```

2. **Filename sanitization:**
   ```python
   from app.utils.security import sanitize_filename
   
   safe_filename = sanitize_filename(user_filename)
   ```

3. **Extension validation:**
   ```python
   from app.utils.security import validate_file_extension
   
   validate_file_extension(filename, {'.mp4', '.mkv'})
   ```

**Implementation Order:**
1. Create `app/utils/security.py` with validation functions
2. Update cleanup service
3. Secure file download endpoint
4. Secure VOD streaming endpoint
5. Secure deletion endpoint
6. Add tests simulating attacks

**Testing Strategy:**
1. Write attack tests (path traversal attempts)
2. Verify attacks are blocked (403)
3. Verify valid paths still work (200)
4. Check security logs for blocked attempts
5. Ensure no internal paths in error messages

**Files to Read First:**
- `.github/instructions/security.instructions.md` (current security patterns)
- `.github/copilot-instructions.md` (Security Guidelines section)
- `app/services/cleanup/cleanup_service.py` (current vulnerable code)

**Success Criteria:**
All file operations validate paths, traversal attempts blocked with 403, valid paths work, attacks logged, tests verify security.

**Common Pitfalls:**
- ❌ Only checking for `../` (can be bypassed with URL encoding)
- ❌ Using string manipulation instead of `os.path.realpath()`
- ❌ Not validating EVERY file operation
- ❌ Exposing internal paths in error messages
- ❌ Not logging security events
- ❌ Missing test cases for attack vectors
