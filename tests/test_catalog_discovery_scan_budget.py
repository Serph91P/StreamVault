"""Indexed priority work must not rescan the full library before every batch.

Value: protects=bounded warm discovery and prompt dirty/new-row refresh;
fails_when=priority selection scans all streams, loses behind-cursor work, or
rewrites unchanged metadata; seam=none; no_claim=provider/NAS/long-soak acceptance.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, event, insert, select, update

from app.models import Stream, Streamer, VideoCatalogEntry
from app.services.media.video_catalog_service import VideoCatalogService
from test_video_catalog_timestamps import catalog_sessions as _catalog_sessions

catalog_sessions = _catalog_sessions


def seed(sessions, tmp_path, count=2000):
    engine = sessions.kw['bind']
    VideoCatalogEntry.__table__.create(engine)
    media = tmp_path / 'snapshot.ts'
    media.write_bytes(b'owned synthetic catalog media')
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    with sessions() as db:
        channel = Streamer(username='scan-budget', twitch_id='scan-budget')
        db.add(channel)
        db.flush()
        db.execute(insert(Stream), [dict(id=n, streamer_id=channel.id,
            title=str(n), recording_path=str(media), started_at=now-timedelta(minutes=1),
            ended_at=now) for n in range(1, count+1)])
        db.execute(insert(VideoCatalogEntry), [dict(stream_id=n, state='available',
            file_path=str(media), file_size=media.stat().st_size,
            duration=60, started_at=now-timedelta(minutes=1), ended_at=now,
            checked_at=now) for n in range(1, count+1)])
        db.commit()
    return media


def test_warm_priority_query_uses_index_not_full_catalog_scan(catalog_sessions, tmp_path):
    sessions, dialect = catalog_sessions
    engine = sessions.kw['bind']
    seed(sessions, tmp_path)
    queries = []
    def observe(_connection, _cursor, sql, parameters, *_):
        if sql.lstrip().upper().startswith('SELECT'):
            queries.append((sql, parameters))
    event.listen(engine, 'before_cursor_execute', observe)
    try:
        with sessions() as db:
            assert VideoCatalogService(db).reconcile_next_batch(200) == (400, 200)
    finally:
        event.remove(engine, 'before_cursor_execute', observe)
    sql, parameters = queries[0]
    with engine.connect() as connection:
        if engine.dialect.name == 'sqlite':
            plan = str(connection.exec_driver_sql('EXPLAIN QUERY PLAN '+sql, parameters).all())
            assert 'SCAN streams' not in plan, plan
            assert 'SEARCH video_catalog_entries' in plan or 'USING INDEX ix_video_catalog_entries_reconcile' in plan, plan
        else:
            connection.exec_driver_sql('ANALYZE video_catalog_entries')
            connection.exec_driver_sql('ANALYZE streams')
            plan = str(connection.exec_driver_sql('EXPLAIN '+sql, parameters).all())
            assert 'Seq Scan on streams' not in plan, plan
            assert 'Seq Scan on video_catalog_entries' not in plan, plan
            assert 'Index' in plan, plan


def test_source_change_admits_missing_snapshot_behind_cursor(catalog_sessions, tmp_path):
    sessions, _ = catalog_sessions
    media = seed(sessions, tmp_path, count=401)
    with sessions() as db:
        # A previously uncatalogued stream becomes a media candidate after the
        # sequential discovery cursor has passed it.
        db.query(VideoCatalogEntry).filter_by(stream_id=1).delete()
        stream = db.get(Stream, 1)
        stream.recording_path = None
        db.commit()
        with VideoCatalogService.track_changes():
            stream.recording_path = str(media)
            db.commit()
        entry = db.get(VideoCatalogEntry, 1)
        assert entry is not None and entry.state == 'pending', 'new candidate was not admitted transactionally'
    with sessions() as db:
        assert VideoCatalogService(db).reconcile_next_batch(400) == (400, 1)
        entry = db.get(VideoCatalogEntry, 1)
        assert entry.state == 'available' and entry.file_path == str(media)
        # A source change remains a priority even with an existing snapshot.
        with VideoCatalogService.track_changes():
            db.get(Stream, 2).title = 'changed after cursor'
            db.commit()
        assert VideoCatalogService(db).reconcile_next_batch(400) == (400, 1)
        assert not db.get(VideoCatalogEntry, 2).dirty


def test_deleted_streams_cannot_starve_indexed_priority_work(catalog_sessions, tmp_path):
    sessions, _ = catalog_sessions
    seed(sessions, tmp_path, count=201)
    with sessions() as db:
        db.execute(update(VideoCatalogEntry).values(dirty=True))
        db.execute(delete(Stream).where(Stream.id <= 200))
        db.commit()
    with sessions() as db:
        # Legacy SQLite databases may not have enforced ON DELETE CASCADE.
        assert VideoCatalogService(db).reconcile_next_batch(200) == (200, 1)
        assert not db.get(VideoCatalogEntry, 201).dirty


def test_unchanged_batch_only_stamps_freshness_not_metadata(catalog_sessions, tmp_path):
    sessions, _ = catalog_sessions
    engine = sessions.kw['bind']
    seed(sessions, tmp_path, count=200)
    writes = []
    def observe(_connection, _cursor, sql, *_):
        if sql.lstrip().upper().startswith('UPDATE VIDEO_CATALOG_ENTRIES'):
            writes.append(sql)
    event.listen(engine, 'before_cursor_execute', observe)
    try:
        with sessions() as db:
            assert VideoCatalogService(db).reconcile_next_batch() == (200, 200)
    finally:
        event.remove(engine, 'before_cursor_execute', observe)
    assert len(writes) == 1, writes
    assigned = writes[0].upper().split(' SET ', 1)[1].split(' WHERE ', 1)[0]
    assert assigned.startswith('CHECKED_AT=') and ',' not in assigned, writes
    with sessions() as db:
        assert set(db.scalars(select(VideoCatalogEntry.revision))) == {0}
        assert all(row.checked_at is not None and not row.dirty
                   for row in db.scalars(select(VideoCatalogEntry)))
