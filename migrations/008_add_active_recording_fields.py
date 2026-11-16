#!/usr/bin/env python
"""
Migration 008: Add fields to active_recordings_state
Adds last_heartbeat, config_json, created_at, updated_at columns
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings
from sqlalchemy.engine import Engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration(target_engine: Engine | None = None):
    """Add additional fields to active_recordings_state table"""
    session = None
    try:
        # Connect to the database
        engine = (
            target_engine
            if target_engine is not None
            else create_engine(settings.DATABASE_URL)
        )
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("🔄 Adding fields to active_recordings_state...")

        # Add last_heartbeat column
        session.execute(
            text(
                """
            ALTER TABLE active_recordings_state
            ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        """
            )
        )
        logger.info("✅ Added last_heartbeat column")

        # Add config_json column
        session.execute(
            text(
                """
            ALTER TABLE active_recordings_state
            ADD COLUMN IF NOT EXISTS config_json TEXT
        """
            )
        )
        logger.info("✅ Added config_json column")

        # Add created_at column
        session.execute(
            text(
                """
            ALTER TABLE active_recordings_state
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        """
            )
        )
        logger.info("✅ Added created_at column")

        # Add updated_at column
        session.execute(
            text(
                """
            ALTER TABLE active_recordings_state
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        """
            )
        )
        logger.info("✅ Added updated_at column")

        # Create heartbeat index for monitoring stale processes
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_active_recordings_heartbeat
            ON active_recordings_state (last_heartbeat)
        """
            )
        )
        logger.info("✅ Added heartbeat index")

        # Create status index
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_active_recordings_status
            ON active_recordings_state (status)
        """
            )
        )
        logger.info("✅ Added status index")

        session.commit()
        logger.info("🎉 Migration 008 completed successfully")

    except Exception as e:
        logger.error(f"Migration 008 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()


if __name__ == "__main__":
    run_migration()
