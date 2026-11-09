"""Standalone Linux exec shim; never use preexec_fn in a threaded server."""

import ctypes
import os
import signal
import sys


def main():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    # Covers parent death between spawn and prctl: never launch an orphan writer.
    if os.getppid() != int(sys.argv[1]):
        raise SystemExit(125)
    os.execvp(sys.argv[2], sys.argv[2:])


if __name__ == "__main__":
    main()
