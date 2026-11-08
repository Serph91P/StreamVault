"""A committed retry or new dependent must survive concurrent history pruning."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timedelta, timezone
import threading

import pytest
from sqlalchemy import event, insert, select

from app.database import Base
from app.models import Recording, RecordingProcessingState, Stream, Streamer
from app.models.background_task import BackgroundTask, BackgroundTaskDependency
from app.services.queues.durable_task_store import DurableTaskStore
from app.services.queues.task_progress_tracker import QueueTask, TaskPriority, TaskStatus
from test_video_catalog_timestamps import catalog_sessions as _catalog_sessions

catalog_sessions=_catalog_sessions


@pytest.mark.parametrize('operation',['retry','dependency'])
def test_prune_serializes_with_acknowledged_admission(catalog_sessions,tmp_path,monkeypatch,operation):
    from app.config.settings import get_settings
    sessions,backend=catalog_sessions; engine=sessions.kw['bind']
    monkeypatch.setattr(get_settings(),'RECORDING_DIRECTORY',str(tmp_path))
    now=datetime.now(timezone.utc)
    with engine.begin() as connection:
        if backend=='sqlite': connection.exec_driver_sql('BEGIN')
        Base.metadata.create_all(connection)
    with sessions() as db:
        channel=Streamer(username='retention-race',twitch_id='retention-race'); db.add(channel); db.flush()
        stream=Stream(streamer_id=channel.id,started_at=now); db.add(stream); db.flush()
        recording=Recording(stream_id=stream.id,start_time=now,status='completed'); db.add(recording); db.flush()
        record_id=recording.id
        db.add(RecordingProcessingState(recording_id=record_id,stream_id=stream.id,streamer_id=channel.id,metadata_status='failed'))
        rows=[dict(id=f'newer-{n}',task_type='metadata',payload={},streamer_key='fixture',priority=2,status='completed',created_at=now,ready_at=now,completed_at=now,retry_count=0,max_retries=1) for n in range(1000)]
        rows.append(dict(rows[0],id='victim',status='failed',completed_at=now-timedelta(days=1)))
        db.execute(insert(BackgroundTask),rows); db.commit()
    store=DurableTaskStore(sessions)
    worker_thread=threading.get_ident(); futures=[]
    def admit():
        if operation=='retry':
            store.accept([(QueueTask(id='victim',task_type='metadata',payload={},priority=TaskPriority.NORMAL,status=TaskStatus.PENDING,created_at=now),[],'fixture')],recording_id=record_id)
        else:
            try:
                store.accept([(QueueTask(id='dependent',task_type='thumbnail',payload={},priority=TaskPriority.NORMAL,status=TaskStatus.PENDING,created_at=now),['victim'],'fixture')])
            except ValueError as error:
                assert str(error)=='Unknown task dependency'
                return False
        return True
    with ThreadPoolExecutor(max_workers=1) as executor:
        def selected(_connection,_cursor,statement,*_):
            if threading.get_ident()!=worker_thread or futures or not statement.lstrip().upper().startswith('SELECT') or 'OFFSET' not in statement.upper(): return
            future=executor.submit(admit); futures.append(future)
            try: future.result(timeout=1)
            except FutureTimeout: pass  # Correct serialization may hold admission until prune commits.
        event.listen(engine,'after_cursor_execute',selected)
        try:
            deleted=store.prune(); assert 0<=deleted<=100
        finally: event.remove(engine,'after_cursor_execute',selected)
        assert len(futures)==1
        acknowledged=futures[0].result(timeout=5)
    with sessions() as db:
        if operation=='retry':
            assert acknowledged
            row=db.get(BackgroundTask,'victim')
            assert row is not None and row.status=='pending', 'Pruning lost an acknowledged retry'
            state=db.scalar(select(RecordingProcessingState).where(RecordingProcessingState.recording_id==record_id))
            assert state.get_task_ids()['metadata']=='victim'
        elif acknowledged:
            assert db.get(BackgroundTask,'victim') is not None, 'Pruning lost an acknowledged dependency'
            assert db.get(BackgroundTask,'dependent').status=='pending'
            assert db.scalar(select(BackgroundTaskDependency).where(BackgroundTaskDependency.task_id=='dependent',BackgroundTaskDependency.dependency_id=='victim')) is not None
        else:
            assert db.get(BackgroundTask,'dependent') is None
            assert db.scalar(select(BackgroundTaskDependency).where(BackgroundTaskDependency.task_id=='dependent')) is None
