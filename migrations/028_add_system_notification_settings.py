"""Add system notification settings for recording events"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal


def upgrade():
    """Add notification preferences for recording events"""
    with SessionLocal() as db:
        try:
            # Add new columns to global_settings
            db.execute(
                text(
                    """
                ALTER TABLE global_settings
                ADD COLUMN IF NOT EXISTS notify_recording_started BOOLEAN DEFAULT false,
                ADD COLUMN IF NOT EXISTS notify_recording_failed BOOLEAN DEFAULT true,
                ADD COLUMN IF NOT EXISTS notify_recording_completed BOOLEAN DEFAULT false;
            """
                )
            )

            db.commit()
            print("✅ Migration 028: Added system notification settings for recording events")
            print("   - notify_recording_started: DEFAULT false (too noisy)")
            print("   - notify_recording_failed: DEFAULT true (CRITICAL)")
            print("   - notify_recording_completed: DEFAULT false (too noisy)")

        except Exception as e:
            db.rollback()
            print(f"❌ Migration 028 failed: {e}")
            raise


def downgrade():
    """Remove system notification settings"""
    with SessionLocal() as db:
        try:
            db.execute(
                text(
                    """
                ALTER TABLE global_settings
                DROP COLUMN IF EXISTS notify_recording_started,
                DROP COLUMN IF EXISTS notify_recording_failed,
                DROP COLUMN IF EXISTS notify_recording_completed;
            """
                )
            )

            db.commit()
            print("✅ Migration 028: Removed system notification settings")

        except Exception as e:
            db.rollback()
            print(f"❌ Migration 028 downgrade failed: {e}")
            raise


if __name__ == "__main__":
    print("Running migration 028: Add system notification settings for recording events...")
    upgrade()
    print("Migration 028 completed successfully!")
