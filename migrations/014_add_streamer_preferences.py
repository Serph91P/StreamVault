#!/usr/bin/env python
"""
Migration 014: Add streamer preferences and missing table columns
Adds is_favorite/auto_record to streamers and missing columns to other tables
"""
import os
import sys
import logging
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
    """Add preference fields to streamers and missing columns to other tables"""
    session = None
    try:
        # Validate DATABASE_URL
        if not settings.DATABASE_URL:
            raise ValueError("DATABASE_URL not configured")

        # Connect to the database
        engine = create_engine(settings.DATABASE_URL, echo=False)
        Session = sessionmaker(bind=engine)
        session = Session()

        logger.info("🔄 Adding missing columns and preferences...")

        # 1. Add preference fields to streamers table
        session.execute(
            text(
                """
            ALTER TABLE streamers
            ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN DEFAULT FALSE
        """
            )
        )
        logger.info("✅ Added is_favorite column to streamers table")

        session.execute(
            text(
                """
            ALTER TABLE streamers
            ADD COLUMN IF NOT EXISTS auto_record BOOLEAN DEFAULT FALSE
        """
            )
        )
        logger.info("✅ Added auto_record column to streamers table")

        # 2. Add missing columns to push_subscriptions table
        try:
            session.execute(
                text(
                    """
                ALTER TABLE push_subscriptions
                ADD COLUMN IF NOT EXISTS p256dh_key TEXT
            """
                )
            )
            session.execute(
                text(
                    """
                ALTER TABLE push_subscriptions
                ADD COLUMN IF NOT EXISTS auth_key TEXT
            """
                )
            )
            session.execute(
                text(
                    """
                ALTER TABLE push_subscriptions
                ADD COLUMN IF NOT EXISTS user_agent TEXT
            """
                )
            )
            session.execute(
                text(
                    """
                ALTER TABLE push_subscriptions
                ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE
            """
                )
            )
            session.execute(
                text(
                    """
                ALTER TABLE push_subscriptions
                ADD COLUMN IF NOT EXISTS last_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            """
                )
            )
            logger.info("✅ Added missing columns to push_subscriptions")
        except (DatabaseError, OperationalError) as e:
            logger.warning(f"Database error while adding push_subscriptions columns: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error while adding push_subscriptions columns: {e}")

        # 3. Add indexes for performance
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_streamers_is_favorite
            ON streamers(is_favorite)
        """
            )
        )
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_streamers_auto_record
            ON streamers(auto_record)
        """
            )
        )
        logger.info("✅ Added streamers preference indexes")

        # 4. Add missing indexes from old migrations
        try:
            # Stream events indexes
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_stream_events_stream_id ON stream_events(stream_id)
            """
                )
            )
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_stream_events_event_type ON stream_events(event_type)
            """
                )
            )
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_stream_events_timestamp ON stream_events(timestamp)
            """
                )
            )

            # Other table indexes
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_notification_settings_streamer_id ON notification_settings(streamer_id)
            """
                )
            )
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_stream_metadata_stream_id ON stream_metadata(stream_id)
            """
                )
            )
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_streamer_recording_settings_streamer_id ON streamer_recording_settings(streamer_id)
            """
                )
            )
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_active_recordings_process_id ON active_recordings_state(process_id)
            """
                )
            )
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_active_recordings_status ON active_recordings_state(status)
            """
                )
            )
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_active_recordings_heartbeat ON active_recordings_state(last_heartbeat)
            """
                )
            )

            logger.info("✅ Added missing indexes")
        except (DatabaseError, OperationalError) as e:
            logger.warning(f"Database error while adding indexes: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error while adding indexes: {e}")

        # 5. Create trigger for push_subscriptions updated_at
        try:
            session.execute(
                text(
                    """
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql'
            """
                )
            )

            session.execute(
                text(
                    """
                DROP TRIGGER IF EXISTS update_push_subscriptions_updated_at ON push_subscriptions
            """
                )
            )

            session.execute(
                text(
                    """
                CREATE TRIGGER update_push_subscriptions_updated_at
                    BEFORE UPDATE ON push_subscriptions
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column()
            """
                )
            )

            logger.info("✅ Added trigger functions and triggers")
        except (DatabaseError, OperationalError) as e:
            logger.warning(f"Database error while adding triggers: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error while adding triggers: {e}")

        session.commit()
        logger.info("🎉 Migration 014 completed successfully")

    except Exception as e:
        logger.error(f"❌ Migration 014 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session:
            session.close()


if __name__ == "__main__":
    run_migration()
