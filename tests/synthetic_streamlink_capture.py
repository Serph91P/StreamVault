"""Synthetic provider executable; only the Streamlink launch boundary is replaced."""
import os
from pathlib import Path
import subprocess
import sys
import time

if '--version' in sys.argv:
    print('streamlink synthetic local capture fixture')
    raise SystemExit(0)
if '-o' not in sys.argv:
    raise SystemExit('fixture refuses unexpected/non-capture Streamlink command')
output=Path(sys.argv[sys.argv.index('-o')+1]).resolve()
root=Path(os.environ['RECORDING_DIRECTORY']).resolve()
assert output.is_relative_to(root)
output.parent.mkdir(parents=True,exist_ok=True)
seconds=int(os.environ.get('STREAMVAULT_SYNTHETIC_CAPTURE_SECONDS','12'))
child=subprocess.Popen([os.environ['STREAMVAULT_SYNTHETIC_FFMPEG'],'-hide_banner','-loglevel','error','-nostdin','-y','-re','-stream_loop','-1','-i',os.environ['STREAMVAULT_SYNTHETIC_MEDIA'],'-t',str(seconds),'-c','copy','-f','mpegts',str(output)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    block=b'local capture diagnostic\n'*2048
    for _ in range(128):
        os.write(1,block); os.write(2,block)
        time.sleep(seconds/128)
    raise SystemExit(child.wait())
finally:
    if child.poll() is None:
        child.kill(); child.wait()
