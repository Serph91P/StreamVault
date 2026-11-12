"""Mounted token maintenance mutates only its request-owned real catalog."""

from datetime import datetime, timedelta, timezone
from threading import get_ident

import pytest
from sqlalchemy import event

from app.utils.async_db_utils import run_in_thread_pool
from app.utils.token_store import ShareTokenModel
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["cleanup", "delete", "delete-missing", "stats"])
async def test_admin_share_token_maintenance_preserves_actual_peer_rows(
    image_applications, monkeypatch, operation
):
    import app.utils.token_store as store

    _apps, databases, clients, _ = image_applications
    now = datetime.now(timezone.utc)

    def seed():
        for index, database in enumerate(databases):
            with database.sync_session_factory() as db:
                for identity in range(1, 3 + index):
                    db.add(
                        ShareTokenModel(
                            id=identity,
                            token=f"fixture-owner-{index}-row-{identity}",
                            stream_id=70 + identity,
                            expires_at=now + timedelta(hours=1)
                            if identity == 1
                            else now - timedelta(hours=1),
                        )
                    )
                db.commit()

    await run_in_thread_pool(seed)
    monkeypatch.setattr(store, "SessionLocal", databases[1].sync_session_factory)
    queries = []
    listeners = []
    for index, database in enumerate(databases):

        def listener(*_args, index=index):
            queries.append((index, get_ident()))

        event.listen(database.sync_engine, "before_cursor_execute", listener)
        listeners.append(listener)
    try:
        if operation == "stats":
            response = await clients[0].get("/api/admin/share-tokens/stats")
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            assert (
                data["total_tokens"],
                data["active_tokens"],
                data["expired_tokens"],
            ) == (2, 1, 1)
            assert {row["id"]: row["is_expired"] for row in data["tokens"]} == {
                1: False,
                2: True,
            }
            assert all(
                datetime.fromisoformat(row["expires_at"]) for row in data["tokens"]
            )
            assert "fixture-owner" not in response.text
            expected = [1, 2]
        elif operation == "cleanup":
            response = await clients[0].post("/api/admin/share-tokens/cleanup")
            assert response.status_code == 200, response.text
            assert response.json()["data"]["cleaned_count"] == 1
            expected = [1]
        else:
            identity = 1 if operation == "delete" else 999
            response = await clients[0].delete(f"/api/admin/share-tokens/{identity}")
            assert response.status_code == (200 if operation == "delete" else 404), (
                response.text
            )
            if operation == "delete":
                assert response.json()["data"] == {"token_id": 1, "stream_id": 71}
            else:
                assert response.json()["detail"] == "Share token not found"
            expected = [2] if operation == "delete" else [1, 2]
        assert queries and {owner for owner, _thread in queries} == {0}
        assert get_ident() not in {thread for _owner, thread in queries}
        for index, database in enumerate(databases):
            event.remove(
                database.sync_engine, "before_cursor_execute", listeners[index]
            )
            with database.sync_session_factory() as db:
                assert [
                    row.id
                    for row in db.query(ShareTokenModel)
                    .order_by(ShareTokenModel.id)
                    .all()
                ] == (expected if index == 0 else [1, 2, 3])
            assert database.sync_engine.pool.checkedout() == 0
    finally:
        for database, listener in zip(databases, listeners, strict=True):
            if event.contains(database.sync_engine, "before_cursor_execute", listener):
                event.remove(database.sync_engine, "before_cursor_execute", listener)
