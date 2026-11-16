"""A real app's configured metadata root excludes a foreign catalog's files."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.bootstrap.application import create_app
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import Stream, Streamer, StreamMetadata


@pytest.mark.asyncio
@pytest.mark.parametrize("symlink", [False, True])
async def test_metadata_rejects_an_authoritative_path_outside_its_application_root(
    tmp_path, symlink
):
    roots = [tmp_path / name for name in ("owner", "peer")]
    for root in roots:
        (root / ".media").mkdir(parents=True)
        (root / "alice").mkdir()
    foreign = roots[1] / "alice" / "capture.ts"
    foreign.write_bytes(b"peer original recording")
    if symlink:
        link = roots[0] / "alice" / "peer-link"
        link.symlink_to(foreign.parent, target_is_directory=True)
        recorded_path = link / foreign.name
    else:
        recorded_path = foreign
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'metadata-guard.db'}")
    application = create_app(
        Settings(
            ENVIRONMENT="test",
            RECORDING_DIRECTORY=str(roots[0]),
            LOGS_BASE_DIR=str(tmp_path / "logs"),
            _env_file=None,
        ),
        database=database,
    )
    handlers = application.state.background_queue_manager.task_handlers
    before = {
        str(path.relative_to(roots[1])): path.read_bytes()
        for path in roots[1].rglob("*")
        if path.is_file()
    }
    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(Streamer(id=1, username="alice", twitch_id="alice"))
            session.flush()
            started = datetime(2026, 11, 1, tzinfo=timezone.utc)
            session.add(
                Stream(
                    id=1,
                    streamer_id=1,
                    title="Owner stream",
                    recording_path=str(recorded_path),
                    started_at=started,
                    ended_at=started + timedelta(minutes=5),
                )
            )
            session.commit()
        assert (
            await handlers.metadata_service.generate_metadata_for_stream(
                1, str(recorded_path.parent), "capture"
            )
            is False
        )
        assert {
            str(path.relative_to(roots[1])): path.read_bytes()
            for path in roots[1].rglob("*")
            if path.is_file()
        } == before
        with database.sync_session_factory() as session:
            assert session.scalar(select(func.count()).select_from(StreamMetadata)) == 0
            assert session.get(Stream, 1).recording_path == str(recorded_path)
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await handlers.cleanup()
        await application.state.websocket_manager.close_all()
        await database.adispose()
