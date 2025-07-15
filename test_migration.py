#!/usr/bin/env python3
"""
Test migration system
"""

import logging
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.abspath('.'))

from app.services.migration_service import MigrationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Test the migration service"""
    try:
        logger.info("Testing migration service...")
        
        # Test run_safe_migrations
        logger.info("Testing run_safe_migrations...")
        result = MigrationService.run_safe_migrations()
        logger.info(f"run_safe_migrations returned: {result}")
        
        # Test get_all_migration_scripts
        logger.info("Testing get_all_migration_scripts...")
        scripts = MigrationService.get_all_migration_scripts()
        logger.info(f"Found {len(scripts)} migration scripts:")
        for script in scripts:
            logger.info(f"  - {os.path.basename(script)}")
        
        logger.info("✅ Migration service test completed")
        
    except Exception as e:
        logger.error(f"❌ Error testing migration service: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
