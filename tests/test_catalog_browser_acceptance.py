"""Opt-in real Chromium -> production Vue -> live app/PG/FS acceptance.

Uses the existing disposable full-app runtime and real authentication. No browser
route interception, auth override, API fulfilment or synthetic UI responses.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import time

from sqlalchemy import select, text

from app.models import Stream, Streamer
from app.services.media.video_catalog_service import VideoCatalogService
from test_fullstack_postgres_acceptance import fullstack_runtime as _fullstack_runtime

fullstack_runtime = _fullstack_runtime


def test_library_paging_search_sort_filters_and_deep_player_in_real_browser(fullstack_runtime, tmp_path):
    runtime = fullstack_runtime
    sessions = runtime['Session']
    with sessions() as db:
        seed = db.get(Stream, runtime['stream_id'])
        media = Path(seed.recording_path).parent / 'browser.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=24','-t','6','-c:v','libx264','-preset','ultrafast','-threads','1','-pix_fmt','yuv420p',str(media)], check=True, capture_output=True)
    paths={}
    try:
        now=datetime.now(timezone.utc)
        with sessions() as db:
            channel=Streamer(username='browser-channel',twitch_id='browser-synthetic-only',is_test_data=True)
            db.add(channel); db.flush()
            for n in range(120):
                folder=media.parent/f'browser-{n:03}'
                folder.mkdir()
                video_path=folder/'video.mp4'
                os.link(media,video_path)
                stream=Stream(streamer_id=channel.id,title=f'Browser video {n:03}',recording_path=str(video_path),started_at=now-timedelta(seconds=n),ended_at=now+timedelta(seconds=6))
                db.add(stream)
            db.commit()
            last_id=db.scalar(select(Stream.id).where(Stream.title=='Browser video 119'))
            protected_id=db.scalar(select(Stream.id).where(Stream.title=='Browser video 108'))
            paths={row.id:Path(row.recording_path) for row in db.scalars(select(Stream).where(Stream.streamer_id==channel.id))}
            VideoCatalogService(db).reconcile_batch(after_id=0,limit=200)
            # A real DB failure, not an intercepted response. File permission
            # faults occur after this endpoint ACKs its durable cleanup job.
            db.execute(text("CREATE FUNCTION browser_delete_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF OLD.id = TG_ARGV[0]::integer THEN RAISE EXCEPTION 'synthetic browser deletion fault'; END IF; RETURN OLD; END $$"))
            db.execute(text(f"CREATE TRIGGER browser_delete_fault BEFORE DELETE ON streams FOR EACH ROW EXECUTE FUNCTION browser_delete_fault('{int(protected_id)}')"))
            db.commit()
        repo=Path(__file__).resolve().parents[1]
        output=Path(os.environ.get('STREAMVAULT_BROWSER_EVIDENCE',str(tmp_path/'evidence')))
        fixture=tmp_path/'browser-paths.json'
        fixture.write_text(json.dumps({'paths':{identifier:str(path) for identifier,path in paths.items()},'protectedId':protected_id}))
        env=dict(os.environ,STREAMVAULT_PLAYWRIGHT_MODULE=str(repo/'app/frontend/node_modules/@playwright/test'),PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH','/opt/hermes/tools/chromium-1208/chrome-linux64/chrome'))
        completed=subprocess.run(['node',str(repo/'tests/catalog_browser_flow.cjs'),str(runtime['client'].base_url),str(output),str(last_id),str(fixture)],env=env,capture_output=True,text=True,timeout=90)
        assert completed.returncode==0, completed.stdout+completed.stderr
        report=json.loads((output/'browser.json').read_text())
        assert report['status']=='passed' and len(report['checks'])==2
        assert report['mockedRoutes'] is False
        assert len(set(report['deletedIds']))==2
        with sessions() as db:
            assert all(db.get(Stream,identifier) is None for identifier in report['deletedIds'])
            assert len(report['failedIds'])==1
            assert all(db.get(Stream,identifier) is not None for identifier in report['failedIds'])
            assert all(paths[identifier].is_file() for identifier in report['failedIds'])
        deadline=time.monotonic()+10
        while any(paths[identifier].exists() for identifier in report['deletedIds']) and time.monotonic()<deadline:
            time.sleep(.05)
        assert all(not paths[identifier].exists() for identifier in report['deletedIds'])
    finally:
        with sessions() as db:
            db.execute(text('DROP TRIGGER IF EXISTS browser_delete_fault ON streams'))
            db.execute(text('DROP FUNCTION IF EXISTS browser_delete_fault()'))
            db.commit()
        media.unlink(missing_ok=True)
        for path in paths.values():
            if path.parent.exists(): path.parent.chmod(0o700)
            path.unlink(missing_ok=True)
            if path.parent.exists(): path.parent.rmdir()
