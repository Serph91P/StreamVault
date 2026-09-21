import unittest
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Streamer, StreamerRecordingSettings
from app.routes.recording import update_streamer_recording_settings
from app.schemas.recording import StreamerRecordingSettingsSchema
from app.services.recording.twitch_auth_scheduler import (
    AuthCandidate,
    AuthDecisionKind,
    TwitchAuthScheduler,
)

migration_043_auth_priority = import_module(
    "migrations.043_add_twitch_auth_priority"
)


NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def candidate(
    channel_key: str,
    priority: int,
    *,
    recording_id: int,
    age_seconds: int,
    authenticated: bool = False,
    anonymous_available: bool = True,
    purpose: str = "RECORDING",
    eligible: bool = True,
) -> AuthCandidate:
    return AuthCandidate(
        channel_key=channel_key,
        recording_id=recording_id,
        priority=priority,
        started_at=NOW - timedelta(seconds=age_seconds),
        authenticated=authenticated,
        anonymous_available=anonymous_available,
        purpose=purpose,
        eligible=eligible,
    )


class TwitchAuthPrioritySchedulerTests(unittest.TestCase):
    def test_priority_schema_accepts_documented_range_and_defaults_to_zero(self) -> None:
        self.assertEqual(
            StreamerRecordingSettingsSchema(streamer_id=1).twitch_auth_priority, 0
        )
        self.assertEqual(
            StreamerRecordingSettingsSchema(
                streamer_id=1, twitch_auth_priority=-1000
            ).twitch_auth_priority,
            -1000,
        )
        self.assertEqual(
            StreamerRecordingSettingsSchema(
                streamer_id=1, twitch_auth_priority=1000
            ).twitch_auth_priority,
            1000,
        )

        for invalid in (-1001, 1001):
            with self.assertRaises(ValidationError):
                StreamerRecordingSettingsSchema(
                    streamer_id=1, twitch_auth_priority=invalid
                )

    def test_no_owner_selects_highest_priority_then_oldest_then_recording_id(self) -> None:
        decision = TwitchAuthScheduler().decide(
            [
                candidate("newer", 10, recording_id=30, age_seconds=10),
                candidate("older-high-id", 10, recording_id=20, age_seconds=20),
                candidate("older-low-id", 10, recording_id=10, age_seconds=20),
                candidate(
                    "ineligible", 100, recording_id=1, age_seconds=100, eligible=False
                ),
            ]
        )

        self.assertIs(decision.kind, AuthDecisionKind.PROMOTE)
        self.assertEqual(decision.owner_channel_key, "older-low-id")
        self.assertEqual(decision.requested_channel_key, "older-low-id")

    def test_equal_priority_keeps_current_owner_without_churn(self) -> None:
        decision = TwitchAuthScheduler().decide(
            [
                candidate(
                    "owner", 10, recording_id=2, age_seconds=5, authenticated=True
                ),
                candidate("older", 10, recording_id=1, age_seconds=100),
            ]
        )

        self.assertIs(decision.kind, AuthDecisionKind.KEEP)
        self.assertEqual(decision.owner_channel_key, "owner")
        self.assertFalse(decision.pending_handoff)

    def test_higher_priority_preempts_only_anonymously_continuable_recording(self) -> None:
        decision = TwitchAuthScheduler().decide(
            [
                candidate(
                    "owner",
                    0,
                    recording_id=1,
                    age_seconds=100,
                    authenticated=True,
                    anonymous_available=True,
                ),
                candidate("preferred", 100, recording_id=2, age_seconds=1),
            ]
        )

        self.assertIs(decision.kind, AuthDecisionKind.HANDOFF)
        self.assertEqual(decision.owner_channel_key, "owner")
        self.assertEqual(decision.requested_channel_key, "preferred")
        self.assertEqual(decision.displaced_channel_key, "owner")
        self.assertTrue(decision.pending_handoff)
        self.assertEqual(decision.reason, "higher_priority_recording")

    def test_protected_or_live_owner_blocks_handoff_without_termination(self) -> None:
        cases = (
            (False, "RECORDING", "owner_anonymous_unavailable"),
            (True, "LIVE", "live_playback_owner_not_preemptible"),
        )
        for anonymous_available, purpose, reason in cases:
            with self.subTest(purpose=purpose, anonymous_available=anonymous_available):
                decision = TwitchAuthScheduler().decide(
                    [
                        candidate(
                            "owner",
                            0,
                            recording_id=1,
                            age_seconds=100,
                            authenticated=True,
                            anonymous_available=anonymous_available,
                            purpose=purpose,
                        ),
                        candidate("preferred", 100, recording_id=2, age_seconds=1),
                    ]
                )

                self.assertIs(decision.kind, AuthDecisionKind.BLOCKED)
                self.assertEqual(decision.owner_channel_key, "owner")
                self.assertEqual(decision.requested_channel_key, "preferred")
                self.assertFalse(decision.pending_handoff)
                self.assertEqual(decision.reason, reason)

    def test_recording_settings_api_round_trips_priority(self) -> None:
        with TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'settings.db'}")
            Base.metadata.create_all(
                engine,
                tables=[Streamer.__table__, StreamerRecordingSettings.__table__],
            )
            Session = sessionmaker(bind=engine, expire_on_commit=False)
            with Session() as db:
                streamer = Streamer(twitch_id="123", username="priority-channel")
                db.add(streamer)
                db.commit()
                response = __import__("asyncio").run(
                    update_streamer_recording_settings(
                        streamer.id,
                        StreamerRecordingSettingsSchema(
                            streamer_id=streamer.id,
                            twitch_auth_priority=100,
                        ),
                        db,
                    )
                )
                persisted = db.query(StreamerRecordingSettings).one()

            self.assertEqual(response.twitch_auth_priority, 100)
            self.assertEqual(persisted.twitch_auth_priority, 100)
            engine.dispose()

    def test_migration_adds_compatible_zero_priority_and_is_idempotent(self) -> None:
        with TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'migration.db'}")
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE streamer_recording_settings "
                        "(id INTEGER PRIMARY KEY, streamer_id INTEGER NOT NULL)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO streamer_recording_settings (id, streamer_id) "
                        "VALUES (1, 99)"
                    )
                )

            migration_043_auth_priority.upgrade(engine)
            migration_043_auth_priority.upgrade(engine)

            columns = {
                column["name"]
                for column in inspect(engine).get_columns("streamer_recording_settings")
            }
            with engine.connect() as connection:
                priority = connection.execute(
                    text(
                        "SELECT twitch_auth_priority FROM streamer_recording_settings "
                        "WHERE id = 1"
                    )
                ).scalar_one()

            self.assertIn("twitch_auth_priority", columns)
            self.assertEqual(priority, 0)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
