"""Add is_test_data flag to streamers for test data isolation"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal


def upgrade():
    """Add is_test_data flag to streamers table"""
    with SessionLocal() as db:
        try:
            # Add is_test_data column to streamers
            db.execute(
                text(
                    """
                ALTER TABLE streamers
                ADD COLUMN IF NOT EXISTS is_test_data BOOLEAN DEFAULT false NOT NULL;
            """
                )
            )

            # Create index for efficient filtering
            db.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_streamers_test_data
                ON streamers(is_test_data);
            """
                )
            )

            db.commit()
            print("✅ Migration 029: Added is_test_data flag to streamers")
            print("   - is_test_data column: BOOLEAN DEFAULT false NOT NULL")
            print("   - idx_streamers_test_data: Index for filtering test data")
            print("   - Purpose: Isolate test streamers from frontend queries")

        except Exception as e:
            db.rollback()
            print(f"❌ Migration 029 failed: {e}")
            raise


def downgrade():
    """Remove is_test_data flag"""
    with SessionLocal() as db:
        try:
            db.execute(text("DROP INDEX IF EXISTS idx_streamers_test_data;"))
            db.execute(text("ALTER TABLE streamers DROP COLUMN IF EXISTS is_test_data;"))

            db.commit()
            print("✅ Migration 029: Removed is_test_data flag from streamers")

        except Exception as e:
            db.rollback()
            print(f"❌ Migration 029 downgrade failed: {e}")
            raise


if __name__ == "__main__":
    print("Running migration 029: Add is_test_data flag for test data isolation...")
    upgrade()
    print("Migration 029 completed successfully!")
