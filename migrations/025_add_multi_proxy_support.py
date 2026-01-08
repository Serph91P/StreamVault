"""
Migration 025: Add Multi-Proxy System Support

Adds support for multiple proxies with health checking and automatic failover.

Changes:
- Create proxy_settings table for multiple proxy configurations
- Add proxy management columns to recording_settings
- Migrate existing proxy from global_settings (if exists)

Background:
Current single-proxy setup creates single point of failure. When proxy goes down,
all recordings fail. Multi-proxy system provides redundancy and automatic failover.

Author: StreamVault
Date: 2025-11-13
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal


def upgrade():
    """Add multi-proxy support tables and columns"""
    with SessionLocal() as db:
        try:
            # Create proxy_settings table
            db.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS proxy_settings (
                    id SERIAL PRIMARY KEY,
                    proxy_url VARCHAR NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    enabled BOOLEAN NOT NULL DEFAULT true,
                    last_health_check TIMESTAMP WITH TIME ZONE,
                    health_status VARCHAR NOT NULL DEFAULT 'unknown',
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    average_response_time_ms INTEGER,
                    total_recordings INTEGER NOT NULL DEFAULT 0,
                    failed_recordings INTEGER NOT NULL DEFAULT 0,
                    success_rate FLOAT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                );
            """
                )
            )

            # Add indexes for performance
            db.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_proxy_enabled
                ON proxy_settings(enabled);
            """
                )
            )

            db.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_proxy_health
                ON proxy_settings(health_status);
            """
                )
            )

            db.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_proxy_priority
                ON proxy_settings(priority);
            """
                )
            )

            # Add new columns to recording_settings
            db.execute(
                text(
                    """
                ALTER TABLE recording_settings
                ADD COLUMN IF NOT EXISTS enable_proxy BOOLEAN NOT NULL DEFAULT true;
            """
                )
            )

            db.execute(
                text(
                    """
                ALTER TABLE recording_settings
                ADD COLUMN IF NOT EXISTS proxy_health_check_enabled BOOLEAN NOT NULL DEFAULT true;
            """
                )
            )

            db.execute(
                text(
                    """
                ALTER TABLE recording_settings
                ADD COLUMN IF NOT EXISTS proxy_health_check_interval_seconds INTEGER NOT NULL DEFAULT 300;
            """
                )
            )

            db.execute(
                text(
                    """
                ALTER TABLE recording_settings
                ADD COLUMN IF NOT EXISTS proxy_max_consecutive_failures INTEGER NOT NULL DEFAULT 3;
            """
                )
            )

            db.execute(
                text(
                    """
                ALTER TABLE recording_settings
                ADD COLUMN IF NOT EXISTS fallback_to_direct_connection BOOLEAN NOT NULL DEFAULT true;
            """
                )
            )

            # Migrate existing proxy from global_settings to proxy_settings (if exists)
            result = db.execute(
                text(
                    """
                SELECT http_proxy FROM global_settings
                WHERE http_proxy IS NOT NULL AND http_proxy != ''
                LIMIT 1;
            """
                )
            )

            existing_proxy = result.fetchone()
            if existing_proxy and existing_proxy[0]:
                proxy_url = existing_proxy[0]
                db.execute(
                    text(
                        """
                    INSERT INTO proxy_settings (proxy_url, priority, enabled, health_status)
                    VALUES (:proxy_url, 0, true, 'unknown')
                    ON CONFLICT DO NOTHING;
                """
                    ),
                    {"proxy_url": proxy_url},
                )
                print(f"✅ Migrated existing proxy: {proxy_url[:50]}...")

            db.commit()
            print("✅ Migration 025: Added multi-proxy support")
            print("   - Created proxy_settings table")
            print("   - Added proxy management columns to recording_settings")
            print("   - Migrated existing proxy configuration")

        except Exception as e:
            db.rollback()
            print(f"❌ Migration 025 failed: {e}")
            raise


def downgrade():
    """Remove multi-proxy support (rollback)"""
    with SessionLocal() as db:
        try:
            # Remove columns from recording_settings
            db.execute(text("ALTER TABLE recording_settings DROP COLUMN IF EXISTS fallback_to_direct_connection;"))
            db.execute(text("ALTER TABLE recording_settings DROP COLUMN IF EXISTS proxy_max_consecutive_failures;"))
            db.execute(
                text("ALTER TABLE recording_settings DROP COLUMN IF EXISTS proxy_health_check_interval_seconds;")
            )
            db.execute(text("ALTER TABLE recording_settings DROP COLUMN IF EXISTS proxy_health_check_enabled;"))
            db.execute(text("ALTER TABLE recording_settings DROP COLUMN IF EXISTS enable_proxy;"))

            # Drop indexes
            db.execute(text("DROP INDEX IF EXISTS idx_proxy_priority;"))
            db.execute(text("DROP INDEX IF EXISTS idx_proxy_health;"))
            db.execute(text("DROP INDEX IF EXISTS idx_proxy_enabled;"))

            # Drop table
            db.execute(text("DROP TABLE IF EXISTS proxy_settings;"))

            db.commit()
            print("✅ Migration 025 (downgrade): Removed multi-proxy support")

        except Exception as e:
            db.rollback()
            print(f"❌ Migration 025 downgrade failed: {e}")
            raise
