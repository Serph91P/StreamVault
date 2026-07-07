# StreamVault frontend visual accessibility and performance matrix

Date: 2026-07-07T03:55:37Z
Task: t_ce2be569, N-QA-001A remediation
Branch: feat/frontend-product-overhaul-final
Base URL: http://127.0.0.1:4173 using production preview from a VITE_USE_MOCK_DATA=true build

## Gate result

PASS recommendation for the actionable mock-mode N-QA-001 gates. The production preview matrix completed all route and viewport captures, axe returned zero violations in the scanned matrix, notification dialog keyboard Escape closed successfully, and Lighthouse dashboard performance stayed above the prior dev mock blocker threshold.

The only remaining non-source blockers are environment limits: real backend WebSocket, real HLS playback and real push delivery still require a non-mock backend/device environment.

## Evidence captured

- Viewports: 390, 430, 768, 1024, 1280, 1440
- Core routes: dashboard, streamers, streamer-detail, library, stored-player, live-player, subscriptions, settings, admin, add-streamer
- Screenshot files: 60 route screenshots plus reduced-motion evidence in this folder
- Raw matrix JSON: `.hermes/frontend-visual-evidence/qa-matrix-results.json`
- Lighthouse JSON: `.hermes/frontend-visual-evidence/lighthouse-dashboard.json`
- QA script: `.hermes/frontend-visual-evidence/run-qa-matrix.mjs`

All 60/60 route and viewport navigations completed. The script detected 0 horizontal overflow findings in the requested matrix.

## axe summary

axe ran on all core routes at 390 and 1280.

| Rule | Count |
| --- | ---: |
| All violations | 0 |

## Keyboard and reduced motion

| Check | Result |
| --- | --- |
| Notification dialog opens from keyboard-targetable button | pass |
| Focus moves after Tab | pass |
| Escape closes notification dialog | pass |
| Reduced motion media query honored | pass |

Keyboard details: notificationDialog=True, focusMoved=True, escapeCloses=True.

## Web Vitals browser measurements

Measured through PerformanceObserver on the production preview mock app at 1280px. Values are milliseconds except CLS.

| Route | Path | FCP | LCP | CLS | INP approx |
| --- | --- | ---: | ---: | ---: | ---: |
| dashboard | / | 52 | 232 | 0 | 3 |
| streamers | /streamers | 36 | 296 | 0 | 2 |
| streamer-detail | /streamers/1 | 36 | 272 | 0 | 1 |
| library | /videos | 36 | 264 | 0 | 3 |
| stored-player | /videos/1 | 28 | 772 | 0 | 2 |
| live-player | /live/streamer_alpha | 52 | 292 | 0.0001 | 1 |
| subscriptions | /subscriptions | 44 | 384 | 0 | 2 |
| settings | /settings | 52 | 608 | 0 | 1 |
| admin | /admin | 64 | 344 | 0 | 1 |
| add-streamer | /add-streamer | 32 | 352 | 0 | 2 |

## Lighthouse dashboard result

| Category | Score |
| --- | ---: |
| performance | 98 |
| accessibility | 96 |
| best-practices | 100 |
| seo | 92 |

| Metric | Display value |
| --- | --- |
| first-contentful-paint | 1.7 s |
| largest-contentful-paint | 2.0 s |
| total-blocking-time | 30 ms |
| cumulative-layout-shift | 0 |
| speed-index | 1.7 s |
| interactive | 2.0 s |

## Build and static checks

Commands run from `app/frontend`:

- `npm run lint:tokens`: passed, `design-token lint: no violations`.
- `npm run type-check`: passed.
- `VITE_USE_MOCK_DATA=true npm run build-only`: passed in 1.81s. Build still warned about Rolldown pure annotations in @vueuse/core and stale Browserslist data.
- `QA_BASE_URL=http://127.0.0.1:4173 node ../../.hermes/frontend-visual-evidence/run-qa-matrix.mjs`: passed.
- `npx --yes lighthouse@13.4.0 http://127.0.0.1:4173/ --port=9222 --output=json --output-path=../../.hermes/frontend-visual-evidence/lighthouse-dashboard.json --quiet`: passed.

## Final blockers

No actionable source or QA harness blockers remain in mock-mode production preview. Real backend WebSocket, real HLS playback and real push delivery remain outside this mock-mode matrix and should be verified in a non-mock environment before product acceptance that depends on those integrations.
