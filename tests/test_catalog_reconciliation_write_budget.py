"""Warm reconciliation must stamp a bounded batch, not issue one UPDATE per row."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import event, select

from app.models import Stream, Streamer
from app.models.video_catalog import VideoCatalogEntry
from app.services.media import video_catalog_service
from test_video_catalog_timestamps import catalog_sessions as _catalog_sessions

catalog_sessions = _catalog_sessions


def test_unchanged_completed_metadata_uses_one_batch_freshness_write(catalog_sessions,tmp_path,monkeypatch):
    sessions,_=catalog_sessions; engine=sessions.kw['bind']
    VideoCatalogEntry.__table__.create(engine)
    media=tmp_path/'synthetic.ts'; media.write_bytes(b'catalog-only media')
    now=datetime(2026,11,1,tzinfo=timezone.utc)
    clock=[now]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return clock[0] if tz else clock[0].replace(tzinfo=None)
    monkeypatch.setattr(video_catalog_service,'datetime',Clock)
    with sessions() as db:
        channel=Streamer(username='synthetic',twitch_id='synthetic'); db.add(channel); db.flush()
        db.add_all([Stream(streamer_id=channel.id,title=str(n),recording_path=str(media),started_at=now-timedelta(minutes=10),ended_at=now) for n in range(100)])
        db.commit()
        assert video_catalog_service.VideoCatalogService(db).reconcile_batch()[1]==100
    clock[0]=now+timedelta(minutes=1)
    statements=[]
    def count(connection,cursor,statement,*args): statements.append(statement)
    event.listen(engine,'before_cursor_execute',count)
    try:
        with sessions() as db:
            assert video_catalog_service.VideoCatalogService(db).reconcile_batch()[1]==100
        writes=[sql for sql in statements if sql.lstrip().upper().startswith('UPDATE VIDEO_CATALOG_ENTRIES')]
        assert len(writes)<=2, f'Unchanged batch issued {len(writes)} per-row writes'
        assert len(statements)<=8
    finally:
        event.remove(engine,'before_cursor_execute',count)
    with sessions() as db:
        rows=list(db.scalars(select(VideoCatalogEntry)))
        assert len(rows)==100 and all(row.state=='available' and not row.dirty for row in rows)
        assert all((row.checked_at.astimezone(timezone.utc) if row.checked_at.tzinfo else row.checked_at.replace(tzinfo=timezone.utc))==clock[0] for row in rows)
