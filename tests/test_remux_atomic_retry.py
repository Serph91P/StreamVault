"""A cancelled/retried remux must never expose or delete a partial final MP4."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
from pathlib import Path
import subprocess

import pytest
from app.utils import ffmpeg_utils
from app.utils.media_process import media_process


@pytest.mark.asyncio
async def test_owned_remux_cancellation_preserves_final_then_retry_promotes_atomically(tmp_path,monkeypatch):
    source=tmp_path/'source.ts'; target=tmp_path/'final.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=24','-t','3','-c:v','mpeg2video','-threads','1','-f','mpegts',str(source)],check=True,capture_output=True)
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    from uuid import uuid4
    from app.utils.queue_ownership import QueueOwnerFile, queue_owner_file
    current=QueueOwnerFile(tmp_path/'owners',str(uuid4())); current.open()
    dead=QueueOwnerFile(tmp_path/'owners',str(uuid4())); dead.open(); dead.close()
    live=QueueOwnerFile(tmp_path/'owners',str(uuid4())); live.open()
    missing=str(uuid4())
    files=[]
    for token in (dead.token,live.token,missing):
        directory=tmp_path/'.final.mp4.processing'/token; directory.mkdir(parents=True)
        partial=directory/f'{uuid4()}.mp4'; partial.write_bytes(b'partial'); files.append(partial)
    context=queue_owner_file.set(current)
    target.write_bytes(b'previous complete media stays untouched')
    previous=target.read_bytes(); launched=asyncio.Event(); pids=[]
    @asynccontextmanager
    async def slow_process(*command,**kwargs):
        async with media_process(command[0],'-re',*command[1:],**kwargs) as result:
            pids.append(result[0].pid); launched.set(); yield result
    monkeypatch.setattr(ffmpeg_utils,'media_process',slow_process)
    running=asyncio.create_task(ffmpeg_utils.embed_metadata_with_ffmpeg_wrapper(str(source),str(target),{},overwrite=True))
    try:
        await asyncio.wait_for(launched.wait(),3)
        assert target.read_bytes()==previous
        running.cancel()
        with pytest.raises(asyncio.CancelledError): await running
        assert target.read_bytes()==previous
        assert not list(tmp_path.glob('.final.mp4.processing-*.mp4'))
        assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
        import psutil
        assert pids and all(not psutil.pid_exists(pid) for pid in pids)
        monkeypatch.setattr(ffmpeg_utils,'media_process',media_process)
        result=await ffmpeg_utils.embed_metadata_with_ffmpeg_wrapper(str(source),str(target),{},overwrite=True)
        assert result['success'] is True and target.read_bytes()!=previous
        assert not files[0].exists()
        assert files[1].read_bytes()==b'partial' and files[2].read_bytes()==b'partial'
        assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
        assert await ffmpeg_utils.validate_mp4(str(target))
        assert not list(tmp_path.glob('.final.mp4.processing-*.mp4'))
        digest=hashlib.sha256(target.read_bytes()).hexdigest()
        refused=await ffmpeg_utils.embed_metadata_with_ffmpeg_wrapper(str(source),str(target),{})
        assert refused['success'] is False
        assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
        broken=tmp_path/'broken.ts'; broken.write_bytes(b'not media'*100)
        failed=await ffmpeg_utils.embed_metadata_with_ffmpeg_wrapper(str(broken),str(target),{},overwrite=True)
        assert failed['success'] is False and broken.read_bytes()==b'not media'*100
        assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
    finally:
        if not running.done(): running.cancel(); await asyncio.gather(running,return_exceptions=True)
        queue_owner_file.reset(context); current.close(); live.close()
