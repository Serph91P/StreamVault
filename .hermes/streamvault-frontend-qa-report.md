# StreamVault frontend QA report

Date: 2026-07-05
Branch: feat/frontend-overhaul-plan
PR: https://github.com/Serph91P/StreamVault/pull/700

## Automated checks

| Check | Command | Result |
| --- | --- | --- |
| Frontend lint | npm run lint -- --max-warnings=9999 | Passed with warnings only, 0 errors after unused import fix |
| Design token lint | npm run lint:tokens | Passed, design-token lint: no violations |
| Typecheck | npm run type-check | Passed, vue-tsc --build |
| Production build | npm run build-only | Passed, Vite generated dist/sw.js and dist/workbox-dcde9eb3.js |
| Backend replay test | uv run --with-requirements requirements.txt --with pytest pytest -q tests/test_websocket_replay.py | Passed, 4 passed |
| Ruff changed Python format | uv tool run ruff format --check app/main.py app/middleware/auth.py app/services/communication/websocket_manager.py tests/test_websocket_replay.py | Passed after formatting websocket_manager.py |
| Ruff changed Python lint | uv tool run ruff check app/main.py app/middleware/auth.py app/services/communication/websocket_manager.py tests/test_websocket_replay.py | Passed |
| Diff whitespace | git diff --check | Passed |
| Unicode dash guard | custom diff and source scans on changed paths | Passed for added diff lines and generated .hermes docs |
| CI | GitHub PR #700 checks | All status checks completed SUCCESS |

## Build warnings documented

- Rolldown reports invalid pure annotation comments from @vueuse/core.
- useWebSocket.ts is dynamically imported and also statically imported by realtime store, so the dynamic import does not split that module.
- Browserslist data is stale and should be updated separately.
- ESLint still reports many no-explicit-any warnings in existing and touched frontend files, but CI only failed on unused imports and now passes.

## Route QA matrix

| Surface | Desktop 1024, 1200, 1440 | Mobile 375, 390, 430, 768 | Keyboard and a11y | Result |
| --- | --- | --- | --- | --- |
| Dashboard | Multi column status layout intended | Single column status feed intended | Cards and actions use visible labels | Pass by build and source review, browser smoke still recommended |
| Streamers | Filter and cards available | Touch cards and sheet model intended | Buttons and filters labeled | Pass by source review and CI |
| Streamer Detail | Cockpit tabs and status sections | Segmented tabs and action sheet model intended | Tabs and actions need manual focus pass | Pass with manual follow-up |
| Library | Grid and metadata cards | Compact card layout intended | Missing file state visible | Pass by source review |
| Video Player | Player route and status/error components | Full screen player route intended | Player controls need device check | Pass with manual follow-up |
| Live Player | Player and side status model | Player first layout intended | HLS errors have recovery copy | Pass with manual follow-up |
| Settings | Grouped panels | Stacked panels | Forms use labels and errors | Pass by source review |
| Notifications | Panel with filters and target actions | Sheet style behavior intended | Read and dismiss actions are buttons | Pass by source review |
| Admin Diagnostics | Raw diagnostics isolated | Read mostly mobile support | Diagnostic controls labeled | Pass by source review |
| Auth and setup | Full screen flow | Full screen flow | Form focus and errors require manual browser pass | Pass by source review |

## PWA and push QA

| Item | Result | Notes |
| --- | --- | --- |
| Single frontend registration source | Pass | main.ts virtual:pwa-register owns registration |
| public/sw.js removed | Pass | stale generated worker removed from source |
| public/registerSW.js removed | Pass | duplicate manual registration removed |
| dist/sw.js generation | Pass | npm run build-only generated dist/sw.js |
| push-sw custom handler retained | Pass | notificationclick target logic remains |
| Android installed PWA push | Not run | Requires real Android device |
| iOS Home Screen push | Not run | Requires Safari 16.4 plus installed Home Screen app |
| PWA standalone display | Not run | Requires browser or device installation |

## Feature parity QA

- Product routes are preserved.
- Legacy watch route remains.
- Removed items are debug, test, generated artifact or orphan asset paths.
- WebSocket monitor and notification channel tests are kept in Admin Diagnostics.
- Backend replay endpoint has focused pytest coverage.
- Notification and push click targets normalize known legacy streamer routes.

## Performance QA

| Topic | Result |
| --- | --- |
| Route lazy loading | Verified in router source |
| Build chunk generation | Verified by Vite build output |
| Skeleton and state components | Present in dashboard, cards and shared components |
| Realtime event fanout | Central realtime store and listeners reduce scattered watchers |
| Player lazy route | Player routes are lazy loaded |
| Core Web Vitals | Not measured in real browser in this environment |
| Large chunks | LivePlayer chunk remains large and should be profiled in follow-up |

## Known QA limits

- No real browser visual screenshots were captured in this environment.
- No authenticated backend browser session was used for full interactive QA.
- No Android or iOS device was available for installed PWA push validation.
- Full WCAG audit with axe or screen reader remains recommended.
