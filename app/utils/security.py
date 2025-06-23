"""
Security utilities for StreamVault
"""
import logging
import os
from pathlib import Path
from fastapi import HTTPException

logger = logging.getLogger("streamvault")

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
