"""Admin cleanup respects ownership recorded only in the durable queue."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.models.background_task import BackgroundTask
from app.services.queues.durable_task_store import DurableTaskStore
from app.services.queues.task_progress_tracker import (
    QueueTask,
    TaskPriority,
    TaskStatus,
)
from tests.test_temporary_cleanup_ownership import (
    admin_stack as admin_stack,
    credential_headers,
    expired,
)

ROUTE = "/api/admin/maintenance/cleanup-temp"
SQLITE = "sqlite:///{tmp_path}/cleanup.sqlite"
POSTGRES = os.environ.get("STREAMVAULT_938_TEST_POSTGRES_URL")


def enqueue(store, task_type, payload, *, task_id="media-job", dependencies=()):
    task = QueueTask(
        id=task_id,
        task_type=task_type,
        priority=TaskPriority.NORMAL,
        payload=payload,
        status=TaskStatus.PENDING,
        created_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    store.accept([(task, set(dependencies), "synthetic-938")])
    return task.id


def remux_payload(root, source):
    return {
        "stream_id": 1,
        "streamer_name": "synthetic-938",
        "ts_file_path": str(source),
        "mp4_output_path": str(root / "output.mp4"),
    }


def preview(client, headers):
    response = client.post(ROUTE, headers=headers, json={"dry_run": True})
    assert response.status_code == 200
    assert response.json()["files_removed"] == 0
    return response.json()["candidates"]


def confirm(client, headers, candidates):
    return client.post(
        ROUTE,
        headers=headers,
        json={"dry_run": False, "confirmed": True, "candidates": candidates},
    )


@pytest.mark.parametrize("admin_stack", [SQLITE], indirect=True)
@pytest.mark.parametrize(
    "state", ["pending", "deferred", "running", "retrying", "completed", "failed"]
)
def test_cleanup_rechecks_durable_media_state_after_preview(admin_stack, state):
    app, _, sessions, sentinel, _ = admin_stack
    root = sentinel.parent
    source = expired(root / "staged.tmp")
    control = expired(root / "unused.tmp")
    alias = root / "media-alias"
    alias.symlink_to(source)
    store = DurableTaskStore(sessions)
    headers = credential_headers(admin_stack, "jwt", "admin")
    with closing(TestClient(app)) as client:
        original = preview(client, headers)
        assert {item["path"] for item in original} == {source.name, control.name}
        payload = remux_payload(root, alias)
        # A registered non-path field cannot reserve another file.
        payload["debug_path"] = str(control)
        deps = ()
        if state == "deferred":
            deps = (
                enqueue(
                    store,
                    "orphaned_recovery_check",
                    {"max_age_hours": 48},
                    task_id="parent",
                ),
            )
        try:
            task_id = enqueue(store, "mp4_remux", payload, dependencies=deps)
            actual = "pending" if state == "deferred" else state
            if state in {"running", "retrying", "completed", "failed", "deferred"}:
                claimed = store.claim(1, set(), 1, False)
                if state == "deferred":
                    assert [job.id for job, _ in claimed] == list(deps)
                else:
                    assert [job.id for job, _ in claimed] == [task_id]
            if state == "retrying":
                store.finish(task_id, success=False, error="synthetic retry")
            elif state == "completed":
                store.finish(task_id, success=True)
            elif state == "failed":
                with sessions() as db:
                    db.get(BackgroundTask, task_id).max_retries = 0
                    db.commit()
                store.finish(task_id, success=False, error="synthetic terminal failure")
            assert store.snapshot([task_id])[task_id].status.value == actual
            protected = state not in {"completed", "failed"}
            expected = {control.name} if protected else {source.name, control.name}
            assert {item["path"] for item in preview(client, headers)} == expected
            response = confirm(client, headers, original)
            assert response.status_code == 200
            assert response.json()["files_removed"] == len(expected)
            assert source.exists() is protected
            assert not control.exists()
        finally:
            store.close_owner(remove=True)


@pytest.mark.parametrize("admin_stack", [SQLITE], indirect=True)
@pytest.mark.parametrize(
    ("task_type", "path_fields"),
    [
        ("metadata_generation", {"mp4_path": "artifact.tmp", "output_dir": "output"}),
        ("chapters_generation", {"mp4_path": "artifact.tmp"}),
        ("mp4_remux", {"ts_file_path": "input.ts", "mp4_output_path": "artifact.tmp"}),
        ("mp4_validation", {"ts_file_path": "input.ts", "mp4_path": "artifact.tmp"}),
        ("thumbnail_generation", {"mp4_path": "artifact.tmp"}),
        (
            "segment_concatenation",
            {"segment_files": ["artifact.tmp"], "output_path": "output.ts"},
        ),
        (
            "segment_concatenation",
            {"segment_files": ["input.ts"], "output_path": "artifact.tmp"},
        ),
        ("cleanup", {"files_to_remove": ["artifact.tmp"], "mp4_path": "output.mp4"}),
        ("cleanup", {"cleanup_paths": "artifact.tmp"}),
    ],
)
def test_preview_uses_registered_media_path_contracts(
    admin_stack, task_type, path_fields
):
    app, _, sessions, sentinel, _ = admin_stack
    root = sentinel.parent
    artifact = expired(root / "artifact.tmp")
    sidecar = expired(root / "output" / "sidecar.tmp")
    expired(root / "unused.tmp")
    payload = {
        "stream_id": 1,
        "recording_id": 1,
        "streamer_name": "synthetic-938",
        "base_filename": "media",
        **{
            field: [str(root / path) for path in value]
            if isinstance(value, list)
            else str(root / value)
            for field, value in path_fields.items()
        },
    }
    enqueue(DurableTaskStore(sessions), task_type, payload)
    with closing(TestClient(app)) as client:
        headers = credential_headers(admin_stack, "jwt", "admin")
        expected = {"unused.tmp"}
        if task_type != "metadata_generation":
            expected.add("output/sidecar.tmp")
        assert {item["path"] for item in preview(client, headers)} == expected
        assert artifact.is_file() and sidecar.is_file()


@pytest.mark.parametrize("admin_stack", [SQLITE], indirect=True)
@pytest.mark.parametrize("failure", ["invalid_reference", "unavailable_queue"])
def test_confirmation_fails_closed_when_job_ownership_is_uncertain(
    admin_stack, failure
):
    app, _, sessions, sentinel, _ = admin_stack
    root = sentinel.parent
    source = expired(root / "keep.tmp")
    headers = credential_headers(admin_stack, "jwt", "admin")
    with closing(TestClient(app)) as client:
        original = preview(client, headers)
        assert [item["path"] for item in original] == [source.name]
        if failure == "invalid_reference":
            enqueue(
                DurableTaskStore(sessions),
                "segment_concatenation",
                {
                    "recording_id": 1,
                    "stream_id": 1,
                    "streamer_name": "synthetic-938",
                    "output_path": str(root / "output.ts"),
                    "segment_files": [None],
                },
            )
        else:
            BackgroundTask.__table__.drop(sessions.kw["bind"])
        response = confirm(client, headers, original)
        if failure == "unavailable_queue":
            assert response.status_code == 500
        else:
            assert response.status_code == 200
            assert response.json()["files_removed"] == 0
            assert response.json()["errors"]
        assert source.is_file()


@pytest.mark.parametrize(
    "admin_stack",
    [
        pytest.param(SQLITE, id="sqlite"),
        pytest.param(
            POSTGRES,
            id="postgresql",
            marks=pytest.mark.skipif(
                not POSTGRES,
                reason="requires a disposable STREAMVAULT_938_TEST_POSTGRES_URL",
            ),
        ),
    ],
    indirect=True,
)
def test_confirm_waits_for_inflight_media_admission(admin_stack):
    app, _, sessions, sentinel, _ = admin_stack
    root = sentinel.parent
    source = expired(root / "keep.tmp")
    control = expired(root / "unused.tmp")
    headers = credential_headers(admin_stack, "jwt", "admin")
    engine = sessions.kw["bind"]
    inserted, release, decision = Event(), Event(), Event()
    with closing(TestClient(app)) as client:
        original = preview(client, headers)
        assert {item["path"] for item in original} == {source.name, control.name}

        def pause_admission(conn, cursor, statement, *args):
            if statement.startswith("INSERT INTO background_tasks "):
                inserted.set()
                assert release.wait(5), "test did not release admission"

        def observe_cleanup(conn, cursor, statement, *args):
            if statement == "BEGIN IMMEDIATE" or "pg_advisory_xact_lock" in statement:
                decision.set()

        with ThreadPoolExecutor(max_workers=2) as workers:
            event.listen(engine, "after_cursor_execute", pause_admission)
            try:
                acceptance = workers.submit(
                    enqueue,
                    DurableTaskStore(sessions),
                    "mp4_remux",
                    remux_payload(root, source),
                )
                assert inserted.wait(4), "durable insert did not start"
                event.listen(engine, "before_cursor_execute", observe_cleanup)
                try:
                    cleanup = workers.submit(confirm, client, headers, original)
                    cleanup.add_done_callback(lambda _: decision.set())
                    assert decision.wait(4), (
                        "cleanup reached neither guard nor response"
                    )
                finally:
                    release.set()
                    event.remove(engine, "before_cursor_execute", observe_cleanup)
                assert acceptance.result(timeout=5) == "media-job"
                response = cleanup.result(timeout=5)
            finally:
                release.set()
                event.remove(engine, "after_cursor_execute", pause_admission)
        assert response.status_code == 200
        assert response.json()["files_removed"] == 1
        assert source.is_file()
        assert not control.exists()
