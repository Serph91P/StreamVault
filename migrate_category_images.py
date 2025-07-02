#!/usr/bin/env python3
"""
DEPRECATED: Migration script to download category images for existing categories in the database

This script is now superseded by the automatic migration in migration_service.py
The migration "20250702_setup_category_images" will be run automatically on startup.

You can still run this script manually if needed, but it's not required.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import get_db
from app.models import Category
from app.services.category_image_service import category_image_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_category_images():
    """Download images for all existing categories"""
    logger.info("Starting category image migration...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Get all unique categories from the database
        categories = db.query(Category).all()
        
        if not categories:
            logger.info("No categories found in database")
            return
        
        logger.info(f"Found {len(categories)} categories in database")
        
        # Extract unique category names
        category_names = list(set(
            category.name for category in categories 
            if category.name and category.name.strip()
        ))
        
        logger.info(f"Downloading images for {len(category_names)} unique categories...")
        
        # Download all category images
        await category_image_service.preload_categories(category_names)
        
        logger.info("Category image migration completed!")
        
        # Show cache status
        cached_count = len(category_image_service._category_cache)
        failed_count = len(category_image_service._failed_downloads)
        
        logger.info(f"Results:")
        logger.info(f"  - Successfully cached: {cached_count} images")
        logger.info(f"  - Failed downloads: {failed_count}")
        
        if category_image_service._failed_downloads:
            logger.info("Failed categories:")
            for failed_category in category_image_service._failed_downloads:
                logger.info(f"  - {failed_category}")
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(migrate_category_images())
