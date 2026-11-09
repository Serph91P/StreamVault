"""50k terminal history can retire in bounded batches without breaking a live edge."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, insert, select

from app.models.background_task import BackgroundTask, BackgroundTaskDependency
from app.services.queues.durable_task_store import DurableTaskStore
from app.services.queues.task_progress_tracker import TaskStatus
from test_video_catalog_timestamps import catalog_sessions as _catalog_sessions

catalog_sessions = _catalog_sessions


def test_fifty_thousand_terminal_jobs_prune_without_losing_pending_dependency(catalog_sessions, tmp_path, monkeypatch):
    from app.config.settings import get_settings
    sessions, backend = catalog_sessions
    engine=sessions.kw['bind']
    monkeypatch.setattr(get_settings(),'RECORDING_DIRECTORY',str(tmp_path))
    now=datetime.now(timezone.utc)
    with engine.begin() as connection:
        if backend=='sqlite': connection.exec_driver_sql('BEGIN')
        BackgroundTask.__table__.create(connection)
        BackgroundTaskDependency.__table__.create(connection)
        for offset in range(0,50000,1000):
            connection.execute(insert(BackgroundTask),[{'id':f'history-{n:05}','task_type':'cheap','payload':{},'streamer_key':'synthetic','priority':2,'status':'completed','created_at':now-timedelta(days=2),'ready_at':now-timedelta(days=2),'completed_at':now-timedelta(seconds=50000-n),'retry_count':0,'max_retries':0} for n in range(offset,offset+1000)])
        connection.execute(insert(BackgroundTask),{'id':'waiting','task_type':'cheap','payload':{},'streamer_key':'synthetic','priority':2,'status':'pending','created_at':now,'ready_at':now,'retry_count':0,'max_retries':0})
        connection.execute(insert(BackgroundTaskDependency),{'task_id':'waiting','dependency_id':'history-00000'})
    store=DurableTaskStore(sessions)
    try:
        assert len(store.recent())==1000
        deleted=[]
        while count:=store.prune():
            assert 0<count<=100
            deleted.append(count)
        assert sum(deleted)==48999
        with sessions() as db:
            assert db.scalar(select(func.count()).select_from(BackgroundTask))==1002
            assert db.scalar(select(func.count()).select_from(BackgroundTaskDependency))==1
            assert db.get(BackgroundTask,'history-00000').status=='completed'
            assert db.get(BackgroundTask,'waiting').status=='pending'
        claimed=store.claim(1,set(),1,False)
        assert [task.id for task,_ in claimed]==['waiting']
        assert store.finish('waiting',success=True).status is TaskStatus.COMPLETED
        assert len(store.recent())==1000
    finally:
        store.close_owner(remove=True)
