"""Opt-in full Uvicorn/lifespan/PG restart with real remux and live capture.

Requires an exclusively owned restartable PG17 container, checked before DDL or
restart. No production DB, provider calls, mocked handlers or create_all schema.
"""
import asyncio
import ctypes
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import threading

import httpx
import psutil
import pytest
from sqlalchemy import create_engine, select, insert
from sqlalchemy.orm import sessionmaker

from app.models import ActiveRecordingState, GlobalSettings, Recording, RecordingProcessingState, Stream, Streamer, TwitchUpstreamLease
from app.models.background_task import BackgroundTask
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator
from test_fullstack_postgres_acceptance import _require_disposable_postgres_url, _reset_disposable_database


def wait_for(check, timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        result=check()
        if result: return result
        time.sleep(.05)
    raise AssertionError('Owned full-app fixture did not reach expected state')


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def test_full_app_sigkill_pg_restart_preserves_real_processing_and_live_capture(tmp_path):
    url=os.environ.get('STREAMVAULT_RESTART_POSTGRES_URL')
    container=os.environ.get('STREAMVAULT_RESTART_TEST_CONTAINER')
    if not url or not container:
        pytest.skip('requires exclusively owned STREAMVAULT_RESTART_POSTGRES_URL/container')
    url=_require_disposable_postgres_url(url)
    assert container.startswith('streamvault-1045-restart-')
    metadata=json.loads(subprocess.check_output(['docker','inspect',container]))[0]
    assert metadata['HostConfig']['AutoRemove'] is True
    assert metadata['Config']['Labels'].get('streamvault.test.task')=='t_83f02567'
    assert sys.platform=='linux'
    _reset_disposable_database(url)
    repo=Path(__file__).resolve().parents[1]
    root=tmp_path/'recordings'; root.mkdir()
    for name in ('work','live'):
        (root/name).mkdir()
    source=root/'work'/'input.ts'; live=root/'live'/'live.ts'
    real_ffmpeg=shutil.which('ffmpeg'); assert real_ffmpeg
    subprocess.run([real_ffmpeg,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=24','-t','6','-c:v','mpeg2video','-b:v','8M','-minrate','8M','-maxrate','8M','-bufsize','16M','-threads','1','-f','mpegts',str(source)],check=True,capture_output=True)
    source_hash=digest(source)
    # A real-time input makes the actual remux crash window observable, not mocked.
    binary=tmp_path/'bin'; binary.mkdir()
    wrapper=binary/'ffmpeg'
    wrapper.write_text(f'#!/bin/sh\nexec "{real_ffmpeg}" -re "$@"\n'); wrapper.chmod(0o755)
    streamlink=binary/'streamlink'
    streamlink.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{repo / "tests/synthetic_streamlink_capture.py"}" "$@"\n'); streamlink.chmod(0o755)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env=dict(os.environ,DATABASE_URL=url,BASE_URL=base,TWITCH_APP_ID='synthetic-local',TWITCH_APP_SECRET='synthetic-local',AUTH_JWT_SECRET='synthetic-full-app-restart-key-at-least-32-characters',SECURE_COOKIES='false',USE_SECURE_COOKIES='false',RECORDING_DIRECTORY=str(root),ARTWORK_BASE_PATH=str(root/'.artwork'),READINESS_REQUIRED_COMPONENTS='database',STREAMVAULT_FULLAPP_QUEUE_PROBE='1',STREAMVAULT_FIXTURE_TOKEN='local-synthetic-only',PATH=str(binary)+os.pathsep+os.environ['PATH'])
    for key in ('LOG_DIR','LOGS_BASE_DIR','APP_LOG_DIR','STREAMLINK_LOG_DIR','FFMPEG_LOG_DIR'):
        env[key]=str(tmp_path/'logs'); Path(env[key]).mkdir(exist_ok=True)
    env.update(STREAMVAULT_SYNTHETIC_MEDIA=str(source),STREAMVAULT_SYNTHETIC_FFMPEG=real_ffmpeg,STREAMVAULT_SYNTHETIC_CAPTURE_SECONDS='12')
    servers=[]; log_handles=[]
    def start_app(*,promotion_crash=False):
        handle=(tmp_path/f'app-{len(servers)}.log').open('wb'); log_handles.append(handle)
        process_env=dict(env)
        if promotion_crash: process_env['STREAMVAULT_PROMOTION_CRASH_MARKER']=str(tmp_path/'promoted.marker')
        server=subprocess.Popen([sys.executable,'-m','uvicorn','--app-dir','tests','fullapp_queue_runtime:app','--host','127.0.0.1','--port',str(port)],cwd=repo,env=process_env,stdout=handle,stderr=subprocess.STDOUT)
        servers.append(server)
        def ready():
            assert server.poll() is None, f'App exit {server.returncode}; inspect {handle.name}'
            try: return httpx.get(base+'/api/health/ready',timeout=1).status_code==200
            except httpx.TransportError: return False
        wait_for(ready)
        return server
    engine=create_engine(url,pool_pre_ping=True); sessions=sessionmaker(engine)
    client=httpx.Client(base_url=base,timeout=10)
    capture=None; child_ids=[]
    libc=ctypes.CDLL(None,use_errno=True); old=ctypes.c_int()
    assert libc.prctl(37,ctypes.byref(old),0,0,0)==0
    assert libc.prctl(36,1,0,0,0)==0
    try:
        app=start_app()
        assert client.post('/auth/setup',json={'username':'restart-admin','password':'synthetic-password'}).status_code==200
        capture=subprocess.Popen([real_ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-y','-re','-stream_loop','-1','-i',str(source),'-t','45','-c','copy','-f','mpegts',str(live)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,start_new_session=True)
        wait_for(lambda: live.exists() and live.stat().st_size>0)
        identity=asyncio.run(TwitchUpstreamCoordinator(sessions,monotonic_clock=time.monotonic).inspect_process_identity(capture.pid))
        now=datetime.now(timezone.utc)
        with sessions() as db:
            settings=db.get(GlobalSettings,1); settings.notifications_enabled=False
            work=Streamer(username='work',twitch_id='restart-work',is_test_data=True)
            live_channel=Streamer(username='live',twitch_id='restart-live',is_test_data=True)
            db.add_all([work,live_channel]); db.flush()
            work_stream=Stream(streamer_id=work.id,title='Restart media',started_at=now-timedelta(seconds=6),ended_at=now,recording_path=str(source))
            live_stream=Stream(streamer_id=live_channel.id,title='Live capture',started_at=now,recording_path=str(live))
            db.add_all([work_stream,live_stream]); db.flush()
            recording=Recording(stream_id=work_stream.id,status='post_processing',path=str(source),start_time=now-timedelta(seconds=6),end_time=now)
            active=Recording(stream_id=live_stream.id,status='recording',path=str(live),start_time=now)
            db.add_all([recording,active]); db.flush()
            db.add(ActiveRecordingState(stream_id=live_stream.id,recording_id=active.id,process_id=capture.pid,process_identifier='synthetic-external-capture',streamer_name='live',started_at=now,ts_output_path=str(live),status='active',last_heartbeat=now))
            db.add(TwitchUpstreamLease(channel_key='restart-live',recording_id=active.id,purpose='RECORDING',state='ACTIVE',generation=1,process_pid=capture.pid,process_group_id=identity.process_group_id,process_started_at=identity.started_at,process_start_fingerprint=identity.fingerprint,reserved_at=now,heartbeat_at=now,expires_at=now+timedelta(minutes=5),created_at=now,updated_at=now))
            db.commit(); stream_id,rec_id,active_id=work_stream.id,recording.id,active.id
        payload={'stream_id':stream_id,'recording_id':rec_id,'ts_file_path':str(source),'output_dir':str(source.parent),'streamer_name':'work','started_at':now.isoformat(),'cleanup_ts_file':False}
        accepted=client.post('/__local_fixture/chain',json=payload,headers={'x-fixture-token':'local-synthetic-only'})
        assert accepted.status_code==200, accepted.text
        ids=accepted.json()['ids']; assert len(ids)==5
        def remux_started():
            with sessions() as db:
                row=db.scalar(select(BackgroundTask).where(BackgroundTask.id.in_(ids),BackgroundTask.task_type=='mp4_remux'))
                return row is not None and row.status=='running'
        wait_for(remux_started)
        child_ids=[child.pid for child in psutil.Process(app.pid).children(recursive=True) if child.name()=='ffmpeg']
        wait_for(lambda:any(child.name()=='ffmpeg' for child in psutil.Process(app.pid).children(recursive=True)))
        child_ids=[child.pid for child in psutil.Process(app.pid).children(recursive=True) if child.name()=='ffmpeg']
        stage_root=source.parent/f'.{source.with_suffix(".mp4").name}.processing'
        stages=wait_for(lambda:[p for p in stage_root.glob('*/*.mp4') if p.stat().st_size>0])
        crash_scratch=list(stage_root.glob('*/*'))
        before_live=live.stat().st_size
        app.kill(); assert app.wait(timeout=5)==-9
        for pid in child_ids:
            wait_for(lambda: not psutil.pid_exists(pid) or psutil.Process(pid).status()==psutil.STATUS_ZOMBIE,timeout=5)
            try: os.waitpid(pid,0)
            except ChildProcessError: pass
            assert not psutil.pid_exists(pid)
        assert capture.poll() is None and digest(source)==source_hash
        restarted=start_app(promotion_crash=True); assert restarted.pid!=app.pid
        wait_for(remux_started)
        subprocess.run(['docker','exec','--user','postgres',container,'pg_ctl','-D','/var/lib/postgresql/data','-m','fast','-w','restart'],check=True,capture_output=True,timeout=20)
        engine.dispose()
        assert restarted.wait(timeout=30)==-9
        assert (tmp_path/'promoted.marker').read_text()=='promoted-before-step-commit'
        assert all(not path.exists() for path in crash_scratch)
        assert source.with_suffix('.mp4').is_file() and digest(source)==source_hash
        with sessions() as db:
            state=db.scalar(select(RecordingProcessingState).where(RecordingProcessingState.recording_id==rec_id))
            assert state.mp4_remux_status!='completed'
            assert set(state.get_task_ids().values())==set(ids)
        recovered=start_app(); assert recovered.pid not in (app.pid,restarted.pid)
        def completed():
            try:
                with sessions() as db:
                    rows=list(db.scalars(select(BackgroundTask).where(BackgroundTask.id.in_(ids))))
                    assert len(rows)==5
                    assert all(row.status!='failed' for row in rows), [(row.id,row.error_message) for row in rows]
                    return all(row.status=='completed' for row in rows)
            except (httpx.TransportError,): return False
        wait_for(completed,timeout=60)
        with sessions() as db:
            state=db.scalar(select(RecordingProcessingState).where(RecordingProcessingState.recording_id==rec_id))
            assert {state.metadata_status,state.chapters_status,state.mp4_remux_status,state.mp4_validation_status,state.thumbnail_status}=={'completed'}
            assert set(state.get_task_ids().values())==set(ids)
            assert db.get(Recording,active_id).status=='recording'
        assert capture.poll() is None and live.stat().st_size>before_live
        output=source.with_suffix('.mp4'); output_hash=digest(output)
        duplicate=client.post('/__local_fixture/chain',json=payload,headers={'x-fixture-token':'local-synthetic-only'})
        assert duplicate.status_code==200 and duplicate.json()['ids']==[]
        assert digest(output)==output_hash and digest(source)==source_hash
        assert capture.wait(timeout=50)==0
        for media in (output,live):
            info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(media)],text=True))
            assert float(info['format']['duration'])>=(44 if media==live else 5.9)
            subprocess.run([real_ffmpeg,'-hide_banner','-loglevel','error','-xerror','-i',str(media),'-f','null','-'],check=True,capture_output=True)
        # One complete controlled RecordingManager capture -> same bytes through
        # real concat/remux/validation/thumbnail/cleanup, alongside a 50k catalog.
        with sessions() as db:
            library=Streamer(username='library-fixture',twitch_id='library-fixture',is_test_data=True)
            controlled=Streamer(username='controlled-capture',twitch_id='controlled-fixture',is_test_data=True)
            db.add_all([library,controlled]); db.flush()
            for offset in range(0,50000,1000):
                db.execute(insert(Stream),[{'streamer_id':library.id,'title':f'Catalog fixture {n:05}','started_at':now-timedelta(seconds=n),'ended_at':now,'recording_path':str(source)} for n in range(offset,offset+1000)])
            control_stream=Stream(streamer_id=controlled.id,title='Controlled capture',started_at=datetime.now(timezone.utc))
            db.add(control_stream); db.commit()
            control_id,channel_id=control_stream.id,controlled.id
        from app.services.media.video_catalog_service import VideoCatalogService
        cursor=0
        while True:
            with sessions() as db: cursor,count=VideoCatalogService(db).reconcile_batch(after_id=cursor)
            if not count: break
        started=client.post('/__local_fixture/capture',json={'stream_id':control_id,'streamer_id':channel_id},headers={'x-fixture-token':'local-synthetic-only'},timeout=30)
        assert started.status_code==200, started.text
        control_recording_id=started.json()['recording_id']
        with sessions() as db:
            persistent=db.scalar(select(TwitchUpstreamLease).where(TwitchUpstreamLease.recording_id==control_recording_id))
            assert persistent is not None and persistent.state=='ACTIVE'
            control_pid=persistent.process_pid
            assert psutil.pid_exists(control_pid)
            assert persistent.process_start_fingerprint and persistent.process_group_id==control_pid
            assert persistent.channel_key=='controlled-fixture'
            original_ts=Path(db.get(Recording,control_recording_id).path)
        load_stop=threading.Event()
        load_results=[]
        def library_load(index):
            while not load_stop.is_set():
                began=time.perf_counter()
                response=client.get('/api/videos/catalog',params={'page_size':50,'sort':('date','title','size','duration')[index%4]})
                assert response.status_code in (200,409),response.text
                if response.status_code==200:
                    page=response.json(); assert len(page['items'])<=50 and page['total']>=50000
                load_results.append({'status':response.status_code,'elapsed_s':time.perf_counter()-began})
                time.sleep(.1)
        def capture_chain_completed():
            with sessions() as db:
                state=db.scalar(select(RecordingProcessingState).where(RecordingProcessingState.recording_id==control_recording_id))
                return state is not None and state.cleanup_status=='completed'
        with ThreadPoolExecutor(max_workers=8) as executor:
            workers=[executor.submit(library_load,n) for n in range(8)]
            try: wait_for(capture_chain_completed,timeout=90)
            finally: load_stop.set()
            for worker in workers: worker.result()
        assert len(load_results)>=80
        with sessions() as db:
            state=db.scalar(select(RecordingProcessingState).where(RecordingProcessingState.recording_id==control_recording_id))
            control_ids=list(state.get_task_ids().values()); assert len(control_ids)==6
            assert all(db.get(BackgroundTask,identifier).status=='completed' for identifier in control_ids)
            final=Path(db.get(Stream,control_id).recording_path)
            assert final.suffix=='.mp4' and final.is_file()
            assert db.scalar(select(ActiveRecordingState).where(ActiveRecordingState.recording_id==control_recording_id)) is None
            lease=db.scalar(select(TwitchUpstreamLease).where(TwitchUpstreamLease.channel_key=='controlled-fixture'))
            assert lease is not None and lease.state=='RELEASED'
            assert not psutil.pid_exists(control_pid)
        assert not original_ts.exists(), 'Cleanup did not retire the actual capture input'
        controlled_root=root/'controlled-capture'
        assert not list(controlled_root.rglob('*.ts')), 'Owned concat/capture TS survived completed cleanup'
        assert not list(controlled_root.rglob('*_copy1*')), 'Unexpected self-collision rename'
        with sessions() as db:
            admitted_rows=list(db.scalars(select(BackgroundTask).where(BackgroundTask.payload['recording_id'].as_integer()==control_recording_id)))
            assert {row.id for row in admitted_rows}==set(control_ids)
            assert len(admitted_rows)==6, 'More than one chain was admitted for the same capture'
        def fresh_catalog():
            response=client.get('/api/videos/catalog',params={'sort':'date','order':'desc','page_size':50})
            assert response.status_code in (200,409)
            if response.status_code!=200: return False
            page=response.json(); assert page['total']>=50000 and len(page['items'])==50
            return next((item for item in page['items'] if item['id']==control_id and item['file_path']==str(final)),False)
        assert wait_for(fresh_catalog)['file_path']==str(final)
        controlled_probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(final)],text=True))
        assert float(controlled_probe['format']['duration'])>=11.8
        subprocess.run([real_ffmpeg,'-hide_banner','-loglevel','error','-xerror','-i',str(final),'-f','null','-'],check=True,capture_output=True)
        report={'scope':'real full app/lifespan/migration, five production handlers, SIGKILL+fresh app and actual PG server restart during real remux; external real FFmpeg capture retained; synthetic provider seam, not machine power loss/exactly-once','app_pids':[server.pid for server in servers],'ids':ids,'all_completed':True,'source_preserved':True,'mp4_sha256':output_hash,'capture_duration_s':float(info['format']['duration'])}
        (tmp_path/'restart-report.json').write_text(json.dumps(report,indent=2))
        (tmp_path/'controlled-capture-report.json').write_text(json.dumps({'scope':'real RecordingManager and authoritative TwitchUpstreamLease PID/group/start identity, synthetic local Streamlink launch only, actual captured output through six production steps and cleanup under 50k SQL catalog/c8 HTTP load','recording_id':control_recording_id,'ids':control_ids,'output_sha256':digest(final),'duration_s':float(controlled_probe['format']['duration']),'http':load_results},indent=2))
    finally:
        for server in servers:
            if server.poll() is None:
                server.terminate()
                try: server.wait(timeout=20)
                except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=5)
        if capture is not None and capture.poll() is None: capture.kill(); capture.wait(timeout=5)
        for handle in log_handles: handle.close()
        client.close(); engine.dispose()
        assert libc.prctl(36,old.value,0,0,0)==0
