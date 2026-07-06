# StreamVault frontend QA report

Date: 2026-07-05T22:24:58Z
Task: KAN2-010
Branch: feat/frontend-overhaul-v2
Frontend path: app/frontend

## Scope

Final QA for the frontend overhaul branch covered build checks, feature parity evidence, browser route smoke checks, PWA service worker ownership, keyboard basics, visual layout review, accessibility basis and performance signals.

Graphify note: this worktree does not contain graphify-out/graph.json, so no live Graphify query could run here. The QA used the existing Graphify-derived .hermes artifacts and then verified against source and browser behavior.

## Build and static checks

Commands run from app/frontend unless stated otherwise.

| Check | Result | Evidence |
| --- | --- | --- |
| npm run lint:tokens | Pass | design-token lint: no violations |
| npm run type-check | Pass | vue-tsc --build completed |
| npm run build | Pass | vite build completed in 2.06s, PWA generated dist/sw.js and dist/workbox-dcde9eb3.js |
| npm run lint | Pass with warnings | ESLint: 0 errors, 170 warnings in 32 files, all @typescript-eslint/no-explicit-any |
| git diff --check | Pass | no whitespace errors before docs were added |
| PWA artifact check | Pass | dist/sw.js imports push-sw.js and dist/push-sw.js exists |
| Service worker source check | Pass | registerSW appears in app/frontend/src/main.ts, workbox import config appears in both vite configs, no manual serviceWorker.register hit in source check |

Build warnings observed:

- Rolldown INVALID_ANNOTATION warnings in node_modules/@vueuse/core/dist/index.js.
- Ineffective dynamic import warning for src/composables/useWebSocket.ts because it is also statically imported by src/stores/realtime.ts.
- Browserslist data is 6 months old.

These warnings did not fail the build.

## Browser QA environment

- Browser: HeadlessChrome 149.0.7827.55 through Hermes browser tools.
- Dev server: npm run dev:mock -- --host 127.0.0.1 on http://127.0.0.1:5173.
- Mock mode allowed route smoke without a backend session.
- Playwright package was not installed in app/frontend, so automated viewport matrix scripts were not available without adding tooling.

## Route smoke results

| Route | Result | Evidence |
| --- | --- | --- |
| / | Pass | Dashboard rendered status-first hero, operational cards, live streamers, active recordings, latest videos, queue, failures and realtime activity. |
| /streamers | Pass | Streamers rendered search, filters, sort, Add Streamer and mock streamer cards with live and recording states. |
| /videos | Pass | Videos rendered search, filters, sort and a 12 video library list. |
| /settings | Pass | Settings rendered section navigation and Twitch Connection. PWA and Mobile section rendered install, online, push support, denied permission guidance and subscription state. |
| /admin | Partial pass | Admin Diagnostics rendered health, info, WebSocket monitor, notification diagnostics and collapsed advanced diagnostic groups. WebSocket monitor showed a mock dev-server JSON parse error because no backend endpoint was present. |
| /add-streamer | Pass | Add New Streamer rendered back action and manual or Twitch import choices. |
| /subscriptions | Pass | Subscription Management rendered refresh, resubscribe, delete disabled state and empty state. |
| /videos/1 | Pass with expected mock media error | Stored player rendered controls, metadata and recoverable Playback Error with Retry because mock media file was unavailable. |
| /live/streamer_alpha | Pass with mock stream limitation | Live player rendered live state, stream info, codec selector and actions. Video element stayed unable to play media in mock mode. |

## Desktop visual review

Viewport evidence included 1280x720 browser rendering. The Dashboard showed the desktop shell with left sidebar, header utilities, large status-first hero and operational cards. No obvious overlap, clipped primary actions or unreadable contrast was visible at that viewport.

Widths explicitly requested but not fully covered by a controllable browser viewport API: 1024, 1200 and 1440. The active desktop browser evidence covered 1280. Source design tokens define lg 1024, xl 1200 and 2xl 1440 breakpoints in the design-system artifact, but this QA could not visually verify every requested width in the available tool session.

## Mobile and PWA review

Mobile and PWA acceptance was checked by source, PWA build output and available browser inspection.

Observed mobile visual evidence on the live player showed:

- Bottom navigation present with Dashboard, Streamers, Library, Subscriptions and Settings.
- Header actions fit at the top without covering the player content.
- Live player content stacked into cards, with Back, LIVE badge, Connecting status, player area and Stream Info.
- No obvious horizontal overflow or clipped primary controls was visible in the captured mobile view.

Source and build evidence:

- Bottom navigation safe area and 44px touch target expectations are documented in .hermes/streamvault-pwa-mobile-pass.md.
- VitePWA owns registration through virtual:pwa-register in app/frontend/src/main.ts.
- Custom push behavior remains in app/frontend/public/push-sw.js and is imported by the generated service worker.
- dist/sw.js imports push-sw.js and dist/push-sw.js exists after build.

Widths explicitly requested but not fully covered by a controllable browser viewport API: 375, 390, 430 and 768. The available visual mobile evidence covered 375. The remaining widths should be rechecked in a real browser or Playwright viewport matrix before merging if strict device coverage is required.

## Accessibility basis

Checked items:

- Keyboard: Notification panel can open, Tab moved focus into the dialog close button, Escape closed the dialog and focus returned to the Notifications trigger.
- Dialog semantics: Notification panel and shared sheet/modal components expose role="dialog" and aria-modal="true" in source or rendered output.
- Status language: Dashboard, Streamers, player, PWA settings and Admin Diagnostics expose visible text status, not only color.
- Reduced motion: source search found prefers-reduced-motion handling in App.vue, AppShell.vue, ToastNotification.vue, VideoPlayer.vue and BaseSheet.vue.
- PWA push denied state includes troubleshooting guidance instead of a silent failure.

Limitations:

- No automated axe or Lighthouse audit ran because those tools are not installed in this repo.
- Contrast was visually checked only at available browser captures, not measured numerically.
- Full keyboard traversal across every form and sheet was not exhaustively tested.

## Performance basis

Measured in the browser on the dev server for /live/streamer_alpha:

- first-paint: 52 ms
- first-contentful-paint: 52 ms
- DOMContentLoaded: 78 ms
- loadEventEnd: 81 ms
- navigation encoded body size: 4817 bytes

Build size observations:

- Largest JS chunk: LivePlayerView at 399.07 kB, gzip 123.95 kB.
- SettingsView JS: 103.63 kB, gzip 28.43 kB.
- Main index JS: 110.06 kB, gzip 33.08 kB.
- Main index CSS: 259.73 kB, gzip 34.24 kB.
- PWA precache: 91 entries, 2358.45 KiB.

LCP, INP and CLS limits were not measured with Lighthouse or field instrumentation. The available dev-server paint metrics are healthy but are not a substitute for production Lighthouse or Web Vitals runs.

## Feature parity result

The productive routes listed in .hermes/streamvault-feature-parity-map.md remain present in app/frontend/src/router/index.ts:

- /, /streamers, /streamers/:id, /videos, /videos/:id, /live/:streamer, /subscriptions, /settings, /admin, /add-streamer, /add-streamer/manual, /add-streamer/import, /auth/setup, /welcome, /onboarding, /auth/login and /streamer/:streamerId/stream/:streamId/watch.
- Notification Center remains reachable from the shell and exposes a dialog with empty state and close behavior.
- PWA and push user flows remain in Settings, while push and notification test actions are available in Admin Diagnostics.
- Admin advanced diagnostic groups are disclosed behind collapsed controls instead of a default debug wall.

## Risks and follow-up recommendations

1. Run a Playwright or manual device viewport matrix for 390, 430, 768, 1024, 1200 and 1440 before final merge if strict acceptance coverage is required.
2. Run Lighthouse or Web Vitals instrumentation for LCP, INP and CLS against a production preview with backend or realistic fixtures.
3. Decide whether the useWebSocket dynamic import warning is acceptable or should be cleaned up in a follow-up performance task.
4. Update Browserslist data in a separate maintenance task if CI permits dependency metadata updates.
5. Keep the existing no-explicit-any ESLint warnings as known pre-existing debt unless a type-safety task is opened.
