#!/usr/bin/env python
"""
Migration 015: Add default settings data
Inserts default recording settings to ensure system works correctly
"""
import os
import sys
import logging
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DatabaseError, OperationalError

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add default settings data to ensure system functionality"""
    session = None
    try:
        # Validate DATABASE_URL
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")
        
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL, echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Adding default settings data...")
        
        # 1. Ensure recording_settings has a default row
        try:
            # Check if recording_settings is empty
            result = session.execute(text("SELECT COUNT(*) FROM recording_settings")).scalar()
            
            if result == 0:
                logger.info("🔄 Inserting default recording settings...")
                
                # Create default cleanup policy as proper dictionary
                default_cleanup_policy = {
                    "enabled": False,
                    "days_to_keep": 30,
                    "max_size_gb": 100
                }
                
                session.execute(text("""
                    INSERT INTO recording_settings (
                        enabled, 
                        output_directory, 
                        filename_template, 
                        default_quality, 
                        use_chapters, 
                        filename_preset, 
                        use_category_as_chapter_title, 
                        max_streams_per_streamer, 
                        cleanup_policy
                    ) VALUES (
                        :enabled, 
                        :output_directory, 
                        :filename_template, 
                        :default_quality, 
                        :use_chapters, 
                        :filename_preset, 
                        :use_category_as_chapter_title, 
                        :max_streams_per_streamer, 
                        :cleanup_policy
                    )
                """), {
                    "enabled": True,
                    "output_directory": "/recordings",
                    "filename_template": "{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
                    "default_quality": "best",
                    "use_chapters": True,
                    "filename_preset": "default",
                    "use_category_as_chapter_title": False,
                    "max_streams_per_streamer": 0,
                    "cleanup_policy": json.dumps(default_cleanup_policy)
                })
                
                session.commit()
                logger.info("✅ Added default recording settings")
            else:
                logger.info("Recording settings already exist, skipping default insertion")
                
        except (DatabaseError, OperationalError) as e:
            session.rollback()
            logger.warning(f"Database error while adding recording settings: {e}")
        except Exception as e:
            session.rollback()
            logger.warning(f"Unexpected error while adding recording settings: {e}")
        
        # 2. Ensure global_settings has a default row
        try:
            # Check if global_settings is empty
            result = session.execute(text("SELECT COUNT(*) FROM global_settings")).scalar()
            
            if result == 0:
                logger.info("🔄 Inserting default global settings...")
                session.execute(text("""
                    INSERT INTO global_settings (
                        check_interval, 
                        max_concurrent_recordings, 
                        default_download_folder, 
                        http_proxy, 
                        https_proxy
                    ) VALUES (
                        :check_interval, 
                        :max_concurrent_recordings, 
                        :default_download_folder, 
                        :http_proxy, 
                        :https_proxy
                    )
                """), {
                    "check_interval": 60,
                    "max_concurrent_recordings": 3,
                    "default_download_folder": "/recordings",
                    "http_proxy": None,
                    "https_proxy": None
                })
                
                session.commit()
                logger.info("✅ Added default global settings")
            else:
                logger.info("Global settings already exist, skipping default insertion")
                
        except (DatabaseError, OperationalError) as e:
            session.rollback()
            logger.warning(f"Database error while adding global settings: {e}")
        except Exception as e:
            session.rollback()
            logger.warning(f"Unexpected error while adding global settings: {e}")
        
        # 3. Add default categories if none exist
        try:
            # Check if categories table is empty
            result = session.execute(text("SELECT COUNT(*) FROM categories")).scalar()
            
            if result == 0:
                logger.info("🔄 Adding default categories...")
                default_categories = [
                    "Just Chatting",
                    "Games + Demos", 
                    "Music",
                    "Art",
                    "ASMR",
                    "Talk Shows & Podcasts",
                    "Software and Game Development"
                ]
                
                for category in default_categories:
                    session.execute(text("""
                        INSERT INTO categories (name, description) 
                        VALUES (:name, :description)
                    """), {
                        "name": category, 
                        "description": f"Default category: {category}"
                    })
                
                session.commit()
                logger.info(f"✅ Added {len(default_categories)} default categories")
            else:
                logger.info("Categories already exist, skipping default insertion")
                
        except (DatabaseError, OperationalError) as e:
            session.rollback()
            logger.warning(f"Database error while adding categories: {e}")
        except Exception as e:
            session.rollback()
            logger.warning(f"Unexpected error while adding categories: {e}")
        
        logger.info("🎉 Migration 015 completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration 015 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    run_migration()
