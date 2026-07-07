# Browser Push QA gate follow-up

Task: t_5fc17aad
Base: http://localhost:7001 via .hermes/tcp-proxy-7001.py to streamvault-develop:7000
Timestamp: 2026-07-07T04:36:56Z

## Existing passing evidence referenced

- Mock QA gate: .hermes/frontend-visual-evidence/qa-matrix-results.json and .hermes/frontend-visual-evidence/streamvault-frontend-qa-matrix.md
- Authorized non-mock WebSocket, HLS and Push server config: .hermes/non-mock-authorized-qa-results.json and .hermes/non-mock-authorized-qa-summary.md

## Environment and browser discovery

```text
node: v22.22.3
npm: 10.9.8
xvfb: /usr/bin/Xvfb
xvfb-run: /usr/bin/xvfb-run
xauth:
playwright: Version 1.61.1
backend: streamvault-develop docker container healthy on private Docker network, proxied to localhost:7001
```

## Commands and outcomes

1. Started local proxy: `python3 .hermes/tcp-proxy-7001.py`.
   - Verified `127.0.0.1:7001 open` before browser runs.

2. Headless normal Playwright context:
   - Command: `NODE_PATH=$PWD/app/frontend/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/hermes/.playwright node .hermes/browser-push-qa-robust.cjs > .hermes/browser-push-qa-results.json 2> .hermes/browser-push-qa-stderr.log`
   - Exit code: 2.
   - Artifact: .hermes/browser-push-qa-results.json
   - Browser facts: secure context true, service worker true, PushManager true, VAPID status 200, authenticated true.
   - Permission/subscription result: `Notification.permission` denied, `navigator.permissions.query` granted, Push subscription failed with `AbortError: Registration failed - permission denied`.
   - Chromium console: `Chrome currently does not support the Push API in incognito mode`.

3. Headless persistent profile Playwright context:
   - Command: `NODE_PATH=$PWD/app/frontend/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/hermes/.playwright node .hermes/browser-push-qa-persistent.cjs > .hermes/browser-push-qa-persistent-results.json 2> .hermes/browser-push-qa-persistent-stderr.log`
   - Exit code: 2.
   - Artifact: .hermes/browser-push-qa-persistent-results.json
   - Browser facts: secure context true, service worker true, PushManager true, VAPID status 200, authenticated true, persistent profile .hermes/browser-push-profile.
   - Permission/subscription result: `Notification.permission` denied, `navigator.permissions.query` granted, Push subscription failed with `AbortError: Registration failed - push service not available`.

4. Headful Chromium under manual Xvfb:
   - Command: `DISPLAY=:99 NODE_PATH=$PWD/app/frontend/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/data/.cache/ms-playwright node /tmp/probe-push-headful.cjs`
   - Exit code: 1.
   - Stable blocker: Chrome for Testing crashes before navigation with `chrome_crashpad_handler: --database is required`, despite `--no-sandbox`, `--disable-crash-reporter`, `--disable-crashpad` and `--disable-dev-shm-usage`.

## Gate verdict

- Browser Push permission: FAIL in this environment. Headless has mismatched permission state and `Notification.permission` remains denied.
- Browser Push subscription creation: FAIL in this environment. Normal headless context is incognito and unsupported by Chromium Push API; persistent headless profile reports no push service.
- Browser Push delivery/event observation: NOT RUN because no real PushManager subscription could be created.

## Required human/device input to close gate

Use a real non-incognito Chrome or Edge browser with notification permission granted against either `http://localhost:7001` on this host or the deployed HTTPS URL. Then create a subscription through the PWA panel or direct browser flow and run `/api/push/test`; capture the push receipt/click event. Alternative: provide an existing active subscription/device tied to this backend so `/api/push/test` can be verified.
