"""Loopback-only test ingress into the real app/lifespan/queue, never deployed."""
import os
from sqlalchemy.engine import make_url

url=make_url(os.environ['DATABASE_URL'])
assert url.get_backend_name()=='postgresql' and url.host=='127.0.0.1'
assert (url.database or '').startswith('streamvault_test_')
assert os.environ['STREAMVAULT_FULLAPP_QUEUE_PROBE']=='1'

from fastapi import Request, HTTPException
from app.main import app
from app.services.background_queue_service import background_queue_service
from app.dependencies import get_recording_manager

# Fault injection is confined to this guarded test entrypoint, not product code.
if os.environ.get('STREAMVAULT_PROMOTION_CRASH_MARKER'):
    from pathlib import Path
    import signal
    native_replace=os.replace
    def crash_after_real_promotion(source,destination):
        native_replace(source,destination)
        if Path(destination)==Path(os.environ['STREAMVAULT_SYNTHETIC_MEDIA']).with_suffix('.mp4'):
            Path(os.environ['STREAMVAULT_PROMOTION_CRASH_MARKER']).write_text('promoted-before-step-commit')
            os.kill(os.getpid(),signal.SIGKILL)
    os.replace=crash_after_real_promotion


@app.post('/__local_fixture/chain')
async def enqueue_fixture(request: Request):
    if request.headers.get('x-fixture-token')!=os.environ['STREAMVAULT_FIXTURE_TOKEN']:
        raise HTTPException(status_code=403)
    payload=await request.json()
    ids=await background_queue_service.queue_manager.enqueue_recording_post_processing(**payload)
    return {'ids':ids}


@app.post('/__local_fixture/capture')
async def start_capture_fixture(request: Request):
    if request.headers.get('x-fixture-token')!=os.environ['STREAMVAULT_FIXTURE_TOKEN']:
        raise HTTPException(status_code=403)
    payload=await request.json()
    identifier=await get_recording_manager().start_recording(payload['stream_id'],payload['streamer_id'])
    if identifier is None:
        raise HTTPException(status_code=500,detail='Real recording manager did not start fixture')
    return {'recording_id':identifier}
