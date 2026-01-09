"""
Utility functions for file path resolution in production and development environments
"""

from typing import List


def get_file_paths(filename: str, include_dist: bool = False) -> List[str]:
    """
    Get standardized file paths for static files in both production and development environments

    Args:
        filename: Name of the file to locate
        include_dist: Whether to include dist directory paths (for built files)

    Returns:
        List of potential file paths to try
    """
    base_paths = ["app/frontend/public", "/app/app/frontend/public"]  # Development  # Production Docker

    if include_dist:
        base_paths.extend(
            ["app/frontend/dist", "/app/app/frontend/dist"]  # Development built  # Production Docker built
        )

    return [f"{base_path}/{filename}" for base_path in base_paths]


def get_pwa_file_paths(filename: str) -> List[str]:
    """Get file paths for PWA-related files (includes both public and dist)"""
    return get_file_paths(filename, include_dist=True)
