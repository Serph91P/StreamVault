"""Retention policy semantics and preview purity use real owned files/catalogs."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.models import RecordingSettings, Stream, Streamer, StreamerRecordingSettings
from app.services.system.cleanup_service import CleanupService


@pytest.fixture
async def retention_catalog(tmp_path):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'retention.db'}")
    root = tmp_path / "recordings"
    directory = root / "alice" / "Season 2026"
    directory.mkdir(parents=True)
    paths = []
    for identifier in range(1, 4):
        path = directory / f"episode-{identifier}.mp4"
        # Native sparse regular files exercise GiB policies without allocating
        # physical media-sized memory/disk; these are not decoder fixtures.
        with path.open("wb") as file:
            file.truncate(512 * 1024 * 1024)
        paths.append(path)
    service = CleanupService(
        session_factory=database.sync_session_factory,
        settings=Settings(
            ENVIRONMENT="test", RECORDING_DIRECTORY=str(root), _env_file=None
        ),
    )
    try:
        with database.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as db:
            db.add(Streamer(id=1, username="alice", twitch_id="alice"))
            db.flush()
            for identifier, path in enumerate(paths, 1):
                started = datetime.now(timezone.utc) - timedelta(days=11 - identifier)
                db.add(
                    Stream(
                        id=identifier,
                        streamer_id=1,
                        title=f"episode-{identifier}",
                        category_name="Preserved" if identifier == 1 else "Ordinary",
                        started_at=started,
                        ended_at=started + timedelta(hours=1),
                        recording_path=str(path),
                    )
                )
            db.add(RecordingSettings(id=1, max_streams_per_streamer=0))
            db.commit()
        yield service, database, paths
    finally:
        await database.adispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "policy_type,threshold,expected", [("count", 1, 2), ("size", 1, 1), ("age", 7, 3)]
)
@pytest.mark.parametrize("source", ["custom", "global", "channel"])
async def test_retention_policy_selects_and_deletes_only_expected_rows(
    retention_catalog, policy_type, threshold, expected, source
):
    service, database, paths = retention_catalog
    policy = {
        "type": policy_type,
        "threshold": threshold,
        "preserve_favorites": False,
        "preserve_categories": [],
    }
    if source != "custom":
        with database.sync_session_factory() as db:
            if source == "global":
                db.get(RecordingSettings, 1).cleanup_policy = json.dumps(policy)
            else:
                db.add(
                    StreamerRecordingSettings(
                        streamer_id=1,
                        use_global_cleanup_policy=False,
                        cleanup_policy=json.dumps(policy),
                    )
                )
            db.commit()
    count, deleted = await service.cleanup_old_recordings(
        1, policy if source == "custom" else None
    )
    assert count == expected and len(deleted) == expected
    assert sum(path.exists() for path in paths) == 3 - expected
    assert not any(Path(path).exists() for path in deleted)
    with database.sync_session_factory() as db:
        assert db.query(Stream).count() == 3 - expected
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "policy_type,threshold,expected", [("count", 1, 1), ("size", 1, 1), ("age", 7, 2)]
)
async def test_retention_simulation_is_pure_and_matches_category_preservation(
    retention_catalog, policy_type, threshold, expected
):
    service, database, paths = retention_catalog
    policy = {
        "type": policy_type,
        "threshold": threshold,
        "preserve_favorites": False,
        "preserve_categories": ["Preserved"],
    }
    count, preview = await service.simulate_cleanup(1, policy)
    assert count == expected and len(preview["streams"]) == expected
    assert 1 not in [item["id"] for item in preview["streams"]]
    assert all(path.stat().st_size == 512 * 1024 * 1024 for path in paths)
    with database.sync_session_factory() as db:
        assert db.query(Stream).count() == 3
    deleted, _ = await service.cleanup_old_recordings(1, policy)
    assert deleted == expected and paths[0].exists()
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "configuration",
    [
        "unlimited",
        "invalid-global",
        "invalid-channel",
        "max-streams-global",
        "max-streams-channel",
    ],
)
async def test_retention_legacy_fallbacks_keep_explicit_unlimited_meaning(
    retention_catalog, configuration
):
    service, database, paths = retention_catalog
    with database.sync_session_factory() as db:
        if configuration == "invalid-global":
            db.get(RecordingSettings, 1).cleanup_policy = "not json"
        if configuration == "max-streams-global":
            db.get(RecordingSettings, 1).max_streams_per_streamer = 1
        if configuration in {"invalid-channel", "max-streams-channel"}:
            db.add(
                StreamerRecordingSettings(
                    streamer_id=1,
                    use_global_cleanup_policy=False,
                    cleanup_policy="not json"
                    if configuration == "invalid-channel"
                    else None,
                    max_streams=1 if configuration == "max-streams-channel" else 0,
                )
            )
        db.commit()
    count, _ = await service.cleanup_old_recordings(1)
    expected = 2 if configuration.startswith("max-streams") else 0
    assert count == expected
    assert sum(path.exists() for path in paths) == 3 - expected
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_scheduled_retention_uses_same_policy_and_remains_idempotent(
    retention_catalog,
):
    service, database, paths = retention_catalog
    with database.sync_session_factory() as db:
        db.get(RecordingSettings, 1).cleanup_policy = json.dumps(
            {"type": "count", "threshold": 1, "preserve_favorites": False}
        )
        db.commit()
    await service.run_scheduled_cleanup()
    assert [path.exists() for path in paths] == [False, False, True]
    await service.run_scheduled_cleanup()
    assert paths[2].exists()
    assert database.sync_engine.pool.checkedout() == 0
