"""
Migration 035: Add Segments Directory Path Tracking

Adds column to track the segments directory path in StreamMetadata.

Problem:
- Segments directory was not tracked in database
- Cleanup relied on pattern matching (_segments suffix)
- Could miss or delete wrong directories

Solution:
- Store segments_dir_path in StreamMetadata
- Cleanup uses exact DB path instead of pattern matching
- Enables proper cleanup verification

Changes:
- Add segments_dir_path column to stream_metadata table
- Add segments_removed column (boolean) to track cleanup status
"""

import logging
from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger("streamvault")


from sqlalchemy.engine import Engine
from app.services.system.migration_service import migration_session


def run_migration(target_engine: Engine | None = None):
    """
    Add segments directory path tracking to stream_metadata.
    """

    with migration_session(target_engine, SessionLocal) as session:
        try:
            logger.info("🔄 Running Migration 035: Add Segments Directory Path")

            # === STEP 1: Check if column already exists (idempotency) ===
            check_result = session.execute(
                text(
                    """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'stream_metadata'
                AND column_name = 'segments_dir_path'
                """
                )
            ).fetchone()

            if check_result:
                logger.info("✅ Column segments_dir_path already exists, skipping")
            else:
                # Add segments_dir_path column
                session.execute(
                    text(
                        """
                    ALTER TABLE stream_metadata
                    ADD COLUMN segments_dir_path VARCHAR(500)
                    """
                    )
                )
                logger.info("✅ Added segments_dir_path column to stream_metadata")

            # === STEP 2: Add segments_removed column ===
            check_result2 = session.execute(
                text(
                    """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'stream_metadata'
                AND column_name = 'segments_removed'
                """
                )
            ).fetchone()

            if check_result2:
                logger.info("✅ Column segments_removed already exists, skipping")
            else:
                session.execute(
                    text(
                        """
                    ALTER TABLE stream_metadata
                    ADD COLUMN segments_removed BOOLEAN DEFAULT FALSE
                    """
                    )
                )
                logger.info("✅ Added segments_removed column to stream_metadata")

            session.commit()
            logger.info("✅ Migration 035 completed successfully")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 035 failed: {e}")
            raise


def rollback_migration():
    """Rollback migration 035"""
    with SessionLocal() as session:
        try:
            logger.info("🔄 Rolling back Migration 035")

            # Remove columns if they exist
            session.execute(
                text(
                    """
                ALTER TABLE stream_metadata
                DROP COLUMN IF EXISTS segments_dir_path,
                DROP COLUMN IF EXISTS segments_removed
                """
                )
            )

            session.commit()
            logger.info("✅ Migration 035 rollback completed")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 035 rollback failed: {e}")
            raise
