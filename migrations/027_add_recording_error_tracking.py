"""Add error tracking columns to Recording table for failure detection"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal


def upgrade():
    """Add error tracking columns to recordings table"""
    with SessionLocal() as db:
        try:
            # Add error tracking columns
            db.execute(
                text(
                    """
                ALTER TABLE recordings
                ADD COLUMN IF NOT EXISTS error_message TEXT,
                ADD COLUMN IF NOT EXISTS failure_reason VARCHAR(255),
                ADD COLUMN IF NOT EXISTS failure_timestamp TIMESTAMP WITH TIME ZONE;
            """
                )
            )

            db.commit()
            print("✅ Migration 027: Added error tracking columns to recordings table")

        except Exception as e:
            db.rollback()
            print(f"❌ Migration 027 failed: {e}")
            raise


def downgrade():
    """Remove error tracking columns"""
    with SessionLocal() as db:
        try:
            db.execute(
                text(
                    """
                ALTER TABLE recordings
                DROP COLUMN IF EXISTS error_message,
                DROP COLUMN IF EXISTS failure_reason,
                DROP COLUMN IF EXISTS failure_timestamp;
            """
                )
            )

            db.commit()
            print("✅ Migration 027: Removed error tracking columns")

        except Exception as e:
            db.rollback()
            print(f"❌ Migration 027 downgrade failed: {e}")
            raise


if __name__ == "__main__":
    print("Running migration 027: Add recording error tracking...")
    upgrade()
    print("Migration 027 completed successfully!")
