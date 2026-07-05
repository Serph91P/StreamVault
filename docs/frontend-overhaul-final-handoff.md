# StreamVault frontend overhaul final handoff

Date: 2026-07-05
Branch: feat/frontend-overhaul-plan
Base branch: develop
Frontend path: app/frontend
Kanban scope: KAN-001 to KAN-028 plus backend follow-up t_c1c0daa6

## Executive summary

The frontend overhaul branch is implementation-complete for the planned Kanban scope and passed final integration review. The work moved StreamVault toward a dark-first recording control center with clearer navigation, reusable UI primitives, typed realtime and notification flows, consolidated PWA registration, better push permission UX, a product Notification Center, and documented QA limits.

The final integrated checks passed:

- Frontend: `npm run lint:tokens && npm run type-check && npm run build-only`
- Backend focused replay test: `uv run --with-requirements requirements.txt --with pytest pytest -q tests/test_websocket_replay.py`
- Diff hygiene: `git diff --check`
- Diff-only unicode dash scan for added frontend, backend, docs and tests lines

Remaining release risks are external validation items, not known local build blockers. Android and iOS push behavior still needs real device QA. Backend-integrated live WebSocket smoke needs an authenticated backend session. Existing build warnings remain documented.

## Source base and Graphify learnings

Sources used before and during the work:

- `docs/frontend-overhaul-analysis.md`
- `docs/frontend-overhaul-product-ux-plan.md`
- `docs/frontend-overhaul-token-scss-plan.md`
- `docs/frontend-overhaul-manual-qa-matrix.md`
- Kanban task handoffs KAN-001 to KAN-027
- Live source files in the existing worktree

Graphify orientation came from `/opt/data/workspace/github_repos/StreamVault/graphify-out/graph.json`, not from this worktree. It contained 5,781 nodes and 11,046 edges. Direct Graphify queries were broad, so every important finding was verified against source before changes.

Key verified Graphify and source findings:

- `app/frontend/src/App.vue` was a central hotspot for layout, icons, notifications, WebSocket processing, queue mounts, theme and mobile menu state.
- `app/frontend/src/composables/useWebSocket.ts` owned the singleton WebSocket manager and a capped message list.
- Realtime consumers across composables and views watched the latest raw message independently.
- PWA logic had multiple registration paths: VitePWA in `main.ts`, manual public registration, manual `usePWA.ts` registration and backend service worker routes.
- Notification state was split across App.vue, localStorage, browser events, backend state calls, WebSocket payloads and push payloads.
- Debug and experiment surfaces existed in normal or public paths, including PWA tester files, a notification dashboard experiment and public service worker artifacts.

## Problems addressed

The overhaul targeted these problems from the analysis:

- Mixed product identity with polished UI, admin diagnostics, debug utilities and test pages sharing surfaces.
- Large central files and components, especially App.vue, NotificationFeed.vue, VideoPlayer.vue, StreamerDetailView.vue and global SCSS.
- Inconsistent design primitives for buttons, panels, cards, tables, badges, sheets and forms.
- Multiple icon systems through inline SVG, public SVG, FontAwesome and emoji style components.
- Duplicate service worker registration and generated worker files committed under public assets.
- Push permission requested too directly and without a clear explanation flow.
- Notification history stored as localStorage records with heuristic dedupe and timestamp-only read state.
- Realtime updates consumed as raw latest WebSocket messages without central projection, dedupe or replay.
- LocalStorage and sessionStorage accessed directly across many domains.
- Manual mobile push and live backend behaviors not testable in the local worker environment.

## Product and UX decisions

The product model now follows the plan in `docs/frontend-overhaul-product-ux-plan.md`:

- StreamVault should feel like a modern self-hosted media and recording control center, not a generic admin dashboard.
- Primary navigation remains five destinations on desktop and mobile: Dashboard, Streamers, Library, Subscriptions and Settings.
- Home product copy moved to Dashboard, and Videos product copy moved to Library while route compatibility remains.
- Streamer detail, live player, video player and add streamer stay route-backed context surfaces for deep links.
- Notifications and Queue are global utilities opened from header actions and mobile-friendly panels or sheets, not primary tabs.
- Admin Diagnostics stays outside normal navigation and owns WebSocket monitor, push tests, raw diagnostics and queue internals.
- Settings is user-facing configuration. Diagnostic test actions moved to Admin Diagnostics.
- Push permission is requested only after explanation and user intent.
- Mobile uses bottom navigation for the five primary destinations and sheets or panels for temporary global surfaces.

## Design system and component changes

Design system work completed:

- Added `docs/frontend-overhaul-token-scss-plan.md` with canonical token groups and SCSS ownership.
- Marked `_variables.scss`, `_glass-system.scss`, `main.scss` and `_components.scss` with ownership boundaries.
- Added base primitives:
  - `BasePanel.vue`
  - `BaseSheet.vue`
  - `BaseTable.vue`
  - `FormField.vue`
  - `StatusBadge.vue`
- Added card primitive:
  - `SurfaceCard.vue`
- Added primitive exports and guidance in `components/base/index.ts`, `components/cards/index.ts` and `components/base/README.md`.
- Moved App.vue inline sprite into `components/icons/IconSprite.vue`.
- Added `components/icons/SvgIcon.vue` as the canonical icon renderer.
- Removed FontAwesome from `package.json` and `package-lock.json`.
- Removed public `icons.svg` and converted relevant icon usage to the internal sprite policy.
- Added accessibility improvements for sheet close targets, focus states, live and video player controls, settings actions and notification dialog focus handling.

## App shell, navigation and page changes

App shell and navigation:

- `App.vue` was reduced to orchestration of icon sprite, app shell, auth route rendering, PWA install prompt, toasts, theme init and global realtime banner behavior.
- New app shell components were introduced under `app/frontend/src/components/app/`:
  - `AppShell.vue`
  - `AppHeader.vue`
  - `AppNotificationCenter.vue`
  - `useAppNotifications.ts`
  - `useAppRealtimeToasts.ts`
- The old competing mobile hamburger pattern was removed. Jobs, Notifications, Theme and Logout are direct header actions.
- Background jobs trigger is a real button with an aria label and mobile touch target.
- Navigation labels are Dashboard, Streamers, Library, Subscriptions and Settings.

Core pages and flows:

- Dashboard/Home now presents live streamers, active recordings, latest videos, queue, failures and realtime activity as an operational overview.
- Streamers overview gained recording-aware filtering and realtime reconciliation.
- Streamer detail became a cockpit with Overview, Videos, Recording Settings and Events tabs.
- Video and live player states gained shared status and error components.
- Video cards use shared status primitives for recording, processing and failed markers.
- Settings and Admin were separated so user-facing panels no longer carry raw Apprise, WebSocket or push diagnostic tests.
- Admin keeps diagnostics and channel test cards for Apprise, Web Push and WebSocket.

## Realtime and backend replay changes

Frontend realtime changes:

- Added typed realtime and notification event helpers in `app/frontend/src/types/events.ts`.
- Added central Pinia realtime store in `app/frontend/src/stores/realtime.ts`.
- Kept `useWebSocket.ts` as the singleton connection owner but added direct listener support for reliable dispatch.
- Migrated scattered latest-message consumers to store subscriptions.
- Added online/offline handling, visible-tab reconnect trigger, retry state and `reconnectNow()`.
- Added short-window duplicate live event suppression by event id, dedupe key or timestamp identity.
- Added an app-level realtime reconnect/offline banner with retry action.

Backend replay follow-up completed:

- `app/services/communication/websocket_manager.py` now assigns monotonic `event_id` cursors to replayable realtime events and stores a bounded in-memory log of the last 500 events.
- Live WebSocket notifications carry the same event id used by replay.
- `app/main.py` exposes authenticated `GET /api/realtime/events?since=<cursor>&limit=<n>` with retention metadata.
- Focused test coverage was added in `tests/test_websocket_replay.py`.

Retention and replay limits:

- Replay is bounded in memory and is intended for reconnect gaps, not long-term audit history.
- Connection status handshake messages are not replayed.
- Frontend dedupe is still required because live and replay streams can overlap.

## Notifications

Notification architecture changes:

- Added canonical notification event shape, severity/source/action types, target URL mapping and adapters in `types/events.ts`.
- App notification records now use `event_id` and `dedupe_key` instead of random IDs and time-window heuristics where the event provides enough data.
- Added `app/frontend/src/services/notificationStorage.ts` to encapsulate `streamvault_notifications` and migrate legacy `lastReadTimestamp` into per-notification read state.
- Added `app/frontend/src/stores/notifications.ts` for sorted and filtered notifications, unread count, total count, dedupe, mark read, mark unread, remove and clear actions.
- Rebuilt `NotificationFeed.vue` as a composed Notification Center shell with:
  - `NotificationFilters.vue`
  - `NotificationItem.vue`
  - `NotificationState.vue`
- Product Notification Center supports unread filtering, severity filters, event type filters, target navigation, dismiss, read and unread actions, empty state, filtered empty state, loading state and error state.
- Push notification clicks and in-app notification clicks prefer canonical `target_url` and normalize legacy `/streamer/:id` targets to `/streamers/:id`.

Known notification caveat:

- Backend still needs consistent stable `event_id` and `dedupe_key` on every channel for perfect cross-channel dedupe. The frontend adapter derives safe values for known legacy shapes and rejects incomplete future `notification_event` payloads.

## PWA and Web Push

PWA changes:

- Consolidated on VitePWA `generateSW` and `virtual:pwa-register` as the single app registration strategy.
- Removed duplicate frontend `/registerSW.js` loading and public manual service worker registration paths.
- Removed committed generated public service worker artifacts and stale FontAwesome public assets.
- `usePWA.ts` now reads the existing VitePWA registration with `getRegistration('/')` or `navigator.serviceWorker.ready` instead of manually registering `/sw.js`.
- `public/push-sw.js` remains the custom push and notification click handler path included by the generated worker strategy.
- Backend service worker compatibility routes were simplified so stale manual registration does not remain the main strategy.

Push permission and subscription lifecycle:

- `subscribeToPush()` no longer requests notification permission by itself. It requires granted permission after explicit user action.
- Existing browser subscriptions are detected and re-sent to `/api/push/subscribe` so inactive backend records can be reactivated.
- Old VAPID application server key subscriptions are surfaced as an error and renewed on Retry.
- Server sync failures no longer delete browser subscriptions.
- `showNotification()` no longer triggers the browser permission prompt.
- `PWAPanel.vue` shows explanatory copy, separate permission and subscription states, denied troubleshooting, Retry, Enable, Disable and test actions only after active subscription.

Documented platform limitations:

- Android Chrome installed PWA and browser tab push behavior require real Android validation.
- iOS and iPadOS Web Push require Safari 16.4 or newer and Home Screen installation.
- Unsupported iOS browser tab behavior needs a negative check on device.

## Cleanup and storage changes

Cleanup completed:

- Removed orphan PWA tester and notification dashboard UI.
- Removed standalone PWA test public files.
- Removed backend routes and auth/public handling for those debug files.
- Dev-gated PWA debug import behavior.
- Kept WebSocket monitor as an Admin Diagnostics surface.

Storage and API cleanup:

- Added `app/frontend/src/services/storage.ts` as a central app storage service.
- Migrated raw localStorage and sessionStorage use in frontend source through the wrapper.
- Moved focused REST fallback calls to existing API services.
- Verified no raw `localStorage` or `sessionStorage` property calls remain in `app/frontend/src` outside the wrapper.

## Tests and verification

Final integration review passed with these checks:

- `npm run lint:tokens && npm run type-check && npm run build-only`
  - Result: pass
  - Notable output: `design-token lint: no violations`, `vue-tsc --build` completed, Vite generated `dist/sw.js` and `dist/workbox-dcde9eb3.js`
- `uv run --with-requirements requirements.txt --with pytest pytest -q tests/test_websocket_replay.py`
  - Result: `4 passed in 1.21s`
- `git diff --check`
  - Result: pass, no output
- Diff-only unicode dash scan for added frontend, backend, docs and tests lines
  - Result: pass, no em dash or en dash characters in added diff lines

Additional focused checks run during task implementation included:

- Repeated `npm run lint:tokens`, `npm run type-check`, `npm run build-only` across implementation tasks.
- `uv run --with pytest --with-requirements requirements.txt pytest tests/test_websocket_replay.py tests/test_application_startup.py tests/test_api_routes.py -q`, which passed during backend replay implementation.
- `uv run --with ruff ruff check app/main.py app/services/communication/websocket_manager.py tests/test_websocket_replay.py`, which passed during backend replay implementation.
- Browser smoke in mock mode for Dashboard, Streamers, Library, notification panel and Settings PWA panel.
- Service worker asset and manifest checks in local dev server.
- Source-level PWA registration checks confirming one frontend registration owner.
- Notification, storage and removed debug path source smokes.

Known warnings that remain:

- Lightning CSS warning for `.theme-menu-item :deep(.icon-btn)`.
- Rolldown pure annotation warnings from `@vueuse/core`.
- Static plus dynamic import warning for `useWebSocket.ts` depending on task state.
- Browserslist caniuse-lite data is stale.

## Manual QA outcome

The manual QA report is `docs/frontend-overhaul-manual-qa-matrix.md`.

Passed locally:

- Design-token lint.
- Type check.
- Production build.
- Diff whitespace check.
- Manifest served by Vite dev server.
- Service worker asset served by Vite dev server.
- Desktop Dashboard in mock mode.
- Desktop Streamers in mock mode.
- Desktop Library in mock mode.
- Desktop notification panel rendering.
- Desktop Settings PWA panel rendering.
- Keyboard smoke for exposed primary links, buttons and dialog role.
- Source-level realtime store and notification store checks.

Blocked or not available in this environment:

- Real mobile viewport and installed PWA safe-area checks.
- Android Chrome installed PWA push receive and click.
- Android Chrome browser tab push receive and click.
- iOS or iPadOS Home Screen push receive and click.
- Unsupported iOS browser tab negative check.
- Backend live WebSocket connection, reconnect interruption and queue realtime updates without a running backend service.

## Kanban completion summary

All planned Kanban tasks are done after lead or integration review.

Completed documentation and planning tasks:

- KAN-001 Phase 1 analysis baseline.
- KAN-002 Product UX model.
- KAN-003 Debug and experiment inventory.
- KAN-004 Token and SCSS consolidation plan.
- KAN-025 Baseline and continuous checks.
- KAN-026 Manual QA matrix.
- KAN-027 Integration review.
- KAN-028 Final documentation and handoff.

Completed implementation tasks:

- KAN-005 UI primitive system.
- KAN-006 Icon system consolidation.
- KAN-007 App.vue shell split.
- KAN-008 Desktop and mobile navigation cleanup.
- KAN-009 Dashboard/Home redesign.
- KAN-010 Streamer list and detail redesign.
- KAN-011 Videos and player redesign.
- KAN-012 Settings and Admin cleanup.
- KAN-013 Typed realtime event model.
- KAN-014 Central realtime store.
- KAN-015 Reconnect, dedupe and replay capability check.
- KAN-015 follow-up backend realtime replay endpoint.
- KAN-016 Canonical notification schema.
- KAN-017 Notification store and persistence.
- KAN-018 Product Notification Center.
- KAN-019 Service worker strategy consolidation.
- KAN-020 Push subscription lifecycle and permission UX.
- KAN-021 notificationclick and mobile platform documentation.
- KAN-022 Mobile layout and accessibility pass.
- KAN-023 API, composables and storage cleanup.
- KAN-024 Remove or isolate dead/debug UI paths.

Temporary blocked states during the board were review gates or environment limits:

- Most implementation tasks blocked as `review-required` after local checks, then were accepted by lead or integration review.
- KAN-009 initially timed out, then completed on retry and passed integrated verification.
- KAN-015 created backend replay follow-up task `t_c1c0daa6`, which is now complete.
- Device push, mobile OS and live backend smoke checks remain documented as external QA.

## Review status

Integration review KAN-027 approved the final state. It specifically verified that prior blockers were resolved:

- Stale public service worker source was removed from source control.
- Public manual service worker registration was removed.
- FontAwesome public assets were removed.
- `src/main.ts` owns frontend service worker registration through `virtual:pwa-register`.
- `usePWA.ts` resolves the existing or ready registration for push subscription state and no longer manually registers `/sw.js`.
- Manual QA documentation matches live source.

KAN-027 checks passed:

- `npm run lint:tokens && npm run type-check && npm run build-only`
- `uv run --with-requirements requirements.txt --with pytest pytest -q tests/test_websocket_replay.py`
- `git diff --check`
- Diff-only em/en dash scan for added lines

## Release risks and next steps

Open risks before merge or release:

- Real Android and iOS Web Push validation is still required.
- Backend-integrated live WebSocket reconnect, queue update and notification ingestion smoke is still required with an authenticated backend.
- Static frontend-only preview is not sufficient to prove production push behavior if backend service worker serving differs from Vite dev or preview.
- Existing build warnings should be triaged separately so future warnings are easier to spot.
- Backend notification events should eventually emit stable `event_id` and `dedupe_key` for all channels.
- Replay retention is bounded in memory. If users need durable history across process restarts, this needs database-backed event storage.

Suggested next steps:

1. Run the manual device QA matrix on Android Chrome, Android installed PWA, iOS or iPadOS Home Screen app and unsupported iOS browser tab.
2. Run authenticated backend realtime smoke for `/ws`, `/api/realtime/events`, queue updates and notification ingestion.
3. Open the PR against `develop` with this handoff and `docs/frontend-overhaul-manual-qa-matrix.md` linked in the description.
4. Treat remaining warning cleanup as follow-up tasks unless the PR reviewer requires them before merge.
