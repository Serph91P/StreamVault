"""
Security utilities for StreamVault

This module provides security functions to prevent common vulnerabilities
like path traversal, SQL injection, and input validation bypasses.

CRITICAL: All user input must be validated using these functions.
"""

import os
import re
import html
import json
import logging
from typing import Optional
from pathlib import Path
from datetime import datetime
from fastapi import HTTPException

logger = logging.getLogger("streamvault.security")

def sanitize_path_component(component: str, allow_subdirs: bool = False) -> str:
    """
    Sanitize a path component to prevent path traversal attacks
    
    Args:
        component: The path component to sanitize
        allow_subdirs: Whether to allow subdirectory separators
        
    Returns:
        Sanitized path component
        
    Raises:
        HTTPException: If the component contains dangerous characters
    """
    if not component:
        raise HTTPException(status_code=400, detail="Empty path component")
    
    # Check for path traversal attempts
    if ".." in component:
        logger.warning(f"Path traversal attempt detected: {component}")
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Check for absolute paths
    if component.startswith("/") or component.startswith("\\"):
        logger.warning(f"Absolute path attempt detected: {component}")
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Check for directory separators if not allowed
    if not allow_subdirs and ("/" in component or "\\" in component):
        logger.warning(f"Directory separator in component: {component}")
        raise HTTPException(status_code=400, detail="Invalid path")
    
    return component

def secure_path_join(base_path: str, *components: str) -> Path:
    """
    Securely join path components and validate the result
    
    Args:
        base_path: The base directory path
        *components: Path components to join
        
    Returns:
        Resolved Path object
        
    Raises:
        HTTPException: If the resulting path is outside the base directory
    """
    # Convert to Path objects
    base = Path(base_path).resolve()
    
    # Sanitize all components
    sanitized_components = []
    for component in components:
        sanitized = sanitize_path_component(component, allow_subdirs=True)
        sanitized_components.append(sanitized)
      # Join paths
    full_path = base
    for component in sanitized_components:
        full_path = full_path / component
    
    # Resolve to handle any remaining .. or symlinks
    try:
        resolved_path = full_path.resolve()
    except Exception as e:
        logger.warning(f"Path resolution failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Ensure the resolved path is within the base directory
    if not str(resolved_path).startswith(str(base)):
        logger.warning(f"Path outside base directory: {resolved_path} not in {base}")
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check for symlink attacks on resolved path
    if resolved_path.is_symlink():
        logger.warning(f"Symlink access attempted: {resolved_path}")
        raise HTTPException(status_code=403, detail="Symlink access denied")
    
    return resolved_path

def safe_error_message(error: Exception, default_message: str = "An error occurred") -> str:
    """
    Create a safe error message that doesn't expose sensitive information
    
    Args:
        error: The original exception
        default_message: Default message to use
        
    Returns:
        Safe error message string
    """
    # Log the full error for debugging
    logger.error(f"Error occurred: {str(error)}", exc_info=True)
    
    # Return generic message to client
    return default_message

def validate_safe_path(base_path: str, user_input: str) -> Path:
    """
    Validate that user input creates a safe path within the base directory.
    This function is designed to prevent CodeQL path injection warnings by
    clearly separating trusted base paths from untrusted user input.
    
    Args:
        base_path: Trusted server configuration path
        user_input: Untrusted user-provided path component
        
    Returns:
        Validated Path object within base directory
        
    Raises:
        HTTPException: If path is unsafe or outside base directory
    """
    # Sanitize user input first - no direct path operations on raw input
    if not user_input or not isinstance(user_input, str):
        raise HTTPException(status_code=400, detail="Invalid input")
    
    # Remove dangerous characters and validate
    clean_input = sanitize_path_component(user_input, allow_subdirs=True)
    
    # Use secure_path_join for safe path construction
    return secure_path_join(base_path, clean_input)


def create_safe_file_path(recordings_dir: str, streamer_name: str, filename: str) -> Path:
    """
    Create a safe file path from user inputs, preventing path traversal.
    This separates the validation logic to make CodeQL analysis clearer.
    
    Args:
        recordings_dir: Trusted base directory from server config
        streamer_name: User-provided streamer name (untrusted)
        filename: User-provided filename (untrusted)
        
    Returns:
        Safe, validated Path object
        
    Raises:
        HTTPException: If inputs are invalid or create unsafe paths
    """
    # First validate the streamer directory
    streamer_path = validate_safe_path(recordings_dir, streamer_name)
    
    # Then validate the filename within that directory
    file_path = validate_safe_path(str(streamer_path), filename)
    
    return file_path


def validate_path_security(user_path: str, operation_type: str = "access") -> str:
    """
    SECURITY: Validate path against traversal attacks
    
    This function prevents path traversal attacks (CWE-22) by ensuring
    that user-provided paths cannot access files outside the safe directory.
    
    Args:
        user_path: User-provided path (can be relative or absolute)
        operation_type: "read", "write", "delete", or "access"
        
    Returns:
        str: Normalized, validated absolute path
        
    Raises:
        HTTPException: If path is invalid or outside safe directory
        
    Example:
        >>> safe_path = validate_path_security("/recordings/../../../etc/passwd", "read")
        HTTPException: 403 Access denied: Path outside allowed directory
        
        >>> safe_path = validate_path_security("/recordings/streamer1/video.mp4", "read")
        "/srv/recordings/streamer1/video.mp4"
    """
    from app.config.settings import get_settings
    
    if not user_path or not isinstance(user_path, str):
        logger.error(f"🚨 SECURITY: Empty or invalid path type: {type(user_path)}")
        raise HTTPException(
            status_code=400, 
            detail="Path cannot be empty"
        )
    
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
    # Using shared helper for consistent validation
    if not is_path_within_base(normalized_path, safe_base):
        logger.error(
            f"🚨 SECURITY: Path traversal attempt blocked - "
            f"User: {user_path} -> Normalized: {normalized_path} "
            f"(Safe base: {safe_base})"
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
    
    # Additional validation based on operation type
    if operation_type in ["read", "write", "delete"]:
        if not os.path.exists(normalized_path):
            raise HTTPException(
                status_code=404,
                detail=f"Path not found: {user_path}"
            )
            
        # Validate path type for specific operations
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
    
    logger.debug(f"🔒 SECURITY: Path validated - {user_path} -> {normalized_path}")
    return normalized_path


def validate_filename(filename: str) -> str:
    """
    Validate and sanitize filename for secure file operations
    
    Args:
        filename: User-provided filename
        
    Returns:
        str: Sanitized filename
        
    Raises:
        ValueError: If filename is invalid or dangerous
    """
    if not filename or not isinstance(filename, str) or len(filename.strip()) == 0:
        raise ValueError("Filename cannot be empty")
    
    clean_filename = filename.strip()
    
    # Remove or replace dangerous characters
    # Allow: letters, numbers, dots, hyphens, underscores, spaces
    safe_filename = re.sub(r'[^\w\-_\. ]', '_', clean_filename)
    
    # Replace multiple spaces/underscores with single ones
    safe_filename = re.sub(r'[_\s]+', '_', safe_filename)
    
    # Prevent hidden files and directory references
    if safe_filename.startswith('.') or safe_filename in ['..', '.', '/', '\\']:
        raise ValueError(f"Invalid filename: {filename}")
    
    # Length validation
    if len(safe_filename) > 255:
        raise ValueError("Filename too long (max 255 characters)")
        
    # Prevent empty filename after sanitization
    if not safe_filename or safe_filename.isspace():
        raise ValueError(f"Filename becomes empty after sanitization: {filename}")
        
    return safe_filename


def validate_streamer_name(name: str) -> str:
    """
    Validate Twitch streamer name according to platform rules
    
    Args:
        name: User-provided streamer name
        
    Returns:
        str: Validated, normalized streamer name
        
    Raises:
        ValueError: If name doesn't meet Twitch requirements
    """
    if not name or not isinstance(name, str) or len(name.strip()) == 0:
        raise ValueError("Streamer name cannot be empty")
    
    clean_name = name.strip().lower()
    
    # Twitch username rules: 4-25 chars, alphanumeric + underscore
    # Must start with letter or number
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_]{3,24}$', clean_name):
        raise ValueError(
            "Invalid streamer name: must be 4-25 characters, "
            "alphanumeric + underscore, start with letter/number"
        )
        
    return clean_name


def log_security_event(
    event_type: str,
    details: dict,
    severity: str = "INFO",
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None
):
    """
    Log security-related events for monitoring and analysis
    
    Args:
        event_type: Type of security event
        details: Event-specific details
        severity: Event severity (INFO, WARNING, CRITICAL)
        user_id: Associated user ID (optional)
        ip_address: Source IP address (optional)
    """
    log_entry = {
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": ip_address,
        "timestamp": datetime.utcnow().isoformat(),
        "severity": severity,
        **details
    }
    
    if severity == "CRITICAL":
        logger.critical(f"🚨 SECURITY ALERT: {json.dumps(log_entry)}")
    elif severity == "WARNING":
        logger.warning(f"⚠️ SECURITY WARNING: {json.dumps(log_entry)}")
    else:
        logger.info(f"🔐 SECURITY EVENT: {json.dumps(log_entry)}")


# File type validation constants
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.ts', '.m3u8', '.avi', '.mov'}
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

ALLOWED_VIDEO_MIME_TYPES = {
    'video/mp4',
    'video/x-matroska',      # .mkv
    'video/mp2t',            # .ts
    'application/x-mpegURL', # .m3u8
    'video/x-msvideo',       # .avi
    'video/quicktime'        # .mov
}


def validate_file_type(
    filename: str, 
    allowed_extensions: set = ALLOWED_VIDEO_EXTENSIONS
) -> str:
    """
    Validate file type by extension
    
    Args:
        filename: File name to validate
        allowed_extensions: Set of allowed file extensions
        
    Returns:
        str: File extension (normalized)
        
    Raises:
        ValueError: If file type is not allowed
    """
    if not filename:
        raise ValueError("Filename is required")
    
    file_extension = Path(filename).suffix.lower()
    
    if not file_extension:
        raise ValueError("File must have an extension")
        
    if file_extension not in allowed_extensions:
        raise ValueError(
            f"File type '{file_extension}' not allowed. "
            f"Allowed: {', '.join(sorted(allowed_extensions))}"
        )
    
    return file_extension


def is_path_within_base(path: str, base: str) -> bool:
    """
    Check if path is within base directory
    
    This is a public helper function for validating that a path is contained
    within a base directory, used throughout the application for security checks.
    
    Args:
        path: Path to check (should be normalized)
        base: Base directory (should be normalized)
        
    Returns:
        bool: True if path is within base directory
    """
    try:
        path_obj = Path(path)
        base_obj = Path(base)
        
        # Exact match
        if path_obj == base_obj:
            return True
        
        # Use is_relative_to if available (Python 3.9+)
        if hasattr(path_obj, 'is_relative_to'):
            return path_obj.is_relative_to(base_obj)
        
        # Fallback: string-based check
        return path.startswith(base + os.sep)
    except (OSError, ValueError, TypeError):
        return False


def sanitize_html_input(html_input: str) -> str:
    """
    Sanitize HTML input to prevent XSS attacks
    
    Args:
        html_input: User-provided HTML content
        
    Returns:
        str: Sanitized HTML
    """
    if not html_input or not isinstance(html_input, str):
        return ""
    
    # Basic HTML escaping - for more complex needs, use bleach library
    sanitized = html.escape(html_input.strip())
    
    # Limit length to prevent DoS
    if len(sanitized) > 10000:  # 10KB limit
        sanitized = sanitized[:10000] + "..."
        
    return sanitized
