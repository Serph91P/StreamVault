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
