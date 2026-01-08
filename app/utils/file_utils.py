"""File utility functions for StreamVault - ONLY file operations, no metadata!"""
import re
import logging
from pathlib import Path

logger = logging.getLogger("streamvault")


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for use as a filename"""
    if not name:
        return "unknown"

    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, '_')

    # Remove control characters
    name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)

    # Collapse multiple spaces/underscores
    name = re.sub(r'[_\s]+', '_', name)

    # Remove leading/trailing dots and spaces
    name = name.strip('. ')

    # Limit length
    if len(name) > 200:
        name = name[:197] + "..."

    return name or "unknown"


async def cleanup_temporary_files(base_path: str):
    """Clean up temporary files after processing"""
    try:
        temp_extensions = ['.tmp', '.part', '.temp']
        base = Path(base_path).parent if base_path else Path('.')

        for ext in temp_extensions:
            for temp_file in base.glob(f"*{ext}"):
                try:
                    temp_file.unlink()
                    logger.debug(f"Removed temporary file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Could not remove {temp_file}: {e}")

    except Exception as e:
        logger.error(f"Error cleaning temporary files: {e}")


def validate_directory_path(directory: Path, base_directory: Path) -> bool:
    """
    Validate that a directory path is safe to operate on.

    Args:
        directory: The directory path to validate
        base_directory: The base directory that should contain the target directory

    Returns:
        True if path is safe to operate on, False otherwise
    """
    try:
        # Ensure both paths are absolute
        if not directory.is_absolute():
            logger.warning(f"Directory path is not absolute: {directory}")
            return False

        if not base_directory.is_absolute():
            logger.warning(f"Base directory path is not absolute: {base_directory}")
            return False

        # Check if directory is within the base directory
        try:
            directory.resolve().relative_to(base_directory.resolve())
            return True
        except ValueError:
            logger.warning(f"Directory {directory} is outside base directory {base_directory}")
            return False

    except Exception as e:
        logger.error(f"Error validating directory path {directory}: {e}")
        return False


def safe_remove_directory(directory: Path, base_directory: Path) -> bool:
    """
    Safely remove a directory with path validation.

    Args:
        directory: The directory to remove
        base_directory: The base directory for validation

    Returns:
        True if directory was removed successfully, False otherwise
    """
    import shutil

    if not validate_directory_path(directory, base_directory):
        logger.error(f"Refusing to remove directory due to failed path validation: {directory}")
        return False

    try:
        if directory.exists():
            shutil.rmtree(directory)
            logger.info(f"Successfully removed directory: {directory}")
            return True
        else:
            logger.info(f"Directory does not exist, skipping removal: {directory}")
            return True
    except Exception as e:
        logger.error(f"Error removing directory {directory}: {e}")
        return False


def ensure_directory_exists(directory: Path) -> bool:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory: The directory path to ensure exists

    Returns:
        True if directory exists or was created successfully, False otherwise
    """
    try:
        directory.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {directory}: {e}")
        return False
