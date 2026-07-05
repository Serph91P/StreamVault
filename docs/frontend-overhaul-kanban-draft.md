# StreamVault Frontend Overhaul Kanban Draft

Status: Draft only. Real Hermes Kanban creation is blocked because the `hermes` CLI and Kanban tool are not available in this session PATH.

This file is an import-ready backlog specification. Each task includes title, goal, Graphify/analysis context, affected modules, assignee role, steps, acceptance criteria, tests, risks, dependencies and artifacts.

## Dependency links

- KAN-001 blocks all implementation work.
- KAN-002 blocks KAN-010 to KAN-020.
- KAN-003 blocks KAN-010 to KAN-016.
- KAN-004 blocks KAN-017 to KAN-021.
- KAN-005 blocks KAN-018, KAN-019 and KAN-021.
- KAN-006 blocks KAN-020 and KAN-021.
- KAN-022 to KAN-027 depend on their related implementation tasks.
- KAN-028 depends on all non-blocked implementation tasks.
- KAN-029 depends on KAN-028.

## EPIC 1: Analyse & UX-Produktmodell

### KAN-001: Phase 1 analysis baseline

- Ziel: Preserve the Graphify and source analysis baseline for all agents.
- Kontext: Existing Graphify graph has 5,781 nodes and 11,046 edges. `docs/frontend-overhaul-analysis.md` is the Phase 1 artifact.
- Dateien/Module: `graphify-out/graph.json`, `docs/frontend-overhaul-analysis.md`, `app/frontend/src`.
- Subagent: Graphify & Architecture Analyst.
- Schritte:
  1. Read analysis report.
  2. Verify key source references before using them.
  3. Add missing findings as Kanban comments.
- Akzeptanzkriterien: Every later task links to the analysis report and cites verified files.
- Tests: No code tests. Documentation review only.
- Risiken: Graphify query was broad and needed source verification.
- Abhaengigkeiten: None.
- Artefakte/Diffs: Kanban comments, optional report patch.

### KAN-002: Product UX model

- Ziel: Finalize page model, IA and target user journeys.
- Kontext: `docs/frontend-overhaul-product-ux-plan.md` defines 12 product areas.
- Dateien/Module: `docs/frontend-overhaul-product-ux-plan.md`, router, navigation files.
- Subagent: UI/UX Product Designer Agent.
- Schritte:
  1. Review product areas.
  2. Define primary and secondary navigation.
  3. Decide which surfaces become pages, panels or sheets.
- Akzeptanzkriterien: Dashboard, streamers, detail, videos, live player, settings, admin, notification and PWA flows have final layouts.
- Tests: Design review checklist.
- Risiken: Admin diagnostics may leak into user UX if not separated.
- Abhaengigkeiten: KAN-001.
- Artefakte/Diffs: UX decision note or report patch.

### KAN-003: Debug and experiment inventory

- Ziel: Decide retention, isolation or removal for test/debug paths.
- Kontext: Analysis identified `PWATester.vue`, `pwa-test.html`, `pwa-helper.js`, `WebSocketMonitor.vue`, `NotificationsDashboard.vue` and `pwaDebug.ts`.
- Dateien/Module: `app/frontend/src/views/PWATester.vue`, `app/frontend/public/*`, `app/frontend/src/components/WebSocketMonitor.vue`, `app/frontend/src/utils/pwaDebug.ts`.
- Subagent: Graphify & Architecture Analyst.
- Schritte:
  1. Find all references and routes.
  2. Classify product, admin diagnostics, dev-only or removable.
  3. Block risky deletes for human decision.
- Akzeptanzkriterien: Each debug/test path has a disposition.
- Tests: `npm run type-check`, `npm run build-only` after any route changes.
- Risiken: Removing useful diagnostics without replacement.
- Abhaengigkeiten: KAN-001.
- Artefakte/Diffs: Inventory table and eventual code diffs.

## EPIC 2: Design-System & UI-Grundlagen

### KAN-004: Token and SCSS consolidation plan

- Ziel: Define canonical token names and SCSS ownership.
- Kontext: 211 CSS custom properties detected, many aliases and compatibility names.
- Dateien/Module: `styles/_variables.scss`, `styles/_glass-system.scss`, `styles/main.scss`, `styles/_components.scss`.
- Subagent: Design System Agent.
- Schritte:
  1. Group tokens by color, typography, spacing, radius, elevation and status.
  2. Mark deprecated aliases.
  3. Decide glass usage rules.
- Akzeptanzkriterien: Canonical token list exists and no new aliases are introduced.
- Tests: `npm run lint:tokens`, `npm run build-only`.
- Risiken: Global style regressions across large components.
- Abhaengigkeiten: KAN-001, KAN-002.
- Artefakte/Diffs: Token migration note and SCSS diffs.

### KAN-005: UI primitive system

- Ziel: Unify buttons, forms, cards, panels, tables, badges, modals and sheets.
- Kontext: 514 button occurrences and 354 card occurrences show mixed UI systems.
- Dateien/Module: `components/base/*`, `components/cards/*`, `styles/_components.scss`, `styles/_tables.scss`.
- Subagent: Design System Agent.
- Schritte:
  1. Audit existing base components.
  2. Promote or replace primitives.
  3. Add StatusBadge and SurfaceCard if needed.
- Akzeptanzkriterien: New work uses primitives, not ad hoc classes.
- Tests: `npm run type-check`, `npm run build-only`, visual smoke at 390px and desktop.
- Risiken: Scoped styles depend on old globals.
- Abhaengigkeiten: KAN-004.
- Artefakte/Diffs: Component and style diffs.

### KAN-006: Icon system consolidation

- Ziel: Replace mixed SVG sprite, FontAwesome, icons.svg and emoji components with one policy.
- Kontext: App.vue embeds a large sprite, public icons exist, FontAwesome is imported globally, some components use emoji templates.
- Dateien/Module: `App.vue`, `public/icons.svg`, `main.scss`, `NotificationsDashboard.vue`, icon components.
- Subagent: Design System Agent.
- Schritte:
  1. Inventory icon usage.
  2. Choose SVG sprite or component-based icons.
  3. Move sprite out of App.vue if retained.
- Akzeptanzkriterien: App.vue no longer owns the icon system.
- Tests: `npm run type-check`, `npm run build-only`.
- Risiken: Broken icon references in many pages.
- Abhaengigkeiten: KAN-004.
- Artefakte/Diffs: Icon component or sprite module diffs.

## EPIC 3: App Shell & Navigation

### KAN-007: Split App.vue into app shell components

- Ziel: Remove domain logic from App.vue.
- Kontext: App.vue has 1,324 lines and owns layout, icons, notifications, queue, theme and mobile menu.
- Dateien/Module: `App.vue`, new `components/app/*`.
- Subagent: Vue Frontend Architecture Agent.
- Schritte:
  1. Extract AppShell.
  2. Extract AppHeader.
  3. Move Notification Center mount point.
  4. Move Queue Monitor mount point.
- Akzeptanzkriterien: App.vue becomes orchestration only and has no notification storage logic.
- Tests: `npm run type-check`, `npm run build-only`, route smoke.
- Risiken: Header, menu and popup behavior regression.
- Abhaengigkeiten: KAN-005, KAN-006.
- Artefakte/Diffs: App shell component diffs.

### KAN-008: Desktop and mobile navigation cleanup

- Ziel: Make desktop sidebar, mobile bottom nav and mobile sheets consistent.
- Kontext: Bottom nav exists, but App.vue also has a hamburger menu for jobs, notifications and logout.
- Dateien/Module: `useNavigation.ts`, `NavigationWrapper.vue`, `SidebarNav.vue`, `BottomNav.vue`, App shell components.
- Subagent: Mobile & Accessibility Agent.
- Schritte:
  1. Finalize primary tabs.
  2. Decide jobs and notifications surfaces.
  3. Ensure safe area and 44px targets.
- Akzeptanzkriterien: No competing mobile navigation patterns.
- Tests: Responsive smoke at 390px, 430px, 768px, 1024px and 1440px.
- Risiken: Existing users rely on header menu actions.
- Abhaengigkeiten: KAN-002, KAN-007.
- Artefakte/Diffs: Navigation component diffs.

## EPIC 4: Kernseiten Redesign

### KAN-009: Dashboard/Home redesign

- Ziel: Build status-rich dashboard around recordings, live streamers, latest videos, failures and queue.
- Kontext: Product UX plan defines dashboard as operational overview.
- Dateien/Module: `views/HomeView.vue`, dashboard components, realtime and notification stores.
- Subagent: UI/UX Product Designer Agent plus Vue Frontend Architecture Agent.
- Schritte: Design layout, implement components, wire central stores, remove duplicate local watchers.
- Akzeptanzkriterien: Desktop and mobile dashboard are usable and status-driven.
- Tests: type-check, build, desktop/mobile smoke.
- Risiken: Realtime changes depend on KAN-017.
- Abhaengigkeiten: KAN-005, KAN-017.
- Artefakte/Diffs: Home view and components.

### KAN-010: Streamer list and detail redesign

- Ziel: Modernize streamer overview and detail cockpit.
- Kontext: Streamer views are large and duplicate WebSocket processing.
- Dateien/Module: `views/StreamersView.vue`, `views/StreamerDetailView.vue`, `components/cards/StreamerCard.vue`.
- Subagent: Vue Frontend Architecture Agent.
- Schritte: Use shared cards, filter bar, detail tabs and central realtime updates.
- Akzeptanzkriterien: Live/offline/recording states are immediate and consistent.
- Tests: type-check, build, mobile smoke.
- Risiken: Existing force-recording actions and settings may regress.
- Abhaengigkeiten: KAN-005, KAN-017.
- Artefakte/Diffs: Streamer view and component diffs.

### KAN-011: Videos and player redesign

- Ziel: Improve videos, video player and live player UX.
- Kontext: `VideoPlayer.vue`, `VideoPlayerView.vue` and `LivePlayerView.vue` are very large.
- Dateien/Module: video views, `components/VideoPlayer.vue`, `components/cards/VideoCard.vue`.
- Subagent: Vue Frontend Architecture Agent.
- Schritte: Split player status, error and controls. Apply shared media grid/list.
- Akzeptanzkriterien: HLS errors, loading and offline states are clear.
- Tests: type-check, build, manual player smoke where possible.
- Risiken: HLS token/playback behavior is sensitive.
- Abhaengigkeiten: KAN-005.
- Artefakte/Diffs: Player and media component diffs.

### KAN-012: Settings and Admin cleanup

- Ziel: Separate user settings from diagnostics.
- Kontext: Settings has PWA, notification and technical controls mixed with user settings.
- Dateien/Module: `views/SettingsView.vue`, `views/AdminView.vue`, settings panels, admin components.
- Subagent: UI/UX Product Designer Agent plus Vue Frontend Architecture Agent.
- Schritte: Regroup settings, move debug/test panels into Admin Diagnostics, simplify save patterns.
- Akzeptanzkriterien: Push, Apprise and WebSocket diagnostics are clearly separated.
- Tests: type-check, build, settings panel smoke.
- Risiken: Admin-only features could become inaccessible.
- Abhaengigkeiten: KAN-003, KAN-005, KAN-020.
- Artefakte/Diffs: Settings and admin diffs.

## EPIC 5: Realtime-Architektur / WebSocket

### KAN-013: Typed realtime event model

- Ziel: Define `RealtimeEvent` and event type mapping.
- Kontext: Event names include dotted and underscored variants such as `recording.started` and `recording_started`.
- Dateien/Module: new `types/events.ts`, `useWebSocket.ts`, consumers.
- Subagent: Realtime/WebSocket Agent.
- Schritte: Inventory event names, define union types, normalize where safe.
- Akzeptanzkriterien: All frontend consumers use typed event helpers.
- Tests: type-check.
- Risiken: Backend names cannot be changed casually.
- Abhaengigkeiten: KAN-001.
- Artefakte/Diffs: Event types and mapping.

### KAN-014: Central realtime store

- Ziel: Replace scattered latest-message watchers with one central store/composable.
- Kontext: Multiple consumers watch `messages` and process only latest message.
- Dateien/Module: `useWebSocket.ts`, new realtime store, Home, Streamers, Settings, queue composables.
- Subagent: Realtime/WebSocket Agent.
- Schritte: Keep singleton connection, add event bus/state projections, expose connection status.
- Akzeptanzkriterien: Domain components consume selectors, not raw message arrays.
- Tests: type-check, build, reconnect smoke.
- Risiken: Widespread consumers.
- Abhaengigkeiten: KAN-013.
- Artefakte/Diffs: Store and consumer diffs.

### KAN-015: Reconnect, dedupe and replay capability check

- Ziel: Improve reconnect behavior and document backend replay gap.
- Kontext: No frontend since-cursor or replay endpoint found.
- Dateien/Module: realtime store, backend routes if available.
- Subagent: Realtime/WebSocket Agent.
- Schritte: Add visibility/online handling, dedupe keys, check backend for replay endpoint. If missing, create backend task and block replay implementation.
- Akzeptanzkriterien: Reconnect state visible and duplicate UI events reduced.
- Tests: manual disconnect/reconnect smoke, type-check, build.
- Risiken: Replay cannot be frontend-only.
- Abhaengigkeiten: KAN-014.
- Artefakte/Diffs: Reconnect logic, backend gap note.

## EPIC 6: Notification-Architektur

### KAN-016: Canonical notification schema

- Ziel: Define shared notification event shape for UI, WebSocket and Push.
- Kontext: Current notifications use generated IDs, heuristic dedupe and inconsistent field names.
- Dateien/Module: `types/events.ts`, notification services, `NotificationFeed.vue`, App shell.
- Subagent: Realtime/WebSocket Agent plus Vue Frontend Architecture Agent.
- Schritte: Define schema, adapters for existing events, target URL logic and severity mapping.
- Akzeptanzkriterien: Notification Center never guesses critical fields from arbitrary payloads.
- Tests: type-check and adapter unit tests if existing test setup allows.
- Risiken: Backend may need changes for stable event_id and dedupe_key.
- Abhaengigkeiten: KAN-013.
- Artefakte/Diffs: Types and adapter diffs.

### KAN-017: Notification store and persistence

- Ziel: Move notification history out of App.vue/localStorage wild storage.
- Kontext: App.vue stores `streamvault_notifications`, `lastReadTimestamp` and dispatches `notificationsUpdated`.
- Dateien/Module: `App.vue`, `NotificationFeed.vue`, new notification store and storage service.
- Subagent: Vue Frontend Architecture Agent.
- Schritte: Create store, encapsulate storage, model read/unread, support filters and actions.
- Akzeptanzkriterien: App.vue no longer owns notification storage or unread calculations.
- Tests: type-check, build, local notification smoke.
- Risiken: Backend/local persistence decision affects scope.
- Abhaengigkeiten: KAN-016.
- Artefakte/Diffs: Store, storage and component diffs.

### KAN-018: Product Notification Center

- Ziel: Rebuild NotificationFeed as product-grade Notification Center.
- Kontext: NotificationFeed is 1,118 lines and localStorage-coupled.
- Dateien/Module: `NotificationFeed.vue`, new `components/notifications/*`.
- Subagent: UI/UX Product Designer Agent plus Vue Frontend Architecture Agent.
- Schritte: Split item, filters, empty/loading/error, desktop panel and mobile sheet.
- Akzeptanzkriterien: Read/unread, filtering, dedupe and target navigation work.
- Tests: type-check, build, mobile/desktop smoke.
- Risiken: Requires KAN-017 store first.
- Abhaengigkeiten: KAN-017.
- Artefakte/Diffs: Notification components.

## EPIC 7: PWA & Web Push

### KAN-019: Service worker strategy consolidation

- Ziel: Choose exactly one service worker registration and source strategy.
- Kontext: VitePWA register, index.html `/registerSW.js`, public registerSW and usePWA manual register coexist.
- Dateien/Module: `main.ts`, `index.html`, `vite.config.ts`, `usePWA.ts`, `public/registerSW.js`, `public/sw.js`, `public/push-sw.js`, backend SW routes.
- Subagent: PWA/Web Push Agent.
- Schritte: Decide generateSW plus explicit importScripts or injectManifest with `src/sw.ts`. Remove duplicate registrations after verification.
- Akzeptanzkriterien: One documented registration path and push handlers included in built SW.
- Tests: build, service worker registration smoke, push handler presence check.
- Risiken: Mobile push regression.
- Abhaengigkeiten: KAN-003, KAN-016.
- Artefakte/Diffs: SW and PWA config diffs.

### KAN-020: Push subscription lifecycle and permission UX

- Ziel: Make push opt-in reliable and user-friendly.
- Kontext: `usePWA.ts` directly requests permission during subscribe and posts subscription to backend.
- Dateien/Module: `usePWA.ts`, `PWAPanel.vue`, PWA status components, `routes/push.py` if needed.
- Subagent: PWA/Web Push Agent.
- Schritte: Add explanatory opt-in flow, detect existing subscription, renew stale subscription, surface denied/default/granted states.
- Akzeptanzkriterien: Permission is requested only after user action and explanation.
- Tests: type-check, build, manual denied/default/granted matrix.
- Risiken: Browser-specific behavior.
- Abhaengigkeiten: KAN-019.
- Artefakte/Diffs: PWA components and composable.

### KAN-021: notificationclick and mobile platform documentation

- Ziel: Ensure push click opens correct route and document Android/iOS caveats.
- Kontext: `push-sw.js` handles `notificationclick` with `internal_url` or `url`.
- Dateien/Module: service worker, app SW message handler, docs.
- Subagent: PWA/Web Push Agent.
- Schritte: Verify app-side navigation handler, add target URL mapping, document Android Chrome and iOS Home Screen behavior.
- Akzeptanzkriterien: Push click deep links work in built app or limitations are documented.
- Tests: manual PWA push matrix where environment allows.
- Risiken: iOS Web Push requires installed Home Screen app and platform support.
- Abhaengigkeiten: KAN-019, KAN-020.
- Artefakte/Diffs: SW and documentation diffs.

## EPIC 8: Mobile/PWA UX

### KAN-022: Mobile layout and accessibility pass

- Ziel: Validate touch targets, safe areas, keyboard and focus.
- Kontext: Some 44px and safe-area fixes exist, but large custom components need review.
- Dateien/Module: Navigation, Notification Center, Settings, Dashboard, Video/Live player.
- Subagent: Mobile & Accessibility Agent.
- Schritte: Check 390px, 430px, 768px, focus states, reduced motion and semantic controls.
- Akzeptanzkriterien: No horizontal scroll and no obvious inaccessible control in primary flows.
- Tests: responsive smoke, keyboard smoke, build.
- Risiken: Visual-only testing cannot replace real mobile devices.
- Abhaengigkeiten: KAN-008, KAN-018, KAN-020.
- Artefakte/Diffs: CSS/component fixes and QA notes.

## EPIC 9: Codequalitaet & Cleanup

### KAN-023: API, composables and storage cleanup

- Ziel: Reduce direct fetches, scattered localStorage and duplicate logic.
- Kontext: API services exist but many components still fetch directly. localStorage appears in auth, theme, navigation, notifications, PWA and live player.
- Dateien/Module: services, composables, storage service, stores.
- Subagent: Vue Frontend Architecture Agent.
- Schritte: Introduce storage wrapper, consolidate API calls, remove duplicate watchers after stores exist.
- Akzeptanzkriterien: Domain state is not stored in raw localStorage outside a wrapper.
- Tests: type-check, build.
- Risiken: Auth and live token behavior is sensitive.
- Abhaengigkeiten: KAN-014, KAN-017.
- Artefakte/Diffs: Service and composable diffs.

### KAN-024: Remove or isolate dead/debug UI paths

- Ziel: Clean product navigation and routes.
- Kontext: KAN-003 classifies debug paths.
- Dateien/Module: routes, PWA public files, diagnostics components.
- Subagent: Vue Frontend Architecture Agent.
- Schritte: Remove safe dead files, move retained diagnostics to Admin, dev-gate utilities.
- Akzeptanzkriterien: Normal user UI has no test/debug pages.
- Tests: type-check, build, route smoke.
- Risiken: Hidden diagnostics might still be used.
- Abhaengigkeiten: KAN-003, KAN-012, KAN-019.
- Artefakte/Diffs: Cleanup diffs.

## EPIC 10: Tests, QA & Abschluss

### KAN-025: Baseline and continuous checks

- Ziel: Keep build, typecheck and design-token lint green after each change.
- Kontext: Baseline currently passes after `npm ci`.
- Dateien/Module: app/frontend.
- Subagent: QA/Test Agent.
- Schritte: Run `npm run lint:tokens`, `npm run type-check`, `npm run build-only` after relevant task sets.
- Akzeptanzkriterien: Results are posted to Kanban comments.
- Tests: Commands above.
- Risiken: Build warnings may hide real regressions.
- Abhaengigkeiten: All implementation tasks.
- Artefakte/Diffs: QA comments.

### KAN-026: Manual QA matrix

- Ziel: Execute and document desktop, mobile, PWA, push and realtime manual tests.
- Kontext: Prompt defines required matrix.
- Dateien/Module: QA docs, app/frontend.
- Subagent: QA/Test Agent.
- Schritte: Create checklist, run available local/browser checks, mark unavailable device checks as not executed with reason.
- Akzeptanzkriterien: Every matrix row has pass, fail, blocked or not available.
- Tests: Manual matrix.
- Risiken: Real mobile push may not be testable in this environment.
- Abhaengigkeiten: KAN-019, KAN-020, KAN-021, KAN-022.
- Artefakte/Diffs: QA report.

### KAN-027: Integration review

- Ziel: Review all diffs for consistency, regressions and scope creep.
- Kontext: Multiple subagents touch shared UI and stores.
- Dateien/Module: Full frontend diff.
- Subagent: Integration Reviewer Agent.
- Schritte: Review diffs, check conflicts between design system, app shell, realtime, notifications and PWA, request fixes.
- Akzeptanzkriterien: Approved or clear blocking comments.
- Tests: type-check, build, QA report review.
- Risiken: Parallel work can diverge in patterns.
- Abhaengigkeiten: KAN-025, KAN-026.
- Artefakte/Diffs: Review comments.

### KAN-028: Final documentation and handoff

- Ziel: Produce final summary matching the prompt Definition of Done.
- Kontext: Must include Graphify learnings, problems, UX decisions, design changes, components, PWA, realtime, notifications, tests and risks.
- Dateien/Module: docs, PR body if PR is opened.
- Subagent: Integration Reviewer Agent.
- Schritte: Compile completed and blocked tasks, changed files, checks and risks.
- Akzeptanzkriterien: Final summary is complete and sourced.
- Tests: Documentation review.
- Risiken: Missing blocked task rationale.
- Abhaengigkeiten: KAN-027.
- Artefakte/Diffs: Final summary doc or PR body.
