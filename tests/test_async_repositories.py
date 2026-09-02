"""
Phase 2 persistence foundation: async repositories.

Repositories use AsyncSession/select and caller-owned ``session.begin()``
boundaries. Repository writes may add/flush but must never commit or
rollback; these tests verify that via explicit rollback after a write.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.database import Base, DatabaseLifecycle
from app.models import Stream, Streamer

from app.services.core.async_repositories import (
    AsyncGlobalSettingsRepository,
    AsyncRecordingRepository,
    AsyncStreamerRepository,
)


@pytest.fixture
def async_session_factory(tmp_path):
    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'repositories.db'}")
    Base.metadata.create_all(lifecycle.sync_engine)
    yield lifecycle.async_session_factory
    lifecycle.dispose_sync()


def _now():
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_streamer_repo_create_read_roundtrip(async_session_factory):
    async with async_session_factory() as session:
        async with session.begin():
            repo = AsyncStreamerRepository(session)
            created = await repo.create(
                twitch_id="twitch-1",
                username="StreamerOne",
                is_live=False,
                last_updated=_now(),
                is_test_data=True,
            )
            assert created.id is not None

    async with async_session_factory() as session:
        repo = AsyncStreamerRepository(session)
        streamers = await repo.get_all(include_test_data=True)
        assert [streamer.username for streamer in streamers] == ["StreamerOne"]


@pytest.mark.asyncio
async def test_streamer_repo_excludes_test_data_by_default(
    async_session_factory,
):
    async with async_session_factory() as session:
        async with session.begin():
            repo = AsyncStreamerRepository(session)
            await repo.create(
                twitch_id="twitch-2",
                username="RealOne",
                is_live=False,
                last_updated=_now(),
                is_test_data=False,
            )
            await repo.create(
                twitch_id="twitch-3",
                username="TestTwo",
                is_live=False,
                last_updated=_now(),
                is_test_data=True,
            )

    async with async_session_factory() as session:
        repo = AsyncStreamerRepository(session)
        streamers = await repo.get_all()
        assert [streamer.username for streamer in streamers] == ["RealOne"]


@pytest.mark.asyncio
async def test_streamer_repo_lookup_by_twitch_id(async_session_factory):
    async with async_session_factory() as session:
        async with session.begin():
            repo = AsyncStreamerRepository(session)
            created = await repo.create(
                twitch_id="twitch-4",
                username="ByTwitch",
                is_live=True,
                last_updated=_now(),
                is_test_data=True,
            )

    async with async_session_factory() as session:
        repo = AsyncStreamerRepository(session)
        found = await repo.get_by_twitch_id("twitch-4")
        assert found is not None
        assert found.id == created.id
        assert await repo.get_by_twitch_id("missing") is None


@pytest.mark.asyncio
async def test_streamer_repo_create_does_not_hidden_commit(
    async_session_factory,
):
    async with async_session_factory() as session:
        repo = AsyncStreamerRepository(session)
        await repo.create(
            twitch_id="twitch-rollback",
            username="MustNotPersist",
            is_live=False,
            last_updated=_now(),
            is_test_data=True,
        )
        # Caller-owned transaction boundary: the write must still be
        # rollback-able, proving the repository never committed.
        await session.rollback()

    async with async_session_factory() as session:
        repo = AsyncStreamerRepository(session)
        assert await repo.get_by_twitch_id("twitch-rollback") is None


@pytest.mark.asyncio
async def test_recording_repo_lifecycle(async_session_factory):
    async with async_session_factory() as session:
        async with session.begin():
            streamer = Streamer(
                twitch_id="twitch-rec",
                username="RecordingStreamer",
                is_live=False,
                last_updated=_now(),
                is_test_data=True,
            )
            session.add(streamer)
            await session.flush()
            stream = Stream(
                streamer_id=streamer.id,
                title="A stream",
                started_at=_now(),
            )
            session.add(stream)
            await session.flush()
            stream_id = stream.id

        async with session.begin():
            repo = AsyncRecordingRepository(session)
            recording = await repo.create(
                stream_id=stream_id,
                start_time=_now(),
                status="recording",
            )
            recording_id = recording.id
            assert recording_id is not None

        async with session.begin():
            repo = AsyncRecordingRepository(session)
            fetched = await repo.get_by_id(recording_id)
            assert fetched is not None
            assert fetched.status == "recording"
            assert [r.id for r in await repo.list_for_stream(stream_id)] == [
                recording_id
            ]

        now = _now()
        async with session.begin():
            repo = AsyncRecordingRepository(session)
            await repo.end(
                fetched,
                ended_at=now,
                status="completed",
                path="/recordings/out.mp4",
                duration=120,
            )
            assert fetched.end_time == now
            assert fetched.status == "completed"


@pytest.mark.asyncio
async def test_recording_repo_write_does_not_hidden_commit(
    async_session_factory,
):
    async with async_session_factory() as session:
        async with session.begin():
            streamer = Streamer(
                twitch_id="twitch-rec-rollback",
                username="RecRollback",
                is_live=False,
                last_updated=_now(),
                is_test_data=True,
            )
            session.add(streamer)
            await session.flush()
            stream = Stream(
                streamer_id=streamer.id,
                title="A stream",
                started_at=_now(),
            )
            session.add(stream)
            await session.flush()
            stream_id = stream.id

        repo = AsyncRecordingRepository(session)
        await repo.create(
            stream_id=stream_id,
            start_time=_now(),
            status="recording",
        )
        await session.rollback()

        async with session.begin():
            await session.execute(text("DELETE FROM streams"))
            await session.execute(text("DELETE FROM streamers"))

    async with async_session_factory() as session:
        count = (
            await session.execute(text("SELECT COUNT(*) FROM recordings"))
        ).scalar()
        assert count == 0


@pytest.mark.asyncio
async def test_global_settings_repo_singleton_and_update(async_session_factory):
    async with async_session_factory() as session:
        async with session.begin():
            repo = AsyncGlobalSettingsRepository(session)
            settings = await repo.get_singleton()
            settings_id = settings.id
            await repo.update(settings, notifications_enabled=False)

    async with async_session_factory() as session:
        repo = AsyncGlobalSettingsRepository(session)
        settings = await repo.get_singleton()
        assert settings.id == settings_id
        assert settings.notifications_enabled is False


@pytest.mark.asyncio
async def test_global_settings_repo_write_does_not_hidden_commit(
    async_session_factory,
):
    async with async_session_factory() as session:
        repo = AsyncGlobalSettingsRepository(session)
        settings = await repo.get_singleton()
        await repo.update(settings, notifications_enabled=False)
        await session.rollback()

    async with async_session_factory() as session:
        repo = AsyncGlobalSettingsRepository(session)
        settings = await repo.get_singleton()
        assert settings.notifications_enabled is True


@pytest.mark.asyncio
async def test_async_db_utils_get_all_streamers_uses_repository(
    async_session_factory, monkeypatch
):
    import app.utils.async_db_utils as async_db_utils

    async with async_session_factory() as session:
        async with session.begin():
            repo = AsyncStreamerRepository(session)
            await repo.create(
                twitch_id="twitch-util",
                username="UtilStreamer",
                is_live=False,
                last_updated=_now(),
                is_test_data=True,
            )

    monkeypatch.setattr(
        async_db_utils,
        "get_async_session_maker",
        lambda: async_session_factory,
    )
    streamers = await async_db_utils.get_all_streamers()
    assert [streamer.username for streamer in streamers] == ["UtilStreamer"]
