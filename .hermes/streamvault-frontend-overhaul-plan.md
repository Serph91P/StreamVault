# StreamVault frontend overhaul plan

Date: 2026-07-05
Branch: feat/frontend-overhaul-v2
Head: 8766fe23
Board: streamvault-frontend-overhaul-v2
Base branch: develop

## Scope statement

This is a fresh prompt-driven pass from current `develop`. It does not treat PR #700 as sufficient. Phase 1 has identified remaining risks in large views, settings, admin diagnostics, player surfaces, store boundaries, mobile/PWA validation and performance measurement.

## Epics and Kanban structure

### EPIC 1: Discovery, Graphify and inventory

Tasks:

- Graphify context from fresh current frontend code.
- Existing docs and reports review.
- Route, view, component, store, composable, service and style inventory.
- UX audit, UI architecture audit and performance audit.
- Feature parity map.

Definition of Done: the five phase 1 `.hermes` files exist and cite current source facts.

### EPIC 2: UX concept and information architecture

Tasks:

- Jobs to be Done refinement.
- Journey maps for setup, dashboard, add streamer, active recordings, videos, notifications, mobile PWA, failure recovery and settings.
- Task flows for every core route.
- IA decision for Dashboard, Streamers, Library, Queue, Notifications, Settings and Admin Diagnostics.

Definition of Done: product target and navigation decisions are documented before code changes.

### EPIC 3: Design system

Tasks:

- Define `.hermes/streamvault-design-system.md`.
- Audit existing primitives against Button, IconButton, Input, Select, Toggle, Tabs, SegmentedControl, Modal, Drawer, BottomSheet, Toast, NotificationItem, JobStatusItem, DataTable and SettingsPanel requirements.
- Reduce one off page styling where touched.

Definition of Done: design rules are written and implementation tasks consume them.

### EPIC 4: App shell and architecture

Tasks:

- Prove App.vue is shell only or split remaining logic.
- Add route metadata for product labels and shells.
- Create or refine UI store for shell state.
- Ensure desktop and mobile navigation use one source of truth.

Definition of Done: App shell has clear boundaries and no domain processing.

### EPIC 5: State, stores and services

Tasks:

- Plan and add missing domain stores where justified: recording, streamer, video, settings, PWA, queue and UI.
- Keep services responsible for API and infrastructure.
- Move domain-like composables into stores or services where touched.

Definition of Done: central flows use domain state instead of repeated local orchestration.

### EPIC 6: Realtime and notifications

Tasks:

- Verify typed event schema covers current backend events.
- Improve dedupe and read/unread where needed.
- Make WebSocket, Web Push and Apprise channel differences visible without debug language.
- Verify notification deep links.

Definition of Done: UI reacts to typed event state and Notification Center is actionable.

### EPIC 7: PWA and mobile experience

Tasks:

- Verify single service worker registration strategy.
- Make PWA install and push permission flow product grade.
- Verify safe area, touch targets, sheets and no horizontal scroll.
- Document real device gaps.

Definition of Done: mobile PWA is treated as a primary interface, not a shrinked desktop page.

### EPIC 8: Core pages overhaul

Tasks:

- Dashboard, Streamers, Streamer Detail, Library, Live Player, Video Player, Queue, Settings, Admin Diagnostics and Auth/Setup improvements.
- Split large page files into feature components where the UX requires deeper work.

Definition of Done: central pages are clearer, faster to scan and less monolithic.

### EPIC 9: Cleanup

Tasks:

- Remove or capsule leftover debug/test paths.
- Remove unused styles, views, imports and duplicated components only when verified.
- Preserve all productive feature parity.

Definition of Done: no accidental product loss and no debug UI in product flows.

### EPIC 10: QA, accessibility, performance and closure

Tasks:

- `npm run lint:tokens`
- `npm run type-check`
- `npm run build`
- Route smoke for central pages.
- Mobile widths 375, 390, 430 and 768.
- Desktop widths 1024, 1200 and 1440.
- Keyboard, reduced motion, PWA, push and WebSocket checks where possible.
- `.hermes/streamvault-frontend-qa-report.md`
- `.hermes/streamvault-frontend-overhaul-summary.md`

Definition of Done: final checks and limitations are documented with real output.

## Immediate next tasks

1. Create the real Kanban cards for all epics.
2. Assign parallel discovery and design tasks to workers.
3. Produce design-system and IA artifacts.
4. Only then start code changes on this branch.
