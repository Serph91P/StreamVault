# StreamVault Frontend Overhaul Analysis

Date: 2026-07-05
Branch: feat/frontend-overhaul-plan
Base: origin/develop at 7b493add5137de672818db533c8033356b3cad06
Frontend path: app/frontend

## 1. Kurzueberblick StreamVault Frontend

StreamVault uses a Vue 3, TypeScript, Vite, Pinia, Vue Router, SCSS, VitePWA, Workbox and hls.js frontend. The app covers Twitch streamer management, live status, recordings, videos, admin, settings, auth, onboarding, notification surfaces and PWA helpers.

Graphify context was read first from the existing graph at `/opt/data/workspace/github_repos/StreamVault/graphify-out/graph.json`. The graph contains 5,781 nodes and 11,046 edges. Direct Graphify query for the requested frontend terms returned only broad dependency nodes, so I inspected Graphify graph vocabulary directly and verified every important finding against source files in the clean develop worktree.

Important Graphify hits:

- `app/frontend/src/App.vue` is a large central node with notification, mobile menu, WebSocket and layout state.
- `app/frontend/src/composables/useWebSocket.ts` owns a singleton WebSocket manager.
- `app/frontend/src/composables/usePWA.ts`, `app/frontend/src/main.ts`, `app/frontend/public/registerSW.js`, `app/frontend/public/sw.js` and `app/frontend/public/push-sw.js` form multiple PWA and service worker paths.
- `app/routes/push.py`, `app/services/notifications/push_notification_service.py`, `app/services/notifications/notification_dispatcher.py` and `app/services/notifications/external_notification_service.py` show backend separation between Web Push and Apprise, but the frontend does not yet consume one canonical event schema.

## 2. Aktuelle Frontend-Architektur

The architecture is currently hybrid and partially centralized:

- Entry: `app/frontend/src/main.ts` initializes SCSS, Pinia, router, theme, ripple directive, PWA registration, install prompt handling and auth keepalive.
- App shell: `app/frontend/src/App.vue` contains global SVG sprite, header, mobile menu, notifications, queue monitor, theme toggle, WebSocket message processing and notification storage.
- Routing: `app/frontend/src/router/index.ts` lazy loads views and performs setup, welcome and auth checks in `beforeEach`.
- Navigation: `useNavigation.ts`, `NavigationWrapper.vue`, `SidebarNav.vue` and `BottomNav.vue` provide desktop sidebar and mobile bottom navigation.
- Data: most domain state lives in composables and component-local refs. Pinia exists but only has `stores/counter.ts`, so it is effectively unused for product state.
- API: `services/api.ts` and `services/api-real.ts` exist as service layers, but many components still call `fetch` directly.
- Realtime: `useWebSocket.ts` exposes a shared message array and connection status. Multiple views and composables watch only the latest message.
- Notifications: App.vue processes selected WebSocket messages and stores a 100 item in-app history in localStorage. `NotificationFeed.vue` reads from that storage.

Large files that indicate refactor pressure:

| File | Lines | Risk |
| --- | ---: | --- |
| `styles/_components.scss` | 2521 | global UI rules too broad |
| `components/StreamList.vue` | 1774 | oversized component |
| `components/VideoPlayer.vue` | 1740 | oversized player component |
| `components/admin/AdminPanel.vue` | 1525 | admin/debug density |
| `views/SettingsView.vue` | 1362 | settings wall risk |
| `App.vue` | 1324 | app shell plus domain logic |
| `views/StreamerDetailView.vue` | 1320 | detail page too broad |
| `views/VideoPlayerView.vue` | 1243 | player page complexity |
| `views/LivePlayerView.vue` | 1182 | HLS and mobile complexity |
| `components/NotificationFeed.vue` | 1118 | notification state/UI coupled |

## 3. Aktuelle UI/UX-Probleme

Main issues:

- The product surface feels like a mixture of polished glass UI, admin dashboard widgets, test panels and debug utilities.
- Notification Center is implemented as a panel over localStorage, not as a durable product area with canonical read/unread, filtering, actions and deep links.
- Settings mixes user settings, PWA controls, notification tests, Apprise and diagnostics.
- Admin and debug surfaces leak into product concepts via components like `WebSocketMonitor.vue`, `NotificationsDashboard.vue`, `PWATester.vue`, `pwa-test.html` and many test buttons.
- Empty, loading and error states exist in some places (`EmptyState.vue`, `LoadingSkeleton.vue`) but are not consistently enforced across all pages.
- Buttons, cards, panels and badges are implemented via global classes, base components and ad hoc scoped styles at the same time.
- The UI direction is dark and glass-heavy. It can work for StreamVault, but it needs a calmer media/recording center identity and less glass everywhere.

## 4. Aktuelles Design-System / Token-System

Existing design foundations:

- `_variables.scss` defines color palettes, semantic colors, Twitch colors, type scale, spacing, radius, shadows, breakpoints, transitions and CSS custom property aliases.
- `main.scss` imports `glass-system`, `animations`, `layout`, `components`, `views`, `utilities`, `tables` and `settings-panels`.
- Base components exist: `BaseButton.vue`, `BaseInput.vue`, `BaseDropdown.vue`, `BaseList.vue`, `BaseModal.vue`.
- Card components exist: `GlassCard.vue`, `StatusCard.vue`, `StreamCard.vue`, `StreamerCard.vue`, `VideoCard.vue`.

Problems:

- 211 CSS custom properties were detected, with multiple duplicate or compatibility aliases such as `--primary-color`, `--primary-hover`, `--primary-hover-color`, `--color-primary`, `--text-color`, `--color-text`, `--danger-color`, `--error-color` and similar.
- `_variables.scss` has compatibility aliases for old token names, which is useful short term but preserves drift.
- Global `button:not(.unstyled)` styles in `main.scss` compete with `BaseButton.vue` and component-scoped button classes.
- `GlassCard.vue` exists but many views still use local card classes instead of shared card primitives.
- The build reports a CSS warning: `.theme-menu-item :deep(.icon-btn)` is not recognized by Lightning CSS, suggesting invalid deep selector usage.

## 5. Aktuelle Komponentenlandschaft

Central components:

- Navigation: `NavigationWrapper.vue`, `SidebarNav.vue`, `BottomNav.vue`
- App shell adjuncts: `NotificationFeed.vue`, `BackgroundQueueMonitor.vue`, `PWAInstallPrompt.vue`, `ThemeToggle.vue`, `ToastContainer.vue`
- Domain cards: `StreamerCard.vue`, `StreamCard.vue`, `VideoCard.vue`, `StatusCard.vue`
- Player: `VideoPlayer.vue`, `VideoPlayerView.vue`, `LivePlayerView.vue`, `VideoModal.vue`, `VideoTabs.vue`
- Settings panels: `NotificationSettingsPanel.vue`, `PWAPanel.vue`, `RecordingSettingsPanel.vue`, `ProxySettingsPanel.vue`, `TwitchConnectionPanel.vue`, `ApiKeysPanel.vue`, `LoggingPanel.vue`, `FavoritesSettingsPanel.vue`
- Admin: `AdminPanel.vue`, `BackgroundQueueAdmin.vue`, `PostProcessingManagement.vue`

Redundant or risky patterns:

- Buttons: 514 `btn` occurrences across 41 Vue files plus base button and many custom button classes.
- Cards: 354 `card` occurrences across 44 Vue files plus `GlassCard`, `StatusCard` and domain cards.
- Badges: 106 `badge` occurrences across 20 files.
- Modals and panels are split between base modal, glass popup patterns and custom scoped implementations.
- Inline emoji icon components in `NotificationsDashboard.vue` conflict with the global SVG sprite and FontAwesome.
- App.vue embeds a global SVG sprite with many symbols, while the project also ships `public/icons.svg`, FontAwesome and icon components.

## 6. Aktuelle Navigation Desktop

Desktop navigation uses `SidebarNav.vue` inside `NavigationWrapper.vue`:

- Fixed sidebar below a fixed header.
- Collapsible desktop sidebar state persisted in localStorage via `sidebar-expanded`.
- Main content margin changes between 272px and 96px.
- Navigation tabs are defined in `useNavigation.ts`: Home, Streamers, Videos, Subs, Settings.

Issues:

- Admin is routable but not part of primary navigation.
- Live player, active recordings, jobs and notifications are global surfaces rather than clear navigation destinations.
- Sidebar state is localStorage based and is fine as preference, but the navigation config is a mutable exported array with badge mutation.
- Header logic remains in App.vue rather than a clear AppShell component.

## 7. Aktuelle Navigation Mobile/PWA

Mobile uses `BottomNav.vue` with five tabs and safe area padding. It has 44px minimum touch targets and haptic feedback via `navigator.vibrate(10)`.

Good points:

- Bottom navigation exists.
- `NavigationWrapper.vue` uses `100dvh` and safe area bottom padding.
- Horizontal overflow fixes already exist.

Issues:

- App.vue still has a separate hamburger mobile menu with Jobs, Notifications and Logout, so mobile navigation is split between bottom tabs and header menu.
- Notification Center is opened as a popup panel, not a mobile sheet with product-level behavior.
- PWA install and push flows live in settings and prompt components, not in a coherent onboarding/status flow.
- There is no clear mobile-first route for active recordings or background jobs.

## 8. Aktueller PWA-/Service-Worker-Stand

Current service worker paths:

- `main.ts` calls `registerSW` from `virtual:pwa-register`.
- `index.html` also loads `/registerSW.js`.
- `public/registerSW.js` manually registers `/sw.js`.
- `usePWA.ts` manually registers `/sw.js` again.
- `vite.config.ts` uses VitePWA `generateSW` with `registerType: autoUpdate`.
- Backend `app/main.py` serves `/registerSW.js`, `/pwa-test.html`, `/pwa/push-sw.js`, and injects `importScripts('/pwa/push-sw.js')` into generated service worker output in one route path.
- `public/sw.js` is a generated Workbox file committed under public.
- `public/push-sw.js` contains custom `push` and `notificationclick` handlers.

Conclusion: there are multiple registration and service-worker delivery paths. The desired final state should have one registration strategy and one source of truth for push handlers. The current state is functional enough to build, but architecturally fragile.

## 9. Aktueller Push-Notification-Stand

Frontend:

- `usePWA.ts` checks `PushManager`, requests permission, gets VAPID public key from `/api/push/vapid-public-key`, subscribes via `pushManager.subscribe`, posts subscription to `/api/push/subscribe`, supports unsubscribe and local `showNotification`.
- Permission is requested directly inside `subscribeToPush`, so UX needs more explanation and a deliberate user action.
- `PWAPanel.vue` surfaces push support and subscription actions.

Backend:

- `app/routes/push.py` implements VAPID key, subscribe, unsubscribe, test and debug endpoints.
- `PushSubscription` model exists.
- `PushNotificationService` sends browser push notifications through `enhanced_push_service`, handles stream events and deactivates expired subscriptions on recognizable errors.

Gaps:

- No single typed frontend notification event contract.
- Push payloads and WebSocket notification data are related but not unified.
- notificationclick has target routing support through `data.internal_url || data.url || '/'`, but app-side message handling must remain verified.
- iOS Home Screen and Android Chrome flows are not documented as tested.

## 10. Aktueller WebSocket-/Realtime-Stand

Frontend:

- `useWebSocket.ts` uses a singleton WebSocket manager with one connection shared across subscribers.
- It stores a reactive `messages` array and keeps only the last 100 messages.
- It reconnects with exponential backoff and jitter up to 10 attempts, then cooldown retry.
- It skips auth routes and redirects to login for close codes 4001 or 4003.
- Multiple consumers watch `messages` and process only `newMessages[newMessages.length - 1]`.

Backend:

- `/ws` endpoint accepts and keeps the connection open.
- `ConnectionManager` broadcasts messages and exposes methods for active recordings, recording started, recording stopped, queue stats and more.
- `websocket_broadcast_task.py` periodically broadcasts active recordings and background queue status as fallback updates.

Gaps:

- There is no central realtime Pinia store.
- No typed event union is shared across consumers.
- No event id, cursor, replay or since endpoint was found in the frontend path.
- The 100 message list is not a reliable event source.
- Duplicate and missing events are handled locally and inconsistently by consumers.

## 11. Aktueller Notification-State-Stand

Current in-app notification state:

- App.vue keeps `showNotifications`, `unreadCount`, `notificationCount` and `lastReadTimestamp`.
- App.vue stores notifications in localStorage key `streamvault_notifications` and read timestamp in `lastReadTimestamp`.
- `NotificationFeed.vue` explicitly says it only reads from localStorage and relies on App.vue for WebSocket processing.
- A custom browser event `notificationsUpdated` notifies the feed after localStorage writes.
- Backend notification state is partially queried through `notificationApi.getNotificationState()` and clear operations, but localStorage remains the primary in-app history store.

Problems:

- Read/unread state is timestamp based, not per notification.
- Dedupe is heuristic by type, streamer and time window.
- IDs are generated from `test_id` or random timestamp, not stable event IDs.
- `recording_started` backend events and `recording.started` App.vue history types are naming mismatched.
- LocalStorage is acting as a domain database.

## 12. Apprise vs Web Push vs WebSocket: aktuelle Trennung

Backend separation exists but the frontend does not reflect it cleanly:

- WebSocket: active sessions and UI realtime via `NotificationDispatcher._send_websocket_notification` and `ConnectionManager`.
- Web Push: browser subscribers via `PushNotificationService` and `/api/push/*`.
- Apprise: external channels via `ExternalNotificationService` and `apprise.async_notify`.

Current dispatcher order for stream notifications:

1. Check notification settings.
2. Send WebSocket notification.
3. Send Web Push notifications.
4. Send Apprise external notification.

Needed improvement:

Backend and frontend should agree on a canonical event schema with fields like `event_id`, `type`, `severity`, `title`, `body`, `streamer_id`, `streamer_name`, `recording_id`, `video_id`, `target_url`, `created_at`, `dedupe_key`, `source`, `actions` and read state where supported.

## 13. Alte Tests, Debugseiten und Experimente

Likely debug or experiment paths:

- `app/frontend/src/views/PWATester.vue`
- `app/frontend/public/pwa-test.html`
- `app/frontend/public/pwa-helper.js`
- `app/frontend/public/registerSW.js`
- `app/frontend/public/sw.js` as generated Workbox artifact
- `app/frontend/src/utils/pwaDebug.ts`, imported unconditionally via dynamic import from `main.ts`, despite comment saying development only
- `app/frontend/src/components/WebSocketMonitor.vue`
- `app/frontend/src/components/NotificationsDashboard.vue`
- Test actions inside `NotificationSettingsPanel.vue`, `PWAPanel.vue` and push routes
- `src/mocks/mockData.ts` and `VITE_USE_MOCK_DATA` are useful for dev, but should remain clearly dev-only

Do not delete these blindly. First decide which belong in Admin Diagnostics, which are dev-only, and which should be removed.

## 14. Doppelte oder unnoetige UI-/PWA-/Notification-Logik

Duplicated areas:

- Service worker registration: VitePWA virtual register, index.html `/registerSW.js`, public registerSW, usePWA manual register.
- PWA install prompt: main.ts event, `usePWA.ts`, `PWAInstallPrompt.vue`, `pwa-helper.js`.
- Notifications: App.vue history storage, NotificationFeed localStorage reader, NotificationsDashboard status/event UI, settings notification test flows.
- WebSocket consumers: many views and composables watch latest message separately.
- Icons: App.vue SVG sprite, public icons.svg, FontAwesome, inline emoji icon templates.
- Buttons and cards: base components plus ad hoc global/scoped class systems.
- Storage: localStorage keys are scattered across auth, theme, navigation, PWA dismissals, live codec preference and notification history.

## 15. Risiken bei einem Overhaul

High risks:

- PWA push may regress if registration strategy changes without testing on built output and backend-served paths.
- WebSocket event name mismatch can silently drop notification history or status updates.
- Removing debug/test routes without product decision may remove useful admin diagnostics.
- CSS consolidation can break large scoped styles or global class dependencies.
- App.vue refactor touches layout, notification, queue and auth-adjacent behavior at once.
- Notification persistence choice may require backend additions.
- Event replay/since cannot be safely implemented in frontend if backend does not expose a cursor endpoint.

## 16. Priorisierte Verbesserungsvorschlaege

1. Freeze baseline checks and keep them green: `npm run lint:tokens`, `npm run type-check`, `npm run build-only`.
2. Define canonical `NotificationEvent` and `RealtimeEvent` TypeScript types before moving UI.
3. Introduce a central realtime store/composable that owns WebSocket connection, typed messages, dedupe, connection status and future replay integration.
4. Introduce a notification store with storage abstraction, read/unread model and target URLs.
5. Split App.vue into AppShell, AppHeader, GlobalNotificationCenter, GlobalQueueMonitor and icon strategy.
6. Choose one service worker strategy. Recommended: VitePWA `injectManifest` with `src/sw.ts` if custom push logic remains first class. Alternative: keep `generateSW` but configure importScripts explicitly and remove manual registrations.
7. Move PWA diagnostics and WebSocket monitor to Admin Diagnostics or dev-only routes.
8. Consolidate tokens by choosing canonical names and deprecating compatibility aliases gradually.
9. Promote `BaseButton`, `BaseModal`, `GlassCard` or a calmer `SurfaceCard`, status badges and table/list primitives as the only supported UI layer.
10. Redesign core pages after design-system primitives exist, not before.

## 17. Empfohlene Subagenten-Aufteilung

Use these roles and keep them on separate Kanban lanes:

1. Graphify & Architecture Analyst
   - Owns Graphify graph interpretation, frontend dependency map, risky flows and backend event references.
2. UI/UX Product Designer Agent
   - Owns target app model, page purpose, desktop and mobile IA, empty/loading/error states.
3. Design System Agent
   - Owns tokens, SCSS structure, primitives, icon system and accessibility defaults.
4. Vue Frontend Architecture Agent
   - Owns App.vue split, stores, composables, services, TypeScript typing and localStorage cleanup.
5. Realtime/WebSocket Agent
   - Owns realtime store, event types, reconnect, dedupe, visibility and replay task discovery.
6. PWA/Web Push Agent
   - Owns service worker strategy, push subscription lifecycle, permission UX, notificationclick and mobile caveats.
7. Mobile & Accessibility Agent
   - Owns touch targets, safe areas, keyboard navigation, focus, reduced motion and mobile sheets.
8. QA/Test Agent
   - Owns test matrix, build/typecheck/design-token checks and manual PWA/WebSocket cases.
9. Integration Reviewer Agent
   - Owns diff consistency, conflict detection and release readiness.

## Baseline checks

Commands run in `/opt/data/workspace/github_repos/StreamVault-frontend-overhaul/app/frontend`:

| Command | Result | Notes |
| --- | --- | --- |
| `npm ci` | Pass | 598 packages installed. Warnings about Vite 8 peer ranges in vite-plugin-vue-devtools dependency tree. npm audit reports 2 vulnerabilities, 1 low and 1 moderate. |
| `npm run lint:tokens` | Pass | `design-token lint: no violations` |
| `npm run type-check` | Pass | `vue-tsc --build` completed successfully |
| `npm run build-only` | Pass | Vite build completed in 3.21s, PWA generateSW emitted `dist/sw.js` and `dist/workbox-dcde9eb3.js` |

Build warnings to track:

- Lightning CSS warning for `.theme-menu-item :deep(.icon-btn)`.
- Rolldown invalid pure annotation warnings from `@vueuse/core`.
- Ineffective dynamic import: `useWebSocket.ts` is dynamically imported by `useAuth.ts` but statically imported elsewhere.
- Plugin timings show CSS 64 percent and Vue 29 percent.
- Browserslist data is 6 months old.

## Hermes Kanban status

The prompt requires real Hermes Kanban tasks. I checked this environment and `hermes` is not available in PATH, so I could not create real Hermes Kanban cards from this session yet. This is a tooling blocker, not a product blocker.

Next required action before Phase 3:

- Expose the Hermes CLI or Kanban tool in this session, or provide the exact command/API available here for `kanban_create` and dependency links.
- Then create Epics 1 to 10 as real Kanban tasks with parent links and assign them to the discovered profiles.

Until that is available, this report is the durable Phase 1 artifact requested by the prompt.
