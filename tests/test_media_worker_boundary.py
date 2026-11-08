"""Playback preparation must not run SQL/filesystem work on the event loop."""
import asyncio
from datetime import datetime, timezone
import threading
import time

from fastapi import FastAPI
import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app import dependencies
from app.models import Stream, Streamer
from app.routes import videos


@pytest.mark.asyncio
@pytest.mark.parametrize('public',[False,True])
async def test_media_preparation_owns_session_and_slow_query_in_one_worker(tmp_path,monkeypatch,public):
    from app.database import Base
    from app.config.settings import get_settings
    media=tmp_path/'local.ts'; media.write_bytes(b'local synthetic media')
    engine=create_engine(f'sqlite:///{tmp_path}/media.db')
    with engine.begin() as connection:
        connection.exec_driver_sql('BEGIN')
        Base.metadata.create_all(connection,tables=[Streamer.__table__,Stream.__table__])
    sessions=sessionmaker(engine)
    with sessions() as db:
        channel=Streamer(username='synthetic',twitch_id='synthetic'); db.add(channel); db.flush()
        stream=Stream(streamer_id=channel.id,title='Synthetic',started_at=datetime.now(timezone.utc),recording_path=str(media)); db.add(stream); db.commit(); identifier=stream.id
    owners=[]; queries=[]; closes=[]; query_busy=threading.Event()
    class OwnedSession(Session):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs); owners.append(threading.get_ident())
        def close(self):
            closes.append(threading.get_ident()); super().close()
    factory=sessionmaker(engine,class_=OwnedSession)
    def delayed_query(connection,cursor,statement,*args):
        if statement.lstrip().upper().startswith('SELECT'):
            queries.append(threading.get_ident()); query_busy.set()
            time.sleep(.2)  # controlled slow database; ticker must still run
            query_busy.clear()
    event.listen(engine,'before_cursor_execute',delayed_query)
    monkeypatch.setattr(videos,'SessionLocal',factory)
    monkeypatch.setattr(videos,'validate_share_token',lambda _:identifier)
    monkeypatch.setattr(get_settings(),'RECORDING_DIRECTORY',str(tmp_path))
    def fresh_db():
        with factory() as db: yield db
    application=FastAPI(); application.include_router(videos.router)
    application.dependency_overrides[dependencies.get_db]=fresh_db
    application.dependency_overrides[dependencies.get_current_identity]=lambda:dependencies.AuthIdentity(subject='synthetic',roles=frozenset(),scopes=frozenset(),auth_method='legacy-session',interactive=True)
    main=threading.get_ident(); ticks=[]; stop=False
    async def heartbeat():
        while not stop:
            await asyncio.sleep(.01)
            if query_busy.is_set(): ticks.append(True)
    ticker=asyncio.create_task(heartbeat())
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application),base_url='http://synthetic.local') as client:
            url=f'/api/videos/public/{identifier}?token=synthetic' if public else f'/api/videos/{identifier}/stream'
            response=await client.get(url)
            assert response.status_code==200 and response.content==media.read_bytes()
        assert queries and main not in queries
        assert len(ticks)>=5
        assert len(owners)==len(closes)==1
        assert owners==closes==queries
    finally:
        stop=True; await ticker; engine.dispose()
