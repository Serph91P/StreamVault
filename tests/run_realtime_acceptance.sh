#!/bin/sh
# Isolated runtime-image verification; never mounts existing app data/containers.
set -eu
: "${TMPDIR:?Set TMPDIR to an owned scratch directory}"
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime=$(mktemp -d "$TMPDIR/streamvault-realtime.XXXXXX")
trap 'rm -rf "$runtime"' EXIT HUP INT TERM
uv pip install --target "$runtime/deps" pytest==9.1.1 pytest-asyncio==1.4.0
if [ "$#" -eq 0 ]; then
    set -- tests/test_websocket_replay.py tests/test_realtime_socket_acceptance.py \
        tests/test_api_realtime_security.py tests/test_auth_middleware_contract.py
fi
# Stream code through stdin: the Docker daemon need not share the host filesystem.
tar --exclude=app/frontend --exclude=__pycache__ --exclude=.pytest_cache \
    -c -C "$repo" app tests conftest.py pyproject.toml -C "$runtime" deps |
    docker run --rm -i --network none --entrypoint sh --tmpfs /scratch \
        --tmpfs /app/app/frontend/dist \
        -e PYTHONPATH=/scratch:/scratch/deps -e TMPDIR=/scratch \
        -e DATABASE_URL=sqlite:///:memory: \
        -e TWITCH_APP_ID=synthetic -e TWITCH_APP_SECRET=synthetic \
        -e BASE_URL=http://localhost:8000 -e LOG_DIR=/scratch/logs \
        -e RECORDING_DIRECTORY=/scratch/recordings \
        frequency2098/streamvault:2.24.0-dev \
        -c 'cd /scratch && tar -xf - && python -m pytest -q -p no:cacheprovider "$@"' sh "$@"
