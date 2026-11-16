"""Recording config caches own sessions and contain immutable values, not ORM rows."""

from dataclasses import FrozenInstanceError, fields, is_dataclass
from threading import get_ident

import pytest
from sqlalchemy import event, inspect, update
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import RecordingSettings, Streamer, StreamerRecordingSettings
from app.services.recording.config_manager import ConfigManager
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
async def test_recording_configuration_is_scoped_closed_and_snapshot_only(tmp_path):
    lifecycles = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (label + '.db')}")
        for label in ("first", "second")
    ]
    managers = []
    query_threads = []
    open_sessions = set()
    main_thread = get_ident()

    def began(session, _transaction, _connection):
        open_sessions.add(id(session))

    def ended(session, _transaction):
        if not session.in_transaction():
            open_sessions.discard(id(session))

    try:
        for label, lifecycle in zip(("first", "second"), lifecycles, strict=True):
            with lifecycle.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with lifecycle.sync_session_factory() as session:
                session.add_all(
                    [
                        Streamer(id=1, twitch_id=label, username=label),
                        RecordingSettings(
                            id=1,
                            enabled=True,
                            default_quality=label,
                            max_streams_per_streamer=3,
                        ),
                        StreamerRecordingSettings(
                            streamer_id=1, quality=None, enabled=True
                        ),
                    ]
                )
                session.flush()
                # INSERT defaults replace Python None; exercise a persisted NULL.
                session.execute(update(StreamerRecordingSettings).values(quality=None))
                session.commit()
            event.listen(
                lifecycle.sync_engine,
                "before_cursor_execute",
                lambda *_args: query_threads.append(get_ident()),
            )
            configuration = Settings(
                _env_file=None,
                ENVIRONMENT="test",
                RECORDING_DIRECTORY=str(tmp_path / label),
            )
            managers.append(
                ConfigManager(
                    session_factory=lambda lifecycle=lifecycle: (
                        lifecycle.sync_session_factory()
                    ),
                    settings=configuration,
                )
            )
        assert query_threads == []
        event.listen(Session, "after_begin", began)
        event.listen(Session, "after_transaction_end", ended)
        try:
            for label, manager in zip(("first", "second"), managers, strict=True):
                global_value = await run_in_thread_pool(manager.get_global_settings)
                streamer_value = await run_in_thread_pool(
                    manager.get_streamer_settings, 1
                )
                assert not open_sessions
                assert is_dataclass(global_value) and is_dataclass(streamer_value)
                assert inspect(global_value, raiseerr=False) is None
                assert inspect(streamer_value, raiseerr=False) is None
                assert {field.name for field in fields(global_value)} == {
                    column.key for column in RecordingSettings.__table__.columns
                }
                assert {field.name for field in fields(streamer_value)} == {
                    column.key for column in StreamerRecordingSettings.__table__.columns
                }
                assert global_value.default_quality == label
                assert await run_in_thread_pool(manager.get_quality_setting, 1) == label
                assert manager.get_output_directory() == str(tmp_path / label)
                assert manager.get_recordings_directory() == str(tmp_path / label)
                with pytest.raises(FrozenInstanceError):
                    global_value.enabled = False
                previous = len(query_threads)
                assert manager.get_global_settings() is global_value
                assert len(query_threads) == previous
            assert query_threads and main_thread not in query_threads
        finally:
            event.remove(Session, "after_begin", began)
            event.remove(Session, "after_transaction_end", ended)
        with lifecycles[0].sync_session_factory() as session:
            session.get(RecordingSettings, 1).default_quality = "updated"
            session.commit()
        assert await run_in_thread_pool(managers[0].get_quality_setting, 1) == "first"
        managers[0].invalidate_cache()
        assert await run_in_thread_pool(managers[0].get_quality_setting, 1) == "updated"
        assert await run_in_thread_pool(managers[1].get_quality_setting, 1) == "second"
        assert ConfigManager().get_recordings_directory() == "/recordings"
    finally:
        for lifecycle in lifecycles:
            await lifecycle.adispose()
