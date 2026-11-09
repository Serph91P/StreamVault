"""Both existing task-status routes must read deferred IDs off the loop."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.queues.durable_task_store import DurableTaskStore
from app.services.queues.task_queue_manager import TaskQueueManager


@pytest.mark.asyncio
async def test_deferred_task_status_uses_worker_owned_session_on_both_routes(tmp_path, monkeypatch):
    from app.api import background_queue_endpoints as api
    from app.routes import background_queue as legacy

    engine = create_engine(f"sqlite:///{tmp_path / 'status.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    queue = TaskQueueManager(task_store=DurableTaskStore(sessionmaker(engine)))
    task_id = await queue.enqueue_task("synthetic", {})
    monkeypatch.setattr(api, "get_background_queue_service", lambda: queue)
    monkeypatch.setattr(legacy, "background_queue_service", queue)
    reads_on_loop = []

    def inspect_read(connection, cursor, statement, parameters, context, many):
        if "background_tasks" in statement and statement.lstrip().startswith("SELECT"):
            try:
                asyncio.get_running_loop()
                reads_on_loop.append(True)
            except RuntimeError:
                reads_on_loop.append(False)

    event.listen(engine, "before_cursor_execute", inspect_read)
    app = FastAPI()
    app.include_router(api.router)
    app.include_router(legacy.router)
    try:
        with TestClient(app) as client:
            detail = client.get(f"/api/background-queue/task/{task_id}")
            assert detail.status_code == 200
            assert detail.json()["status"] == "pending"
            status = client.get(f"/background-queue/tasks/{task_id}")
            assert status.status_code == 200
            assert status.json()["task"] == "pending"
        assert reads_on_loop == [False, False]
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()
