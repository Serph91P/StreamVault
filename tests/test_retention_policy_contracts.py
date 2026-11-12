"""Retention policy semantics and preview purity use real owned files/catalogs."""

from datetime import datetime, timedelta, timezone
import json
import os
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


@pytest.mark.asyncio
@pytest.mark.parametrize("policy_type", ["count", "size", "age"])
@pytest.mark.parametrize(
    "timeframe,kept",
    [
        ({"start_date": "2020-01-07T00:00:00"}, {2, 3}),
        ({"end_date": "2020-01-07T23:59:00"}, {1, 2}),
        ({"start_date": "2020-01-07T00:00:00", "end_date": "2020-01-08T00:00:00"}, {2}),
        ({"weekdays": [1]}, {2}),
        ({"weekdays": [6]}, set()),
        ({"timeOfDay": {"start": "09:00", "end": "11:00"}}, {1}),
        ({"timeOfDay": {"start": "22:00", "end": "06:00"}}, {3}),
        ({"timeOfDay": {"start": "17:00", "end": "19:00"}}, set()),
        ({"timeOfDay": {"start": "invalid", "end": "99:99"}}, {1, 2, 3}),
    ],
)
async def test_existing_preview_timeframe_filters_are_pure(
    retention_catalog, policy_type, timeframe, kept
):
    # Existing SDK preview only, not the separate #993 execution/parity feature.
    service, database, paths = retention_catalog
    with database.sync_session_factory() as db:
        for identifier, hour in ((1, 10), (2, 14), (3, 23)):
            row = db.get(Stream, identifier)
            row.started_at = datetime(2020, 1, 5 + identifier, hour)
            row.ended_at = row.started_at + timedelta(minutes=15)
        db.commit()
    candidates = sorted({1, 2, 3} - kept)
    expected = {
        "count": candidates[:-1],
        "size": candidates[:1],
        "age": candidates,
    }[policy_type]
    count, result = await service.simulate_cleanup(
        1,
        {
            "type": policy_type,
            "threshold": 7 if policy_type == "age" else 1,
            "preserve_favorites": False,
            "preserve_timeframe": timeframe,
        },
    )
    assert count == len(expected)
    assert sorted(row["id"] for row in result["streams"]) == expected
    assert all(path.stat().st_size == 512 * 1024 * 1024 for path in paths)
    with database.sync_session_factory() as db:
        assert db.query(Stream).count() == 3
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("denied", [None, "file", "directory"])
async def test_owned_orphan_cleanup_preserves_external_links_and_counts_only_removed_items(
    retention_catalog, tmp_path, monkeypatch, denied
):
    service, database, paths = retention_catalog
    root = Path(service._settings.RECORDING_DIRECTORY)
    empty = root / "empty.nfo"
    empty.touch()
    for name in ("tvshow.nfo", "season.nfo", "zero.mp4"):
        (root / name).touch()
    broken = root / "broken-link"
    broken.symlink_to(root / "absent-target")
    external = tmp_path / "peer.nfo"
    external.touch()
    external_link = root / "external.nfo"
    external_link.symlink_to(external)
    segment = root / "empty_segments"
    segment.mkdir()
    nonempty = root / "kept_segments"
    nonempty.mkdir()
    (nonempty / "part.ts").write_bytes(b"owned incomplete media")
    native_remove, native_rmdir = os.remove, os.rmdir

    def remove(path, *args, **kwargs):
        if denied == "file" and Path(path) == empty:
            raise PermissionError("synthetic-orphan-file-denied")
        return native_remove(path, *args, **kwargs)

    def rmdir(path, *args, **kwargs):
        if denied == "directory" and Path(path) == segment:
            raise PermissionError("synthetic-orphan-directory-denied")
        return native_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "remove", remove)
    monkeypatch.setattr(os, "rmdir", rmdir)
    count, removed = await service.cleanup_orphaned_files()
    assert count == (3 if denied is None else 2)
    assert set(removed) == (
        {str(broken)} if denied == "file" else {str(broken), str(empty)}
    )
    assert empty.exists() is (denied == "file")
    assert segment.exists() is (denied == "directory")
    assert not broken.is_symlink()
    assert external_link.is_symlink() and external.stat().st_size == 0
    assert all(
        (root / name).exists() for name in ("tvshow.nfo", "season.nfo", "zero.mp4")
    )
    assert (nonempty / "part.ts").read_bytes() == b"owned incomplete media"
    assert all(path.exists() for path in paths)
    with database.sync_session_factory() as db:
        assert db.query(Stream).count() == 3
