# StreamVault feature parity map

Date: 2026-07-06
Branch: feat/frontend-product-overhaul-final
Base: origin/develop at aa6a134d
Reference: PR #702 was foundation only

## Rule

No productive function may disappear accidentally. Debug, test and experiment surfaces can be removed only when they are proven non-product, moved to Admin Diagnostics, hidden behind a dev flag or recorded as intentionally replaced.

Allowed status values in this map:

- implemented and visually verified
- implemented and functionally verified
- intentionally admin-only
- intentionally dev-only
- intentionally removed with reason
- blocked with reason

A productive area can be `blocked with reason` during this follow-up, but it cannot be called complete until the block is resolved or accepted by a human reviewer.

## Core parity table

| Core area | Current route or component | User goal | Target UX | Status | Reason or verification needed | Kanban task | Screenshot findings |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard | `/`, `HomeView.vue` | Understand system health quickly | Status-first overview with live, recording, queue, errors, recent activity and quick actions | blocked with reason | Requires dashboard rebuild plus visual evidence at desktop and mobile widths | E-DASH-001 | UXF-001, UXF-015, UXF-017 |
| Streamers | `/streamers`, `StreamersView.vue` | Find, scan and manage creators | Dense creator grid or responsive list with search, filters, sort and clear Add Streamer action | blocked with reason | Requires creator-grid rebuild, stronger status grammar and mobile evidence | F-STREAMERS-001 | UXF-001, UXF-014, UXF-017 |
| Streamer Detail Overview | `/streamers/:id`, overview tab | Manage one streamer as a control center | Compact profile/status/action header with current recording and recovery panels | blocked with reason | Requires replacing the oversized low-value hero and verifying real or realistic streamer states | G-DETAIL-001 | UXF-003, UXF-004, UXF-005 |
| Streamer Detail Videos | `/streamers/:id`, videos tab | Review that streamer's recordings | Media list or grid with thumbnails, title, date, duration, size, status and actions | blocked with reason | Requires media-card style content and low-data visual evidence | G-DETAIL-001, H-LIBRARY-001 | UXF-005, UXF-007 |
| Streamer Detail Recording Settings | `/streamers/:id`, recording settings tab | Tune streamer-specific recording safely | Settings cards with basic, quality, storage, automation, advanced and danger sections | blocked with reason | Requires replacing long form wall and verifying save, validation and danger flows | G-DETAIL-001, K-SETTINGS-001 | UXF-008 |
| Streamer Detail Events | `/streamers/:id`, events tab | Understand timeline and recent changes | Timeline-ready empty, loading and event states with target actions | blocked with reason | Requires meaningful empty state and future timeline structure | G-DETAIL-001 | UXF-005, UXF-006 |
| Videos / Library | `/videos`, `VideosView.vue` | Browse and find recordings | Modern media library with search, filters, sort, responsive grid/list and low-data state | blocked with reason | Requires library rebuild and product language alignment to Library | H-LIBRARY-001 | UXF-001, UXF-013, UXF-017 |
| Stored Video Player | `/videos/:id`, legacy watch route | Watch recordings and recover from playback issues | Player with context, loading, missing file, HLS and recovery states | blocked with reason | Requires real or realistic stored playback QA, mobile controls and lazy player evidence | I-PLAYER-001 | UXF-017 |
| Live Player | `/live/:streamer` | Watch a live stream and understand connection state | Live-first player with stream context, codec or quality state, reconnect and readable HLS errors | blocked with reason | Requires real or realistic HLS live QA and mobile control evidence | I-PLAYER-001 | UXF-017 |
| Queue / Background Jobs | Shell utilities, queue store, queue components | Track recording and processing work | Compact global jobs entry plus product queue states and admin detail when needed | blocked with reason | Requires unified job status item, queue evidence and no debug-first flow | C-DS-001, D-SHELL-001, E-DASH-001 | UXF-017 |
| Notification Center | Shell notification center, `stores/notifications.ts` | Review events, read state and targets | Filterable center with read/unread, dedupe, target links and mobile sheet or route | blocked with reason | Requires product-surface implementation and mobile evidence | J-NOTIFICATIONS-001 | UXF-017 |
| Settings Overview | `/settings`, `SettingsView.vue` | Find the right configuration area | Settings app overview with category cards, clear section nav and contextual save model | blocked with reason | Requires settings IA rebuild and mobile visual evidence | K-SETTINGS-001 | UXF-001, UXF-009, UXF-016 |
| Settings Recording | Settings recording section | Configure recording defaults safely | Grouped recording cards with basic and advanced split | blocked with reason | Requires source rebuild and settings save validation evidence | K-SETTINGS-001 | UXF-008, UXF-009 |
| Settings Notifications | Settings notification section | Configure notification channels | Responsive notification settings with desktop table and mobile cards | blocked with reason | Requires mobile transformation and notification test separation | K-SETTINGS-001, J-NOTIFICATIONS-001 | UXF-012 |
| Settings PWA / Push | Settings PWA section, `PWAPanel.vue`, `push-sw.js` | Install app and enable push intentionally | Guided install and permission flow with prerequisites, state, subscribe and recovery | blocked with reason | Requires device or reality-based push QA and notification click target verification | L-PWA-001 | UXF-011 |
| Settings API Keys | Settings API key area | Understand and manage API key risk | Security and Developer panel with state, explanation, copy, regenerate and revoke | blocked with reason | Requires productized API key UI and security copy | K-SETTINGS-001 | UXF-010 |
| Settings Proxy | Settings proxy area | Configure network proxy safely | Advanced network panel with validation and test feedback | blocked with reason | Requires placement under advanced settings and responsive form evidence | K-SETTINGS-001 | UXF-009 |
| Settings Favorite Games | Settings favorite games area | Manage recording or streamer preferences | Focused preference panel with searchable game choices and clear save state | blocked with reason | Requires source verification and settings card implementation | K-SETTINGS-001 | UXF-009 |
| Settings Twitch Connection | Settings Twitch section | Understand Twitch auth and token state | Integration panel with status, reconnect, token health and user-safe copy | blocked with reason | Requires functional auth state verification and mobile evidence | K-SETTINGS-001 | UXF-009 |
| Admin Diagnostics | `/admin`, `AdminView.vue`, `AdminPanel.vue` | Diagnose internals as an admin | Admin-only diagnostic capsule with raw tools behind disclosure | blocked with reason | Implementation has started in this branch, but still needs checks and visual evidence before it can be verified | M-ADMIN-001 | UXF-017 |
| Add Streamer Flow | `/add-streamer`, `/add-streamer/manual`, `/add-streamer/import` | Add creators manually or from Twitch | Guided add route or sheet with validation, success routing and helpful errors | blocked with reason | Requires route smoke, form validation and mobile evidence | F-STREAMERS-001 | UXF-014, UXF-017 |
| Auth / Setup / Onboarding | `/auth/setup`, `/welcome`, `/onboarding`, `/auth/login` | Set up and sign in without product chrome noise | Focused auth/setup shell with no premature push prompt and clear error recovery | blocked with reason | Requires auth/setup smoke and mobile evidence | L-PWA-001, K-SETTINGS-001 | UXF-017 |
| Mobile App Shell | `AppShell.vue`, bottom nav, sheets | Use StreamVault as a first-class PWA | Bottom navigation, safe areas, sheets, 44px targets and offline or reconnect state | blocked with reason | Requires 390, 430 and 768 visual evidence and touch target check | D-SHELL-001, L-PWA-001, N-QA-001 | UXF-002, UXF-012, UXF-017 |
| Desktop App Shell | `AppShell.vue`, sidebar, topbar | Navigate without chrome overwhelming content | Denser sidebar/topbar and coherent utility cluster for jobs, notifications, theme and logout | blocked with reason | Requires shell density pass and 1024, 1280, 1440 evidence | D-SHELL-001, N-QA-001 | UXF-002 |
| WebSocket / Realtime UI | `useWebSocket.ts`, realtime store, shell indicators | Trust live state and recover from reconnects | Central event projection with visible but calm connected, reconnecting and failed states | blocked with reason | Requires backend WebSocket smoke or explicit blocker and UI evidence | J-NOTIFICATIONS-001, I-PLAYER-001 | UXF-017 |
| PWA Install Flow | `PWAInstallPrompt.vue`, `PWAPanel.vue`, VitePWA registration | Install the app intentionally | Guided install prompt and settings flow with platform-specific copy | blocked with reason | Requires installed PWA or reality-based platform QA | L-PWA-001 | UXF-011 |
| Push Permission Flow | `PWAPanel.vue`, `push-sw.js`, push API services | Enable browser push after understanding value | Permission priming, subscribe, test separation, denied recovery and target click routes | blocked with reason | Requires real or reality-based push delivery and notification click verification | L-PWA-001, J-NOTIFICATIONS-001 | UXF-011 |
| WebSocketMonitor | Admin diagnostic component | Debug connection internals | Raw diagnostics only inside Admin Diagnostics | intentionally admin-only | Product flows must link to user-readable status first, not raw monitor output | M-ADMIN-001 | UXF-017 |
| Logger and debug helpers | Dev helper functions and debug utilities | Troubleshoot during development | Dev-only manual helpers or Admin Diagnostics | intentionally dev-only | Debug helpers must not auto-run in production flows | M-ADMIN-001, L-PWA-001 | UXF-017 |

## Route preservation checklist

The following productive routes must remain routable unless a subsequent task explicitly replaces them with a redirect and records the reason:

- `/`
- `/streamers`
- `/streamers/:id`
- `/videos`
- `/videos/:id`
- `/live/:streamer`
- `/subscriptions`
- `/settings`
- `/admin`
- `/add-streamer`
- `/add-streamer/manual`
- `/add-streamer/import`
- `/auth/setup`
- `/welcome`
- `/onboarding`
- `/auth/login`
- `/streamer/:streamerId/stream/:streamId/watch`

## Current phase result

This map is intentionally strict. Most productive areas are currently `blocked with reason` because the follow-up implementation and evidence gates have not passed yet. The map will be updated only when a task produces real source changes plus matching functional or visual evidence.
