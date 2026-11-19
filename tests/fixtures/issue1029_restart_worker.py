"""Subprocess half of the signed callback/persistent catalog restart contract."""

import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from app import dependencies
from app.models import Category, Recording, Stream, StreamEvent
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_issue1029_retry_contract import (
    ctx as context_fixture,
    payload,
    seed,
    signed,
)
from tests.test_processing_callback_ownership import close_owned


async def main(root, kind, phase):
    patches = pytest.MonkeyPatch()
    fixture = context_fixture.__wrapped__(
        root,
        patches,
        SimpleNamespace(node=SimpleNamespace(name=f"restart-{kind}-{phase}")),
    )
    context = await anext(fixture)
    manager = None
    children = []
    try:
        context.app.state.recording_manager = None
        manager = await run_in_thread_pool(
            dependencies.get_application_recording_manager, context.connection
        )
        context.registry.recording_service = manager
        lifecycle = manager.orchestrator.lifecycle_manager

        async def spawn(**kwargs):
            if phase == "fail":
                return None
            child = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import sys; print('ready',flush=True); sys.stdin.buffer.read()",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            children.append(child)
            assert await child.stdout.readline() == b"ready\n"
            manager.process_manager.active_processes[
                f"stream_{kwargs['stream'].id}"
            ] = child
            return child

        async def monitor(_):
            await asyncio.Event().wait()

        patches.setattr(manager.process_manager, "start_recording_process", spawn)
        patches.setattr(lifecycle, "monitor_and_process_recording", monitor)
        if kind == "stream.offline":
            if phase == "fail":
                # Begin a real owned recording, then fail its incoming stop boundary.
                async def spawn_offline(**kwargs):
                    child = await asyncio.create_subprocess_exec(
                        sys.executable,
                        "-c",
                        "import sys; print('ready',flush=True); sys.stdin.buffer.read()",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        start_new_session=True,
                    )
                    children.append(child)
                    assert await child.stdout.readline() == b"ready\n"
                    manager.process_manager.active_processes[
                        f"stream_{kwargs['stream'].id}"
                    ] = child
                    return child

                patches.setattr(
                    manager.process_manager, "start_recording_process", spawn_offline
                )
                assert (
                    await context.client.post(
                        "/eventsub", **signed(context, payload("stream.online"))
                    )
                ).status_code == 204

                async def denied_stop(*args, **kwargs):
                    raise OSError("synthetic stop failure before interpreter restart")

                patches.setattr(
                    manager.process_manager, "terminate_process", denied_stop
                )
            else:
                await manager.startup_reconcile()
        path = root / "request.json"
        if phase == "fail":
            if kind == "channel.update":
                seed(context, kind)
            request = signed(context, payload(kind))
            path.write_text(
                json.dumps(
                    {
                        "content": request["content"].decode(),
                        "headers": request["headers"],
                    }
                )
            )
        else:
            request = json.loads(path.read_text())

        def deny_category(session):
            if phase == "fail" and any(
                isinstance(row, Category) for row in session.new
            ):
                raise SQLAlchemyError(
                    "synthetic category commit fault before process restart"
                )

        event.listen(
            context.database.sync_session_factory, "before_commit", deny_category
        )
        result = await context.client.post("/eventsub", **request)
        assert result.status_code == (500 if phase == "fail" else 204)
        if phase == "retry":
            assert (
                await context.client.post("/eventsub", **request)
            ).status_code == 204
            if kind == "stream.online":
                assert len(children) == 1 and children[0].returncode is None
                offline = await context.client.post(
                    "/eventsub", **signed(context, payload("stream.offline"))
                )
                assert offline.status_code == 204
                assert children[0].returncode is not None
            with context.database.sync_session_factory() as session:
                assert session.query(Stream).count() == 1
                assert session.query(Recording).count() == (
                    0 if kind == "channel.update" else 1
                )
                assert session.query(StreamEvent).count() == 1
                if kind == "channel.update":
                    assert session.query(Category).count() == 1
                    assert session.query(StreamEvent).one().title == "After"
                else:
                    assert session.query(Recording).one().status == "stopped"
        event.remove(
            context.database.sync_session_factory, "before_commit", deny_category
        )
        print(
            json.dumps(
                {
                    "kind": kind,
                    "phase": phase,
                    "http": result.status_code,
                    "children": len(children),
                }
            ),
            flush=True,
        )
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
        if manager:
            await close_owned([context.app])
        await fixture.aclose()
        patches.undo()


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), sys.argv[2], sys.argv[3]))
