"""
Setup category image caching system and preload existing categories

This migration sets up the category image caching system and preloads existing categories.
"""

from app.database import engine
from sqlalchemy import text
import logging
import asyncio
import os
from pathlib import Path

logger = logging.getLogger("streamvault")

def upgrade():
    """Setup category image caching system and preload existing categories"""
    try:
        # Create images directory structure
        images_dir = Path("app/frontend/public/images/categories")
        images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created category images directory: {images_dir}")
        
        # Create default category image if it doesn't exist
        default_image_path = images_dir / "default-category.svg"
        if not default_image_path.exists():
            default_svg_content = '''<svg width="144" height="192" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#9146FF;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#6441A5;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="144" height="192" fill="url(#grad1)" rx="8"/>
  <text x="72" y="90" text-anchor="middle" fill="white" font-family="Arial, sans-serif" font-size="20" font-weight="bold">
    GAME
  </text>
  <text x="72" y="120" text-anchor="middle" fill="white" font-family="Arial, sans-serif" font-size="16">
    CATEGORY
  </text>
  <circle cx="72" cy="140" r="8" fill="white" opacity="0.7"/>
  <circle cx="60" cy="155" r="6" fill="white" opacity="0.5"/>
  <circle cx="84" cy="155" r="6" fill="white" opacity="0.5"/>
</svg>'''
            with open(default_image_path, 'w', encoding='utf-8') as f:
                f.write(default_svg_content)
            logger.info("Created default category image")
        
        # Start background task to preload existing category images
        try:
            # Import the service here to avoid circular imports
            from app.services.category_image_service import category_image_service
            from app.models import Category
            from app.database import SessionLocal
            
            # Get all existing categories from database
            with SessionLocal() as session:
                categories = session.query(Category).all()
                
                if categories:
                    category_names = [cat.name for cat in categories if cat.name and cat.name.strip()]
                    
                    if category_names:
                        logger.info(f"Starting background preload for {len(category_names)} existing categories")
                        
                        # Create an async task to preload images
                        # Note: This runs in background, migration doesn't wait for completion
                        try:
                            # Try to run the async preload
                            asyncio.create_task(category_image_service.preload_categories(category_names))
                            logger.info("Background category image preload started")
                        except RuntimeError:
                            # If no event loop is running, just log and continue
                            logger.info("No event loop available, category images will be loaded on-demand")
                    else:
                        logger.info("No category names found to preload")
                else:
                    logger.info("No existing categories found in database")
                    
        except Exception as e:
            # Don't fail the migration if preloading fails
            logger.warning(f"Could not preload category images (will load on-demand): {e}")
        
        logger.info("Category images migration completed successfully")
        
    except Exception as e:
        logger.error(f"Category images migration failed: {e}")
        raise

def downgrade():
    """Remove category image caching system"""
    try:
        # Remove images directory
        images_dir = Path("app/frontend/public/images/categories")
        if images_dir.exists():
            import shutil
            shutil.rmtree(images_dir)
            logger.info("Removed category images directory")
    except Exception as e:
        logger.error(f"Error removing category images: {e}")
        raise

if __name__ == "__main__":
    upgrade()
