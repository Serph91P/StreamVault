# Security Guidelines - StreamVault

## Overview

This document provides comprehensive security guidelines for StreamVault development. **EVERY** developer must follow these guidelines to prevent security vulnerabilities.

## Critical Security Requirements

### 🔒 Path Traversal Prevention (CWE-22)

**BACKGROUND**: Path traversal attacks allow attackers to access files outside intended directories using paths like `../../../etc/passwd`.

#### Implementation Requirements

1. **ALWAYS** validate user-provided file paths
2. **NEVER** use raw user input in file operations  
3. **USE** the standard validation function for all file operations

```python
def validate_path_security(user_path: str, operation_type: str = "access") -> str:
    """
    SECURITY: Validate path against traversal attacks
    
    This is the actual implementation from app/utils/security.py
    
    Args:
        user_path: User-provided path (can be relative or absolute)
        operation_type: "read", "write", "delete", or "access"
        
    Returns:
        str: Normalized, validated absolute path
        
    Raises:
        HTTPException: If path is invalid or outside safe directory
    """
    import os
    from app.config.settings import get_settings
    from app.utils.security import is_path_within_base  # Shared helper function
    
    settings = get_settings()
    safe_base = os.path.realpath(settings.RECORDING_DIRECTORY)
    
    try:
        # CRITICAL: Normalize and resolve all path components
        # This resolves symlinks and relative path components (../, ./)
        normalized_path = os.path.realpath(os.path.abspath(user_path))
    except (OSError, ValueError, TypeError) as e:
        logger.error(f"🚨 SECURITY: Invalid path provided: {user_path} - {e}")
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid path format: {user_path}"
        )
    
    # CRITICAL: Ensure path is within safe directory
    # Uses shared validation helper for consistent checking across the app
    if not is_path_within_base(normalized_path, safe_base):
        logger.error(
            f"🚨 SECURITY: Path traversal attempt blocked: "
            f"{user_path} -> {normalized_path} (safe base: {safe_base})"
        )
        
        # Log security event for monitoring
        log_security_event(
            event_type="PATH_TRAVERSAL_BLOCKED",
            details={
                "attempted_path": user_path,
                "normalized_path": normalized_path,
                "safe_base": safe_base,
                "operation_type": operation_type
            },
            severity="CRITICAL"
        )
        
        raise HTTPException(
            status_code=403, 
            detail="Access denied: Path outside allowed directory"
        )
    
    # Validate path exists for operations requiring it
    if operation_type in ["read", "write", "delete"]:
        if not os.path.exists(normalized_path):
            raise HTTPException(
                status_code=404,
                detail=f"Path not found: {user_path}"
            )
            
        # Additional checks based on operation
        if operation_type == "read" and not os.path.isfile(normalized_path):
            raise HTTPException(
                status_code=400,
                detail=f"Path is not a file: {user_path}"
            )
        elif operation_type == "write":
            parent_dir = os.path.dirname(normalized_path)
            if not os.path.isdir(parent_dir):
                raise HTTPException(
                    status_code=400,
                    detail=f"Parent directory does not exist: {parent_dir}"
                )
            if os.path.exists(normalized_path) and os.path.isdir(normalized_path):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot write to directory: {user_path}"
                )
    
    return normalized_path
```

#### Usage Examples

```python
# ✅ CORRECT: API endpoint with path validation
@router.post("/cleanup-orphaned-files")
async def cleanup_orphaned_files(recordings_root: str = Query(...)):
    # SECURITY: Always validate before any file operations
    safe_path = validate_path_security(recordings_root, "read")
    return await cleanup_service.cleanup_orphaned_files(safe_path)

# ✅ CORRECT: Service method with validation
async def cleanup_files(self, recordings_root: str) -> tuple[int, list[str]]:
    # SECURITY: Validate at service layer too
    safe_root = validate_path_security(recordings_root, "read")
    
    for root, dirs, files in os.walk(safe_root):
        # Now safe to use os.walk with validated path
        pass

# ❌ INCORRECT: Direct use of user input
async def cleanup_files(self, recordings_root: str):
    # VULNERABILITY: recordings_root could be "../../../etc"
    for root, dirs, files in os.walk(recordings_root):
        pass
```

### 🛡️ Input Validation & Sanitization

#### String Input Validation
```python
import re
from typing import Optional

def validate_filename(filename: str) -> str:
    """Validate and sanitize filename"""
    if not filename or len(filename.strip()) == 0:
        raise ValueError("Filename cannot be empty")
    
    # Remove dangerous characters
    safe_filename = re.sub(r'[^\w\-_\.]', '_', filename.strip())
    
    # Prevent hidden files and current/parent directory references
    if safe_filename.startswith('.') or safe_filename in ['..', '.']:
        raise ValueError(f"Invalid filename: {filename}")
    
    # Length check
    if len(safe_filename) > 255:
        raise ValueError("Filename too long")
        
    return safe_filename

def validate_streamer_name(name: str) -> str:
    """Validate Twitch streamer name"""
    if not name or len(name.strip()) == 0:
        raise ValueError("Streamer name cannot be empty")
    
    # Twitch username rules: 4-25 chars, alphanumeric + underscore
    clean_name = name.strip().lower()
    if not re.match(r'^[a-zA-Z0-9_]{4,25}$', clean_name):
        raise ValueError("Invalid streamer name format")
        
    return clean_name

def validate_category_slug(slug: str) -> str:
    """Validate category slug for URL safety"""
    if not slug or len(slug.strip()) == 0:
        raise ValueError("Category slug cannot be empty")
    
    # Only allow URL-safe characters
    clean_slug = slug.strip().lower()
    if not re.match(r'^[a-z0-9\-_]+$', clean_slug):
        raise ValueError("Category slug contains invalid characters")
        
    return clean_slug
```

#### Numeric Input Validation
```python
def validate_positive_integer(value: any, field_name: str, max_value: Optional[int] = None) -> int:
    """Validate positive integer input"""
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        raise ValueError(f"{field_name} must be a valid integer")
    
    if int_value < 0:
        raise ValueError(f"{field_name} must be positive")
    
    if max_value and int_value > max_value:
        raise ValueError(f"{field_name} cannot exceed {max_value}")
    
    return int_value

def validate_file_size(size: int, max_size_mb: int = 1000) -> int:
    """Validate file size limits"""
    max_bytes = max_size_mb * 1024 * 1024
    
    if size < 0:
        raise ValueError("File size cannot be negative")
    
    if size > max_bytes:
        raise ValueError(f"File size exceeds {max_size_mb}MB limit")
        
    return size
```

### 🗄️ Database Security (SQL Injection Prevention)

#### SQLAlchemy ORM - Preferred Method
```python
# ✅ CORRECT: ORM queries are automatically parameterized
def get_streams_by_name(db: Session, name_pattern: str) -> List[Stream]:
    return db.query(Stream).filter(
        Stream.streamer_name.ilike(f"%{name_pattern}%")  # Safe with ORM
    ).all()

def get_streams_by_status(db: Session, statuses: List[str]) -> List[Stream]:
    return db.query(Stream).filter(
        Stream.status.in_(statuses)  # Safe with ORM
    ).all()

# ✅ CORRECT: Using ORM with user input
def search_streams(db: Session, search_term: str, limit: int = 50) -> List[Stream]:
    # Input validation first
    if len(search_term.strip()) == 0:
        raise ValueError("Search term cannot be empty")
    
    clean_term = search_term.strip()[:100]  # Limit length
    
    return db.query(Stream).filter(
        or_(
            Stream.streamer_name.ilike(f"%{clean_term}%"),
            Stream.title.ilike(f"%{clean_term}%")
        )
    ).limit(limit).all()
```

#### Raw SQL - When ORM is Insufficient
```python
# ✅ CORRECT: Parameterized raw SQL
def get_stream_statistics(db: Session, start_date: datetime, end_date: datetime):
    result = db.execute(
        text("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as stream_count,
                AVG(duration) as avg_duration
            FROM streams 
            WHERE created_at BETWEEN :start_date AND :end_date
            GROUP BY DATE(created_at)
            ORDER BY date
        """),
        {
            "start_date": start_date,
            "end_date": end_date
        }
    )
    return result.fetchall()

# ❌ INCORRECT: String formatting with user input
def search_streams_unsafe(db: Session, table_name: str, search_term: str):
    # VULNERABILITY: SQL injection via table_name and search_term
    query = f"SELECT * FROM {table_name} WHERE title LIKE '%{search_term}%'"
    return db.execute(query).fetchall()
```

### 🔐 Authentication & Authorization

#### API Route Protection
```python
from app.middleware.auth import verify_admin_access

# ✅ CORRECT: Admin-only endpoint protection
@router.post("/admin/cleanup-files")
@verify_admin_access  # Middleware validates admin privileges
async def cleanup_files(
    recordings_root: str = Query(...),
    current_user: User = Depends(get_current_user)
):
    # Double-check admin status
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    safe_path = validate_path_security(recordings_root, "read")
    return await cleanup_service.cleanup_files(safe_path)

# ✅ CORRECT: User-specific data access
@router.get("/streams/my-streams")
async def get_user_streams(current_user: User = Depends(get_current_user)):
    # Users can only access their own streams
    return db.query(Stream).filter(
        Stream.user_id == current_user.id
    ).all()
```

#### Session Management
```python
# ✅ CORRECT: Secure session configuration
from app.config.settings import get_settings

def create_session_cookie(user_id: int) -> str:
    settings = get_settings()
    
    # Use secure session tokens
    session_data = {
        "user_id": user_id,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
    }
    
    # Sign with secret key
    token = jwt.encode(session_data, settings.SECRET_KEY, algorithm="HS256")
    
    return token

def validate_session_token(token: str) -> Optional[User]:
    """Validate session token and return user"""
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        
        # Check expiration
        expires_at = datetime.fromisoformat(payload["expires_at"])
        if datetime.utcnow() > expires_at:
            return None
            
        return get_user_by_id(payload["user_id"])
        
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
```

### 📁 File Upload Security

#### File Type Validation
```python
import magic
from pathlib import Path

# Allowed file types for uploads
ALLOWED_MIME_TYPES = {
    'video/mp4',
    'video/x-matroska',  # .mkv
    'video/mp2t',        # .ts
    'application/x-mpegURL'  # .m3u8
}

ALLOWED_EXTENSIONS = {'.mp4', '.mkv', '.ts', '.m3u8'}

async def validate_uploaded_file(file: UploadFile) -> str:
    """Validate uploaded file and return safe filename"""
    
    # Size validation
    if file.size > 10 * 1024 * 1024 * 1024:  # 10GB limit
        raise HTTPException(400, "File too large (max 10GB)")
    
    # Filename validation
    if not file.filename:
        raise HTTPException(400, "No filename provided")
        
    safe_filename = validate_filename(file.filename)
    file_extension = Path(safe_filename).suffix.lower()
    
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type not allowed: {file_extension}")
    
    # MIME type validation (read first chunk)
    file_content = await file.read(1024)
    await file.seek(0)  # Reset file pointer
    
    detected_mime = magic.from_buffer(file_content, mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Invalid file format: {detected_mime}")
    
    return safe_filename

# ✅ CORRECT: Secure file upload endpoint
@router.post("/upload/video")
async def upload_video(
    file: UploadFile,
    current_user: User = Depends(get_current_user)
):
    safe_filename = await validate_uploaded_file(file)
    
    # Generate unique filename to prevent conflicts
    unique_filename = f"{current_user.id}_{int(time.time())}_{safe_filename}"
    
    # Validate destination path
    upload_dir = get_settings().UPLOAD_DIRECTORY
    safe_path = validate_path_security(
        os.path.join(upload_dir, unique_filename), 
        "write"
    )
    
    # Save file
    with open(safe_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    return {"filename": unique_filename, "size": file.size}
```

### 🔍 Logging & Monitoring

#### Security Event Logging
```python
import logging

# Configure security logger
security_logger = logging.getLogger("streamvault.security")

def log_security_event(
    event_type: str,
    user_id: Optional[int],
    ip_address: str,
    details: dict,
    severity: str = "INFO"
):
    """Log security-related events"""
    
    log_entry = {
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": ip_address,
        "timestamp": datetime.utcnow().isoformat(),
        "severity": severity,
        **details
    }
    
    if severity == "CRITICAL":
        security_logger.critical(f"🚨 SECURITY ALERT: {json.dumps(log_entry)}")
    elif severity == "WARNING":
        security_logger.warning(f"⚠️ SECURITY WARNING: {json.dumps(log_entry)}")
    else:
        security_logger.info(f"🔐 SECURITY EVENT: {json.dumps(log_entry)}")

# Usage examples
def log_path_traversal_attempt(user_path: str, normalized_path: str, user_id: int, ip: str):
    log_security_event(
        event_type="PATH_TRAVERSAL_BLOCKED",
        user_id=user_id,
        ip_address=ip,
        details={
            "attempted_path": user_path,
            "normalized_path": normalized_path,
            "action": "BLOCKED"
        },
        severity="CRITICAL"
    )

def log_failed_authentication(username: str, ip: str):
    log_security_event(
        event_type="AUTHENTICATION_FAILED",
        user_id=None,
        ip_address=ip,
        details={
            "username": username,
            "action": "LOGIN_FAILED"
        },
        severity="WARNING"
    )
```

### 🧪 Security Testing Requirements

#### Unit Tests for Security Functions
```python
import pytest
import tempfile
import os

class TestPathSecurity:
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.safe_base = os.path.realpath(self.temp_dir)
    
    def test_path_traversal_blocked(self):
        """Test that path traversal attacks are blocked"""
        with pytest.raises(HTTPException) as exc_info:
            validate_path_security("../../../etc/passwd", "read")
        assert exc_info.value.status_code == 403
        
    def test_absolute_path_outside_base_blocked(self):
        """Test that absolute paths outside base are blocked"""
        with pytest.raises(HTTPException) as exc_info:
            validate_path_security("/etc/passwd", "read")
        assert exc_info.value.status_code == 403
    
    def test_valid_subdirectory_allowed(self):
        """Test that valid subdirectories are allowed"""
        subdir = os.path.join(self.temp_dir, "recordings", "streamer1")
        os.makedirs(subdir, exist_ok=True)
        
        result = validate_path_security(subdir, "read")
        assert result == os.path.realpath(subdir)
    
    def test_symlink_traversal_blocked(self):
        """Test that symlinks cannot bypass security"""
        evil_link = os.path.join(self.temp_dir, "evil_link")
        os.symlink("/etc", evil_link)
        
        with pytest.raises(HTTPException) as exc_info:
            validate_path_security(evil_link, "read")
        assert exc_info.value.status_code == 403

class TestInputValidation:
    
    def test_filename_sanitization(self):
        """Test filename sanitization"""
        assert validate_filename("test.mp4") == "test.mp4"
        assert validate_filename("../evil.mp4") == "..evil.mp4"  # .. gets replaced
        assert validate_filename("file with spaces.mp4") == "file_with_spaces.mp4"
    
    def test_streamer_name_validation(self):
        """Test streamer name validation"""
        assert validate_streamer_name("validname") == "validname"
        
        with pytest.raises(ValueError):
            validate_streamer_name("name_with_invalid_chars!")
            
        with pytest.raises(ValueError):
            validate_streamer_name("ab")  # Too short
```

#### Integration Tests for API Security
```python
def test_admin_endpoint_requires_authentication(client: TestClient):
    """Test that admin endpoints require valid authentication"""
    response = client.post("/admin/cleanup-files", params={"recordings_root": "/test"})
    assert response.status_code == 401

def test_admin_endpoint_blocks_path_traversal(client: TestClient, admin_headers):
    """Test that admin endpoints block path traversal"""
    response = client.post(
        "/admin/cleanup-files", 
        params={"recordings_root": "../../../etc"},
        headers=admin_headers
    )
    assert response.status_code == 403
    assert "Path outside allowed directory" in response.json()["detail"]

def test_file_upload_validates_file_type(client: TestClient, user_headers):
    """Test that file upload validates file types"""
    # Create a fake executable file
    fake_exe = b"MZ\x90\x00"  # PE executable header
    
    response = client.post(
        "/upload/video",
        files={"file": ("malware.exe", io.BytesIO(fake_exe), "application/octet-stream")},
        headers=user_headers
    )
    assert response.status_code == 400
    assert "File type not allowed" in response.json()["detail"]
```

## Security Code Review Checklist

Before committing code, verify:

### File Operations
- [ ] All user-provided paths validated with `validate_path_security()`
- [ ] No direct use of `os.walk()`, `open()`, or `shutil` with user input
- [ ] File uploads validate type, size, and filename
- [ ] Temporary files created in secure locations

### Database Operations  
- [ ] All queries use SQLAlchemy ORM or parameterized queries
- [ ] No string formatting or concatenation with user input
- [ ] Input validation applied before database operations
- [ ] Proper indexing for performance (avoid N+1 queries)

### API Endpoints
- [ ] Authentication/authorization checks implemented
- [ ] Input validation on all parameters
- [ ] Proper error handling without information disclosure
- [ ] Rate limiting for sensitive operations

### General Security
- [ ] No secrets or credentials in code
- [ ] Proper logging of security events
- [ ] Error messages don't reveal system internals
- [ ] Security tests written for new functionality

## Emergency Security Response

If you discover a security vulnerability:

1. **STOP** - Do not commit the vulnerable code
2. **ASSESS** - Determine the severity and impact
3. **FIX** - Implement proper security controls using this guide
4. **TEST** - Write security tests to verify the fix
5. **COMMIT** - Use security-specific commit message format:

```
security: fix path traversal in file operations

SECURITY IMPACT: High - Arbitrary file access vulnerability
VULNERABILITY: CWE-22 Path Traversal  
AFFECTED: All file operation APIs accepting user paths

- Implemented path validation using validate_path_security()
- Added containment checks for all file operations
- Enhanced security logging for blocked attempts
- Added comprehensive security tests

Testing: Verified ../../../etc/passwd attacks blocked
```

## Security Dependencies

Ensure these security-focused packages are installed:

```txt
# Input validation and sanitization
pydantic>=2.0.0          # Input validation
bleach>=6.0.0           # HTML sanitization

# Cryptography and authentication
cryptography>=41.0.0     # Secure crypto operations  
pyjwt>=2.8.0            # JWT token handling
bcrypt>=4.0.0           # Password hashing

# File type detection
python-magic>=0.4.0     # MIME type detection
pillow>=10.0.0          # Image validation

# Security monitoring
python-json-logger>=2.0.0  # Structured security logging
```

## Conclusion

Security is **NOT OPTIONAL** in StreamVault. Every developer must:

1. **VALIDATE** all user input
2. **SANITIZE** data before processing  
3. **TEST** security controls thoroughly
4. **LOG** security events appropriately
5. **REVIEW** code for security issues before committing

When in doubt, err on the side of caution and implement additional security controls.