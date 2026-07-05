# StreamVault frontend overhaul summary

Date: 2026-07-05
Branch: feat/frontend-overhaul-plan
Commit: 3c2a212e feat: overhaul StreamVault frontend
PR: https://github.com/Serph91P/StreamVault/pull/700
Base: develop

## What Graphify taught us

Graphify from the sibling StreamVault checkout identified these central areas before implementation:

- App.vue was a hotspot for app shell, notifications, WebSocket processing, mobile menu, queue and theme logic.
- NotificationFeed.vue contained many local helper nodes and storage behavior.
- useWebSocket.ts was the frontend singleton connection owner.
- Backend ConnectionManager and websocket_endpoint owned live WebSocket behavior.
- PWA files showed overlapping service worker paths.

Direct Graphify query was broad, so every important claim was source verified.

## UX methods applied

- Nielsen heuristic evaluation for central pages and flows.
- Jobs to be Done for monitoring, recording, playback, errors, notifications, PWA and settings.
- Journey mapping for setup, dashboard, adding streamers, recordings, videos, notifications, mobile PWA, failure recovery and settings.
- Task flow design for core flows including entry, intent, feedback, errors, exits, success and mobile variant.
- Information architecture for primary navigation, global actions, context routes, settings and diagnostics.
- Progressive disclosure for settings, diagnostics, queue, notification and PWA flows.
- Recognition over recall with labels, badges, filters, empty states and target actions.
- Mobile first and PWA first checks for bottom navigation, sheets, safe area and push permission.
- WCAG 2.2 AA target review for semantics, focus, labels, contrast, reduced motion and status text.
- Performance UX review for route lazy loading, skeletons, centralized realtime and player isolation.
- Design critique against clarity, main action, error recovery, mobile thumb use and visual calm.

## Old UX problems

- Product UI mixed dashboard, debug utilities and test pages.
- App.vue was too large and owned domain behavior.
- Notification history was localStorage first and timestamp based.
- PWA registration had multiple owners.
- Settings mixed basic user configuration and diagnostics.
- Mobile had bottom nav plus extra hamburger model.
- Status language depended too much on scattered badges and colors.
- Debug artifacts existed in public and product facing paths.

## New product target

StreamVault is now shaped as a dark first, status first, self-hosted recording control center. It combines media library behavior, monitoring dashboard behavior and mobile PWA behavior while keeping diagnostics available but separated.

## New information architecture

Primary destinations:

1. Dashboard
2. Streamers
3. Library
4. Subscriptions
5. Settings

Global utilities:

- Notifications
- Queue
- PWA update or install
- Theme
- Account

Context routes:

- Streamer detail
- Add streamer
- Live player
- Video player
- Setup and auth
- Admin Diagnostics

## Design system

Defined and implemented base rules for:

- Semantic tokens and SCSS ownership.
- Shared panels, sheets, tables, forms, status badges and surface cards.
- Internal SVG icon system through IconSprite and SvgIcon.
- Status language for live, recording, queued, processing, failed, completed, offline and reconnecting.
- Mobile, accessibility and performance rules.

## App shell and navigation

- App.vue was reduced to global orchestration.
- AppShell and AppHeader own product shell behavior.
- Notification and realtime toast logic moved out of App.vue.
- Desktop and mobile share five primary destinations.
- Old competing mobile hamburger pattern was removed.
- Queue and notifications are header utilities and mobile friendly panels.

## Views changed

- Dashboard/Home redesigned around system status.
- Streamers gained status first scanning, filters and realtime reconciliation.
- Streamer Detail became a cockpit style view.
- Videos and players gained clearer status and error components.
- Settings was grouped and diagnostics separated.
- Admin keeps raw diagnostics and channel tests.
- Auth and onboarding remain full screen flows.

## Components replaced or added

Added or rebuilt:

- BasePanel
- BaseSheet
- BaseTable
- FormField
- StatusBadge
- SurfaceCard
- IconSprite
- SvgIcon
- NotificationFilters
- NotificationItem
- NotificationState
- PlayerStatus
- PlayerError
- Notification store and realtime store

Removed:

- NotificationsDashboard.vue
- PWATester.vue
- public sw.js
- public registerSW.js
- public pwa-test.html
- public pwa-helper.js
- public FontAwesome assets
- public icons.svg

## Store and service changes

- Added realtime Pinia store.
- Added notification Pinia store.
- Added typed event contracts.
- Added storage service.
- Added notificationStorage service with legacy migration.
- Extended WebSocket manager with direct listener support.
- Added backend replay endpoint and tests.

## Notification and realtime changes

- Central typed realtime events replace scattered latest-message handling where implemented.
- Notification Center supports filters, severity, read state, target navigation, empty state and error state.
- Notification dedupe uses event_id and dedupe_key where possible.
- Backend replay supports reconnect gap recovery with bounded in-memory events.

## PWA and push changes

- VitePWA is the single frontend registration strategy.
- usePWA resolves existing registration instead of manually registering /sw.js.
- Public generated service worker and duplicate manual register script removed.
- Push permission requires explicit user action.
- Subscription sync is safer and does not delete browser subscription on server sync failure.
- notificationclick prefers target_url and legacy route normalization.

## Performance improvements

- Routes remain lazy loaded.
- Realtime event processing centralized.
- Skeleton and state components added or reused.
- Player status and error presentation isolated.
- Heavy live and player routes remain candidates for further splitting.
- Build output and chunk sizes documented in QA.

## Accessibility improvements

- Status components include text, not only color.
- Sheet and panel controls use real buttons.
- Settings fields move toward labeled FormField usage.
- Error states provide recovery text.
- Motion and focus rules are part of the design system.
- Full external WCAG audit remains a recommended follow-up.

## Feature parity result

Product routes and functions were preserved. Removed files are debug, generated artifact or orphan asset paths. Admin Diagnostics retains raw test and diagnostic capabilities. The parity map lists every productive surface and its target position.

## Checks

- npm run lint -- --max-warnings=9999
- npm run lint:tokens
- npm run type-check
- npm run build-only
- uv run --with-requirements requirements.txt --with pytest pytest -q tests/test_websocket_replay.py
- uv tool run ruff format --check on changed Python files
- uv tool run ruff check on changed Python files
- git diff --check
- GitHub PR #700 CI status checks all SUCCESS

## Open risks

- Android and iOS installed PWA push require real device QA.
- Full browser visual regression was not captured here.
- Existing no-explicit-any warnings remain and should be reduced incrementally.
- Full axe and screen reader pass is still recommended.
- Live backend WebSocket smoke with authenticated browser session should be run after deploy or in a staging environment.

## Next useful PRs

1. Split VideoPlayer into smaller HLS service, controls and presentation modules.
2. Add typed streamer, video, recording and settings stores.
3. Reduce no-explicit-any warnings in API services and legacy views.
4. Add browser based smoke tests for dashboard, streamers, settings and notification center.
5. Add real device PWA push QA checklist results to docs.
