#!/usr/bin/env python
"""
Migration 010: Setup category image caching
Creates directory structure and default category image
"""
import os
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Setup category image caching system"""
    try:
        logger.info("🔄 Setting up category image caching...")
        
        # Create images directory structure
        images_dir = Path("app/frontend/public/images/categories")
        images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Created category images directory: {images_dir}")
        
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
            logger.info("✅ Created default category image")
        
        logger.info("🎉 Migration 010 completed successfully")
        
    except Exception as e:
        logger.error(f"Migration 010 failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()