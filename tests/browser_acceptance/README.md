# Integrated real-browser acceptance (#933)

This replaces the earlier notification-only artifact harness. It runs Chromium
against the candidate's **production app factory, middleware, SPA router, business
routers and services**. There are no Playwright API fulfills. Settings are checked
through independent SQLite sessions and fresh browser loads, not success toasts.

## Run

From the repository root, with the existing frontend dependencies installed:

```sh
(cd app/frontend && node scripts/build-artifact-provenance.mjs build --mode real)
python3 tests/browser_acceptance/run.py \
  --backend "$PWD" --frontend "$PWD/app/frontend" \
  --output "$TMPDIR/streamvault-933-evidence"
```

The runner rejects MOCK build provenance. It requires Python, Node, Docker and the
runtime image `frequency2098/streamvault:2.24.0-dev` (includes FFmpeg and backend
dependencies). This workspace's Docker daemon cannot bind-mount agent files, so
candidate source/build files are streamed as a tar into an automatically removed
container. Its disposable `/scratch` tmpfs contains the SQLite database, generated
12-second video and process-restart markers. Networking shares the existing
`hermes-gateway-developer` container; Uvicorn binds only an ephemeral loopback port.
Chromium defaults to the installed agent-cache executable; override
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` if needed. `TMPDIR` must be writable.

Random test-only auth credentials are passed in memory/environment and never
written to the evidence. The test user exists only in disposable SQLite. No
production account, OAuth token or API key is needed. Runner cleanup stops/removes
the test container and removes archive/XDG scratch even when the browser fails.
The output contains a result JSON and screenshots; stdout records pass/failure.

## Executed workflow

Both 1440×900 light desktop and 390×844 dark touch/mobile sessions exercise:

- Login through the actual auth UI; direct SPA navigation and reload.
- Global codec save → independent SQLite read → reload; channel-specific recording
  and notification changes, independently persisted cleanup policy, fresh reload,
  and a real cleanup-service invocation that retains both synthetic recordings.
- Channel management enable/disable persistence.
- Notification HTTP response → matching WebSocket event → one feed row and unread
  count, without document reload.
- Transport disconnect with an event emitted while offline → automatic reconnect,
  replay and deduplication.
- **Actual Uvicorn child-process termination/restart**, changed PID/generation,
  cached queue still visible with offline notice, replay reset, and a fresh live
  event after restart; SQLite settings survive the process restart.
- Connected-socket queue hydration followed by real tracker task
  start/progress/completion → store/DOM, with no replacement REST refresh.
- Real generated H.264 media HTTP delivery, decoded playback/pause/seek, confirmed
  player deletion/navigation and separately confirmed stream deletion, each checked
  against an independent database read.
- No JavaScript page errors or failed business API responses.

`backend.py` adds authenticated `/_acceptance/*` controls **only to the test app**.
They seed synthetic records, observe the disposable DB, invoke real notification
producers/task tracker, and request the process restart. They are not product
routes. `supervisor.py` owns that disposable Uvicorn process; it is not a deployed
service. Production lifespan/background schedulers are deliberately disabled to
avoid contacting external services.

## Explicit limits

Synthetic identities/media/tasks are real local test data, not proof of Twitch
OAuth consent/token exchange, followed-channel lookup, external recording start,
production schedulers, PostgreSQL or deployment. Twitch component/API-contract
regressions are separate unit tests. Settings fixture/responsive matrices remain
separate evidence, never a substitute for this real-backend run. The 254-action
static preservation receipt does not mean 254 executed server journeys.
