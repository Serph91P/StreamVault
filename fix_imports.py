#!/usr/bin/env python3
"""
Import Fix Script for StreamVault Service Reorganization

This script automatically fixes import paths after services were moved to organized folders:
- api/ - Twitch API Services  
- processing/ - Post-processing & Task Services
- system/ - System management Services
- media/ - Media Services (artwork, thumbnail, metadata)
- communication/ - Notification & WebSocket Services
- core/ - Core application Services
- init/ - Initialization Services
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Define the import mappings from old -> new paths
IMPORT_MAPPINGS = {
    # API Services
    'from app.services.api.twitch_api': 'from app.services.api.twitch_api',
    'from app.services.api.twitch_oauth_service': 'from app.services.api.twitch_oauth_service',
    
    # Processing Services  
    'from app.services.processing.post_processing_tasks': 'from app.services.processing.post_processing_tasks',
    'from app.services.processing.post_processing_task_handlers': 'from app.services.processing.post_processing_task_handlers',
    'from app.services.processing.recording_task_factory': 'from app.services.processing.recording_task_factory',
    'from app.services.processing.task_dependency_manager': 'from app.services.processing.task_dependency_manager',
    
    # System Services
    'from app.services.system.cleanup_service': 'from app.services.system.cleanup_service',
    'from app.services.system.migration_service': 'from app.services.system.migration_service',
    'from app.services.system.system_config_service': 'from app.services.system.system_config_service',
    'from app.services.system.logging_service': 'from app.services.system.logging_service',
    
    # Media Services
    'from app.services.media.artwork_service': 'from app.services.media.artwork_service',
    'from app.services.media.thumbnail_service': 'from app.services.media.thumbnail_service',
    'from app.services.media.metadata_service': 'from app.services.media.metadata_service',
    
    # Communication Services
    'from app.services.communication.webpush_service': 'from app.services.communication.webpush_service',
    'from app.services.communication.enhanced_push_service': 'from app.services.communication.enhanced_push_service',
    'from app.services.communication.websocket_manager': 'from app.services.communication.websocket_manager',
    
    # Core Services
    'from app.services.core.auth_service': 'from app.services.core.auth_service',
    'from app.services.core.settings_service': 'from app.services.core.settings_service',
    'from app.services.core.state_persistence_service': 'from app.services.core.state_persistence_service',
    'from app.services.core.test_service': 'from app.services.core.test_service',
    
    # Init Services
    'from app.services.init.startup_init': 'from app.services.init.startup_init',
    'from app.services.init.background_queue_init': 'from app.services.init.background_queue_init',
    
    # Images Services (already moved)
    'from app.services.images.image_sync_service': 'from app.services.images.image_sync_service',
}

def fix_imports_in_file(file_path: Path) -> Tuple[bool, List[str]]:
    """
    Fix imports in a single Python file
    
    Returns:
        Tuple of (was_modified, list_of_changes)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False, []
    
    original_content = content
    changes = []
    
    # Apply all import mappings
    for old_import, new_import in IMPORT_MAPPINGS.items():
        if old_import in content:
            content = content.replace(old_import, new_import)
            changes.append(f"  {old_import} → {new_import}")
    
    # If content was modified, write it back
    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, changes
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return False, []
    
    return False, []

def find_python_files(root_dir: Path) -> List[Path]:
    """Find all Python files in the app directory"""
    python_files = []
    
    # Include app directory and subdirectories, but exclude some paths
    exclude_patterns = {
        '__pycache__',
        '.git',
        'node_modules',
        'frontend/dist',
        'frontend/node_modules'
    }
    
    for file_path in root_dir.rglob('*.py'):
        # Skip if any part of the path contains excluded patterns
        if any(part in exclude_patterns for part in file_path.parts):
            continue
        python_files.append(file_path)
    
    return python_files

def main():
    """Main function to fix all import paths"""
    print("StreamVault Import Fix Script")
    print("=" * 50)
    
    # Get the app directory
    app_dir = Path('app')
    if not app_dir.exists():
        print("app/ directory not found. Please run this script from the StreamVault root directory.")
        return
    
    # Find all Python files
    print("Finding Python files...")
    python_files = find_python_files(Path('.'))
    print(f"Found {len(python_files)} Python files")
    
    # Process each file
    total_modified = 0
    total_changes = 0
    
    for file_path in python_files:
        was_modified, changes = fix_imports_in_file(file_path)
        
        if was_modified:
            total_modified += 1
            total_changes += len(changes)
            print(f"Modified {file_path}")
            for change in changes:
                print(change)
            print()
    
    # Summary
    print("Summary")
    print("=" * 50)
    print(f"Files processed: {len(python_files)}")
    print(f"Files modified: {total_modified}")
    print(f"Total import changes: {total_changes}")
    
    if total_modified > 0:
        print("\nImport fixes completed!")
        print("Next steps:")
        print("  1. Test the application: python -c 'import app.main'")
        print("  2. Fix any remaining import errors manually")
        print("  3. Run tests to ensure everything works")
    else:
        print("\nNo import fixes needed - all imports are already correct!")

if __name__ == "__main__":
    main()
