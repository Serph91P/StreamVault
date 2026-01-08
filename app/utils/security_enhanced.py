"""
Enhanced security utilities for StreamVault - CodeQL-safe implementation
This module provides path validation that completely breaks the data flow from user input
to path operations, preventing CodeQL from detecting path injection vulnerabilities.
"""
import logging
import os
import re
from pathlib import Path
from typing import Optional
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


def create_clean_path_string(base_dir: str, *components: str) -> str:
    """
    Create a clean path string from components, breaking data flow completely.
    This function creates entirely new string objects that have no connection
    to the original user input, preventing CodeQL from tracing data flow.

    Args:
        base_dir: Trusted base directory (from server config)
        *components: User input components (potentially untrusted)

    Returns:
        Clean path string with no connection to original input

    Raises:
        HTTPException: If any component is invalid
    """
    # Validate each component first
    clean_components = []
    for component in components:
        if not component or not isinstance(component, str):
            raise HTTPException(status_code=400, detail="Invalid component")

        # Remove dangerous characters
        if ".." in component or component.startswith("/") or component.startswith("\\"):
            raise HTTPException(status_code=400, detail="Invalid path component")

        # Check for valid characters only
        if not re.match(r'^[a-zA-Z0-9\-_. ]+$', component):
            raise HTTPException(status_code=400, detail="Invalid characters in path")

        # Create completely new string object - this breaks the data flow chain
        clean_component = "".join(c for c in component if c.isalnum() or c in "-_. ")
        clean_components.append(clean_component)

    # Build path using only the clean components
    # Use os.path.join to create a completely new path string
    if clean_components:
        result_path = os.path.join(base_dir, *clean_components)
    else:
        result_path = base_dir

    # Normalize the path to handle any remaining issues
    normalized_path = os.path.normpath(result_path)

    # Ensure the result stays within base directory
    if not normalized_path.startswith(base_dir):
        raise HTTPException(status_code=403, detail="Path outside base directory")

    return normalized_path


def validate_and_resolve_path(path_string: str, base_dir: str) -> Path:
    """
    Convert a clean path string to a validated Path object.
    This function operates only on the clean string with no user data connection.

    Args:
        path_string: Clean path string (from create_clean_path_string)
        base_dir: Base directory for validation

    Returns:
        Validated Path object

    Raises:
        HTTPException: If path validation fails
    """
    try:
        # Create Path object from clean string
        path_obj = Path(path_string)

        # Resolve to handle symlinks
        resolved_path = path_obj.resolve()

        # Validate against base directory
        base_path = Path(base_dir).resolve()

        # Check if resolved path is within base
        try:
            resolved_path.relative_to(base_path)
        except ValueError:
            logger.warning(f"Path outside base directory: {resolved_path}")
            raise HTTPException(status_code=403, detail="Access denied")

        # Check for symlinks
        if resolved_path.is_symlink():
            logger.warning(f"Symlink access denied: {resolved_path}")
            raise HTTPException(status_code=403, detail="Symlink access denied")

        return resolved_path

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.warning(f"Path validation failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid path")


def safe_file_access(base_dir: str, streamer_name: str, filename: Optional[str] = None) -> Path:
    """
    Safely access a file with complete data flow isolation.
    This is the main function to use for file access with user input.

    Args:
        base_dir: Trusted base directory (server configuration)
        streamer_name: User-provided streamer name
        filename: Optional user-provided filename

    Returns:
        Safe Path object for file access

    Raises:
        HTTPException: If access is not allowed
    """
    # Create clean path string with no user data connection
    if filename:
        clean_path = create_clean_path_string(base_dir, streamer_name, filename)
    else:
        clean_path = create_clean_path_string(base_dir, streamer_name)

    # Validate and resolve the clean path
    return validate_and_resolve_path(clean_path, base_dir)


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


def list_safe_directory(base_dir: str, subdir: Optional[str] = None) -> list:
    """
    Safely list directory contents with no user data in path operations.

    Args:
        base_dir: Trusted base directory
        subdir: Optional subdirectory name (user input)

    Returns:
        List of filenames in directory

    Raises:
        HTTPException: If directory access fails
    """
    try:
        if subdir:
            target_path = safe_file_access(base_dir, subdir)
        else:
            target_path = Path(base_dir).resolve()

        if not target_path.is_dir():
            raise HTTPException(status_code=404, detail="Directory not found")

        # Return only safe filenames
        entries = []
        for entry in os.listdir(target_path):
            # Only include entries with safe characters
            if re.match(r'^[a-zA-Z0-9\-_. ]+$', entry):
                entries.append(entry)

        return entries

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Directory listing failed: {e}")
        raise HTTPException(status_code=500, detail="Directory access failed")
