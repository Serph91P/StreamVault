#!/usr/bin/env python
"""
Migration 017: Add chapters_xml_path column to stream_metadata
Adds a column to store XML chapter file paths for Emby/Jellyfin compatibility
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DatabaseError, OperationalError

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from app.config.settings import settings
from sqlalchemy.engine import Engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration(target_engine: Engine | None = None):
    """Add chapters_xml_path column to stream_metadata"""
    session = None
    try:
        # Validate DATABASE_URL
        if target_engine is None and not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")

        # Connect to the database
        engine = (
            target_engine
            if target_engine is not None
            else create_engine(settings.DATABASE_URL)
        )
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("🔄 Adding chapters_xml_path column to stream_metadata...")

        # Use SQLAlchemy's introspection for database-agnostic column checking
        inspector = inspect(engine)
        columns = inspector.get_columns("stream_metadata")
        column_names = [col["name"] for col in columns]

        if (
            "chapters_xml_path" in column_names
            and "tvshow_nfo_path" in column_names
            and "season_nfo_path" in column_names
        ):
            logger.info("✅ All required metadata path columns already exist, skipping")
            return True

        logger.info("🔄 Adding missing metadata path columns to stream_metadata...")

        # List of all metadata path columns that should exist and are actually used
        required_columns = {
            "chapters_xml_path": "TEXT",  # XML chapters for Emby/Jellyfin - actually generated
            "tvshow_nfo_path": "TEXT",  # TVShow NFO file path - actually generated
            "season_nfo_path": "TEXT",  # Season NFO file path - actually generated
        }

        # Security: Whitelist allowed columns and types for SQL safety
        allowed_columns = {"chapters_xml_path", "tvshow_nfo_path", "season_nfo_path"}
        allowed_types = {"TEXT"}

        columns_added = 0
        for column_name, column_type in required_columns.items():
            # Security validation
            if column_name not in allowed_columns or column_type not in allowed_types:
                logger.error(
                    f"❌ Column {column_name} with type {column_type} not in whitelist - skipping for security"
                )
                continue

            if column_name not in column_names:
                logger.info(f"🔄 Adding {column_name} column...")
                # Use hardcoded, whitelisted values for security
                if column_name == "chapters_xml_path":
                    session.execute(
                        text(
                            "ALTER TABLE stream_metadata ADD COLUMN chapters_xml_path TEXT"
                        )
                    )
                elif column_name == "tvshow_nfo_path":
                    session.execute(
                        text(
                            "ALTER TABLE stream_metadata ADD COLUMN tvshow_nfo_path TEXT"
                        )
                    )
                elif column_name == "season_nfo_path":
                    session.execute(
                        text(
                            "ALTER TABLE stream_metadata ADD COLUMN season_nfo_path TEXT"
                        )
                    )

                columns_added += 1
                logger.info(f"✅ Added {column_name} column to stream_metadata")
            else:
                logger.info(f"✅ Column {column_name} already exists, skipping")

        if columns_added > 0:
            session.commit()
            logger.info(f"✅ Added {columns_added} missing metadata path columns")
        else:
            logger.info("✅ All metadata path columns already exist")

        logger.info("✅ Migration 017 completed successfully")
        return True

    except (DatabaseError, OperationalError) as e:
        if session:
            session.rollback()
        logger.error(f"❌ Database operation failed: {e}")
        raise
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"❌ Migration 017 failed: {e}")
        raise
    finally:
        if session:
            session.close()


if __name__ == "__main__":
    run_migration()
