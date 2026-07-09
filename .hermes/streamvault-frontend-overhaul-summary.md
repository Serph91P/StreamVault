# StreamVault frontend overhaul summary

Date: 2026-07-05T22:24:58Z
Task: KAN2-010
Branch: feat/frontend-overhaul-v2
Base branch: develop
Frontend path: app/frontend

## Final state

The frontend overhaul branch is ready for human review from a QA perspective. The branch preserves the productive route map, keeps Vue 3, Vite, TypeScript, Pinia, Vue Router, SCSS, VitePWA, Workbox and hls.js, and documents the remaining device and performance limitations honestly.

## What changed across the overhaul

The current branch now has documented and implemented evidence for these areas:

- Product and IA direction in .hermes/streamvault-ux-ia-concept.md.
- Design-system contract in .hermes/streamvault-design-system.md.
- App shell separation through AppShell and NavigationWrapper usage.
- Domain state improvements for recording, queue, realtime and notifications.
- Notification Center with read state, mark-all-read action, target links and focus behavior.
- PWA flow cleanup with VitePWA as the single registration owner and push-sw.js imported into the generated service worker.
- Core route refresh for Dashboard, Streamers, Library, players, Settings and Admin Diagnostics.
- Debug and test actions moved out of normal user settings into Admin Diagnostics or dev-only helpers.

## Final verification

Commands and outcomes:

| Check | Result |
| --- | --- |
| npm run lint:tokens | Passed, design-token lint: no violations |
| npm run type-check | Passed, vue-tsc --build completed |
| npm run build | Passed, vite build completed and PWA output generated |
| npm run lint | Passed with 0 errors and 170 no-explicit-any warnings |
| PWA artifact check | Passed, dist/sw.js imports push-sw.js and dist/push-sw.js exists |
| Browser route smoke | Passed for core routes with noted mock-mode media and admin endpoint limits |
| Keyboard basis | Passed for Notification panel open, focus entry, Escape close and focus return |

Build warnings to keep visible:

- Rolldown pure annotation warnings from @vueuse/core.
- Ineffective dynamic import warning for useWebSocket.
- Browserslist data is 6 months old.

## Feature parity handoff

The final route map still includes every productive route listed in .hermes/streamvault-feature-parity-map.md:

- Dashboard: /
- Streamers: /streamers and /streamers/:id
- Library and stored playback: /videos and /videos/:id
- Live playback: /live/:streamer
- Legacy watch route: /streamer/:streamerId/stream/:streamId/watch
- Subscriptions: /subscriptions
- Settings: /settings
- Admin Diagnostics: /admin
- Add streamer flow: /add-streamer, /add-streamer/manual and /add-streamer/import
- Auth and setup routes: /auth/setup, /welcome, /onboarding and /auth/login

Notification Center, realtime state, PWA install, push settings, WebSocket diagnostics and admin notification test actions remain reachable.

## QA artifacts

- .hermes/streamvault-frontend-qa-report.md
- .hermes/streamvault-frontend-overhaul-summary.md
- .hermes/streamvault-feature-parity-map.md final QA section

## Known limitations

- Browser tooling covered 1280 desktop and one 375 mobile visual capture, but did not provide a full controllable matrix for 390, 430, 768, 1024, 1200 and 1440.
- Lighthouse, axe and Web Vitals were not available in the repo, so LCP, INP, CLS and contrast were documented as limitations rather than claimed as measured pass.
- Mock mode cannot validate real backend WebSocket diagnostics, HLS media playback or real push delivery.
- ESLint still reports pre-existing no-explicit-any warnings, but no lint errors.

## Recommended next step

Open or update the PR for feat/frontend-overhaul-v2 against develop with this QA report linked. Before merge, run real-device or Playwright viewport coverage and a production-preview Lighthouse pass if strict acceptance coverage is required.
