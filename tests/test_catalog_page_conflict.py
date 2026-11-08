"""Concurrent source cleanup/index refresh is a bounded 409, never a 500/stale write."""
from datetime import datetime,timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import dependencies
from app.database import Base
from app.models import Stream,Streamer
from app.models.video_catalog import VideoCatalogEntry
from app.routes import videos
from app.services.media.video_catalog_service import VideoCatalogService
from test_video_catalog_timestamps import catalog_sessions as _catalog_sessions

catalog_sessions=_catalog_sessions


def test_revalidation_conflict_preserves_newer_index_and_returns_retry(catalog_sessions,tmp_path,monkeypatch):
    sessions,backend=catalog_sessions; engine=sessions.kw['bind']
    with engine.begin() as connection:
        if backend=='sqlite': connection.exec_driver_sql('BEGIN')
        Base.metadata.create_all(connection)
    old=tmp_path/'old.mp4'; old.write_bytes(b'old media')
    fresh=tmp_path/'fresh.mp4'; fresh.write_bytes(b'new complete media')
    now=datetime.now(timezone.utc)
    with sessions() as db:
        channel=Streamer(username='page-race',twitch_id='page-race'); db.add(channel); db.flush()
        stream=Stream(streamer_id=channel.id,title='Race',started_at=now,ended_at=now,recording_path=str(old)); db.add(stream); db.commit()
        identifier=stream.id
        VideoCatalogService(db).reconcile_batch()
    app=FastAPI(); app.include_router(videos.router)
    monkeypatch.setattr(videos,'SessionLocal',sessions)
    app.dependency_overrides[dependencies.get_current_identity]=lambda:dependencies.AuthIdentity(subject='local-fixture',roles=frozenset(),scopes=frozenset(),auth_method='legacy-session',interactive=True)
    stat=Path.stat; changed=[]
    def concurrent_cleanup(path,*args,**kwargs):
        if path==old and not changed:
            changed.append(True); old.unlink()
            with sessions() as db:
                db.get(Stream,identifier).recording_path=str(fresh)
                entry=db.get(VideoCatalogEntry,identifier)
                entry.file_path=str(fresh); entry.file_size=fresh.stat().st_size; entry.revision+=1
                db.commit()
        return stat(path,*args,**kwargs)
    monkeypatch.setattr(Path,'stat',concurrent_cleanup)
    with TestClient(app,raise_server_exceptions=False) as client:
        first=client.get('/api/videos/catalog')
        assert first.status_code==409,first.text
        second=client.get('/api/videos/catalog')
        assert second.status_code==200 and second.json()['total']==1
        assert second.json()['items'][0]['id']==identifier
    assert changed==[True]
    with sessions() as db:
        entry=db.get(VideoCatalogEntry,identifier)
        assert entry.state=='available' and entry.file_path==str(fresh)
        assert entry.file_size==len(b'new complete media')
    assert fresh.read_bytes()==b'new complete media'
