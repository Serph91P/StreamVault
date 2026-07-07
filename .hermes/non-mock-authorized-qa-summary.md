# Authorized non-mock QA follow-up

Task: `t_3200d176`
Container: `streamvault-develop`
Local proxy: `http://127.0.0.1:7001` to Docker backend `192.168.96.3:7000`

## Authorization

Max approved doing what is needed to unblock the non-mock QA gate, including creating temporary QA prerequisites in the running backend.

## Actions taken

- Created temporary authenticated QA sessions directly in the running backend database.
- Added test streamer `summit1g` as `is_test_data=True` when missing, to exercise real Streamlink-backed HLS.
- Started a local TCP proxy so the backend could be accessed as `localhost` for host-header-sensitive HTTP and WebSocket checks.
- Ran `.hermes/non-mock-authorized-qa.py`.
- Attempted browser push subscription QA with `.hermes/browser-push-qa.cjs` after installing Playwright Chromium into `/opt/data/.cache/ms-playwright`.

## Results

Artifact: `.hermes/non-mock-authorized-qa-results.json`

| Gate | Result | Evidence |
|---|---|---|
| Authenticated backend API | Passed | `GET /api/live/active` returned 200 with authenticated Bearer session. |
| WebSocket delivery | Passed | WebSocket connected and received `connection.status`, then received a real `channel.update` event triggered by `POST /api/settings/test-websocket-notification`. |
| HLS playback endpoint | Passed | `POST /api/live/start/summit1g` returned 200 and `/api/live/stream/<session>/playlist.m3u8?token=...` returned a real `#EXTM3U` playlist with segments. The session was stopped after verification. |
| Push server configuration | Passed | `/api/push/debug` reports `vapid_configured=true`, global notifications enabled, streamer settings present. `/api/push/vapid-public-key` returned configured public key. `/api/push/test-local` returned local notification payload. |
| Browser Push subscription/delivery | Still blocked | Headless Chromium reports notification permission denied and service worker registration/subscription path fails with `AbortError: Registration failed - permission denied`. Headful Chromium under Xvfb is blocked by local toolchain issues: first `xvfb-run` lacked `xauth`, then downloaded Chrome crashed with `chrome_crashpad_handler: --database is required`. |

## Remaining blocker

Only the real browser/device Push subscription and delivery gate remains unproven. Backend-side push prerequisites are now configured and verified, but this environment still cannot produce a real PushManager subscription in Chromium.

Needed to close fully:

- run the browser push subscription flow in a real Chrome/Edge browser against `http://localhost:7001` or the deployed HTTPS URL, or
- provide/attach an existing active push subscription/device for the selected backend, then run `/api/push/test`.

## Non-goals and cleanup notes

- No app source code was changed for backend behavior.
- No commit or push was performed.
- Temporary QA sessions were created in the running `streamvault-develop` database. They expire by normal 24h session timeout.
- Test streamer `summit1g` was added with `is_test_data=True` to the `streamvault-develop` database for HLS verification.
