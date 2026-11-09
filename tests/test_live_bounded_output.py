"""A pathological live diagnostic line must not strand the producer's stderr pipe."""
import asyncio
import logging
import sys

import pytest

from app.services.live_streaming_service import LiveStreamingService


@pytest.mark.asyncio
async def test_live_overlong_diagnostics_keep_draining_and_retain_only_safe_tail(tmp_path, caplog):
    finished=tmp_path/'producer-finished'
    code='''import os,sys
os.write(2,b'x'*131072+b'\\n')
for n in range(256): os.write(2,b'normal diagnostic\\n'*1024)
os.write(2,b'Authorization=OAuth local-fixture-secret\\n')
open(sys.argv[1],'wb').write(b'complete')
'''
    child=await asyncio.create_subprocess_exec(sys.executable,'-c',code,str(finished),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
    service=LiveStreamingService()
    service._streamlink_output_secrets[child]=('local-fixture-secret',)
    with caplog.at_level(logging.DEBUG,logger='streamvault'):
        reader=asyncio.create_task(service._log_stderr(child,'streamlink-fixture'))
        try:
            async with asyncio.timeout(3):
                await child.wait()
                await reader
            assert child.returncode==0 and finished.read_bytes()==b'complete'
            assert 'normal diagnostic' in caplog.text
            assert 'local-fixture-secret' not in caplog.text
            assert len(caplog.text)<70000
            assert child not in service._streamlink_output_secrets
        finally:
            if child.returncode is None: child.kill()
            if not reader.done():
                reader.cancel()
                await asyncio.gather(reader,return_exceptions=True)
            await child.communicate()
