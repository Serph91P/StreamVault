# StreamVault frontend overhaul plan

Date: 2026-07-05
Board: streamvault-frontend-overhaul
Target branch: feat/frontend-overhaul-plan
Target base: develop

## Success criteria

- Graphify read and source verified.
- Inventory, UX audit, architecture audit, feature parity map, design system, QA report and summary exist under .hermes.
- Vue stack preserved.
- App shell, navigation, central pages, PWA and notification flows overhauled.
- Debug and test UI removed or placed in Admin Diagnostics.
- Feature parity reviewed.
- CI and local checks pass.

## Kanban execution record

All Hermes Kanban cards on board `streamvault-frontend-overhaul` completed:

| Epic | Cards | Result |
| --- | --- | --- |
| Discovery, Graphify and inventory | KAN-001, KAN-002, KAN-003 | Analysis baseline, UX model and debug inventory done |
| Design system | KAN-004, KAN-005, KAN-006 | Token plan, primitives and icon consolidation done |
| App shell and navigation | KAN-007, KAN-008 | App shell split and navigation cleanup done |
| Core page overhaul | KAN-009, KAN-010, KAN-011, KAN-012 | Dashboard, streamers, players, settings and admin improved |
| State, realtime and notifications | KAN-013 to KAN-018 plus backend follow-up | Typed events, realtime store, replay endpoint and Notification Center done |
| PWA and mobile | KAN-019 to KAN-022 | Service worker strategy, push UX, platform docs, mobile and a11y pass done |
| Cleanup and QA | KAN-023 to KAN-028 | Storage cleanup, debug removal, checks, QA, integration review and handoff done |

## Required task template used

Each implementation or review task was required to cover:

- Title and goal.
- UX method or design principle.
- Affected views and components.
- Affected stores and services.
- Feature parity requirement.
- Desktop acceptance criteria.
- Mobile and PWA acceptance criteria.
- Accessibility acceptance criteria.
- Performance acceptance criteria.
- Test requirements.
- Risks and dependencies.
- Subagent or worker responsibility.
- Definition of Done.

## Epic plan details

### EPIC 1: Discovery, Graphify and inventory

Goal: understand existing product and avoid accidental feature loss.

Tasks:

- Graphify context and source verification.
- Frontend route, view, component, store, composable, service and style inventory.
- Feature parity map.
- UX and UI architecture audit.
- Performance and fluidity audit.

Definition of Done: .hermes inventory, audit and parity files exist and cite Graphify plus source facts.

### EPIC 2: UX concept and information architecture

Goal: define product behavior before code.

Methods applied: Nielsen heuristics, Jobs to be Done, user journeys, task flows, information architecture, progressive disclosure and recognition over recall.

Definition of Done: product target model, navigation and flow decisions documented and used by page tasks.

### EPIC 3: Design system

Goal: avoid one off page styling.

Tasks:

- Define design principles.
- Consolidate tokens and SCSS ownership.
- Add core primitives for panels, sheets, tables, forms, status and surfaces.
- Consolidate icon rules.
- Define status language for live, recording, queued, failed, completed and offline.

Definition of Done: design system file exists and implemented primitives are exported.

### EPIC 4: App shell and architecture

Goal: remove product logic from App.vue.

Tasks:

- Split shell into AppShell and AppHeader.
- Keep auth layout separate from product shell.
- Move notification panel and realtime toast behavior out of App.vue.
- Align desktop sidebar and mobile bottom nav.

Definition of Done: App.vue only orchestrates shell, route, icons and global adjuncts.

### EPIC 5: State, stores and services

Goal: centralize domain state and browser infrastructure.

Tasks:

- Realtime store.
- Notification store.
- Storage service.
- Notification storage service.
- API and composable cleanup where touched.

Definition of Done: UI reacts to typed store state where implemented, not raw scattered WebSocket messages.

### EPIC 6: Realtime and notifications

Goal: make events understandable and actionable.

Tasks:

- Typed event schema.
- Realtime dedupe and replay awareness.
- Backend replay endpoint.
- Notification Center with filters, read state and target links.

Definition of Done: notification and realtime flows pass typecheck, build and replay pytest.

### EPIC 7: PWA and mobile experience

Goal: mobile PWA is first class.

Tasks:

- Single service worker registration strategy.
- Push permission and subscription UX.
- notificationclick target routing.
- Mobile layout, safe area and touch targets.
- Remove old PWA debug public paths.

Definition of Done: no duplicate service worker registration source remains, build generates dist/sw.js, manual device QA items documented.

### EPIC 8: Core pages overhaul

Goal: rebuild the main user surfaces around user goals.

Tasks:

- Dashboard status first redesign.
- Streamers list and detail redesign.
- Videos and player status components.
- Settings and Admin separation.
- Queue and notifications as global utilities.

Definition of Done: central flows remain reachable and use shared primitives or documented legacy components.

### EPIC 9: Cleanup

Goal: remove legacy noise and keep product focused.

Tasks:

- Remove test pages, generated service worker, manual registerSW and orphan assets.
- Remove old notification dashboard experiment.
- Centralize storage access.
- Eliminate unused imports found by CI.

Definition of Done: source search and CI confirm no stale product blockers.

### EPIC 10: QA, accessibility, performance and closure

Goal: verify locally, through CI and with documented manual limits.

Tasks:

- Frontend lint, token lint, typecheck and build.
- Backend replay pytest.
- Ruff for changed Python files.
- Diff hygiene and unicode dash scan.
- Manual QA matrix and final summary.
- PR and CI monitoring.

Definition of Done: PR open against develop, CI green, risks documented.
