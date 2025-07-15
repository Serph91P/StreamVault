#!/usr/bin/env python3
"""
Manual migration runner for episode_number column
"""

import logging
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.abspath('.'))

from app.database import engine
from sqlalchemy import text, inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Run the episode_number migration manually"""
    try:
        logger.info("Starting manual migration for episode_number column...")
        
        with engine.connect() as conn:
            # Check if column already exists
            inspector = inspect(engine)
            columns = inspector.get_columns('streams')
            column_names = [col['name'] for col in columns]
            
            if 'episode_number' in column_names:
                logger.info("Column episode_number already exists in streams table")
                return
            
            # Add the episode_number column
            logger.info("Adding episode_number column to streams table...")
            conn.execute(text("ALTER TABLE streams ADD COLUMN episode_number INTEGER"))
            conn.commit()
            logger.info("✅ Successfully added episode_number column to streams table")
            
    except Exception as e:
        logger.error(f"❌ Error adding episode_number column: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
