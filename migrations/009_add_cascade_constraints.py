#!/usr/bin/env python
"""
Migration 009: Update foreign key constraints with CASCADE
Updates foreign key constraints to add ON DELETE CASCADE where missing
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
    """Update foreign key constraints to add CASCADE where needed"""
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

        logger.info("🔄 Updating foreign key constraints...")

        # Helper function to update constraint
        def update_constraint(
            table_name, constraint_name, column_name, ref_table, ref_column="id"
        ):
            try:
                # Drop existing constraint
                session.execute(
                    text(
                        f"""
                    ALTER TABLE {table_name}
                    DROP CONSTRAINT IF EXISTS {constraint_name}
                """
                    )
                )

                # Add new constraint with CASCADE
                session.execute(
                    text(
                        f"""
                    ALTER TABLE {table_name}
                    ADD CONSTRAINT {constraint_name}
                    FOREIGN KEY ({column_name})
                    REFERENCES {ref_table}({ref_column})
                    ON DELETE CASCADE
                """
                    )
                )
                logger.info(f"✅ Updated {constraint_name} on {table_name}")
            except Exception as e:
                logger.warning(f"Could not update {constraint_name}: {e}")

        # Update active_recordings_state constraints
        update_constraint(
            "active_recordings_state",
            "active_recordings_state_stream_id_fkey",
            "stream_id",
            "streams",
        )

        update_constraint(
            "active_recordings_state",
            "active_recordings_state_recording_id_fkey",
            "recording_id",
            "recordings",
        )

        session.commit()
        logger.info("🎉 Migration 009 completed successfully")

    except Exception as e:
        logger.error(f"Migration 009 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()


if __name__ == "__main__":
    run_migration()
