# StreamVault feature parity map

Date: 2026-07-05
Branch: feat/frontend-overhaul-v2
Head: 8766fe23

## Rule

No productive function may disappear accidentally. Debug, test and experiment surfaces can be removed only when they are proven non-product, moved to Admin Diagnostics, hidden behind a dev flag or documented as intentionally replaced.

| Existing route or component | Function | User goal | New target position | New UX flow | Status | Risk | Test requirement |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/` HomeView | Dashboard | Understand system state | Dashboard | status first overview | rebuild further | High | browser route smoke, typecheck, build |
| `/streamers` StreamersView | Streamer overview | Find and manage streamers | Streamers | search, filters, status cards | rebuild further | High | mobile route smoke, feature parity check |
| `/streamers/:id` StreamerDetailView | Detail cockpit | Manage one streamer | Streamer detail | tabs and contextual actions | rebuild further | High | deep link and realtime QA |
| `/videos` VideosView | Media library | Find recordings | Library | responsive grid and filters | rebuild further | Medium | video list QA |
| `/videos/:id` VideoPlayerView | Stored playback | Watch recording | Video player | player with recovery states | keep and improve | High | HLS and missing file QA |
| `/live/:streamer` LivePlayerView | Live playback | Watch live stream | Live player | player first plus status | keep and improve | High | HLS live QA |
| `/subscriptions` SubscriptionsView | Subscriptions | Manage subscriptions | Subscriptions | primary nav page | keep | Medium | route smoke |
| `/settings` SettingsView | Configuration | Change settings safely | Settings | grouped settings, advanced split | rebuild further | High | settings save tests and QA |
| `/admin` AdminView/AdminPanel | Diagnostics | Inspect internals | Admin Diagnostics | admin only diagnostics | capsule | Medium | admin route smoke |
| `/add-streamer*` AddStreamerView | Add/import streamer | Add streamers | Add streamer flow | task route or sheet | keep and improve | Medium | form validation QA |
| `/auth/setup`, `/welcome`, `/onboarding` | Setup and onboarding | First run setup | Auth/setup shell | no premature push prompt | keep and improve | Medium | auth/setup route QA |
| `/auth/login` | Login | Authenticate | Auth shell | sign in and recover errors | keep | Medium | auth route QA |
| `/streamer/:streamerId/stream/:streamId/watch` | Legacy playback | Preserve old links | Compatibility player route | route to player | keep | Medium | legacy link smoke |
| Notification store and center | In-app notifications | Understand events | Notification Center | filters, read state, target links | keep and improve | High | notification QA |
| Realtime store and useWebSocket | Live updates | Trust system state | realtime domain layer | central event projection | keep and improve | High | WebSocket reconnect QA |
| PWAPanel and push-sw | PWA and push | Install and receive alerts | PWA settings and prompt | permission, subscribe, click target | keep, test actions moved to Admin Diagnostics | High | real device QA |
| WebSocketMonitor | Raw diagnostics | Debug connection | Admin Diagnostics | admin only | admin-only | Low | admin QA |
| Logger and API debug paths | Developer diagnostics | Troubleshoot | dev or admin only | hidden from normal users | capsule, dev PWA debug is manual only | Medium | source review |

## Parity result for phase 1

The current `develop` branch already contains a substantial previous overhaul, so the next implementation must not delete those changes blindly. The second pass should improve the remaining large surfaces and architecture gaps while preserving the productive routes and backend integrations listed above.

## Cleanup review for KAN2-009

- Settings PWA and notification panels keep preference flows, but send delivery tests to Admin Diagnostics instead of showing test buttons in the user settings flow.
- Admin Diagnostics keeps productive repair and troubleshooting functions, but advanced queue, post-processing, verification, maintenance and video recording diagnostics are collapsed behind labeled disclosure controls.
- Dev PWA diagnostics no longer auto-run on mobile page load. The helper is available as `window.debugStreamVaultPWA()` only in development builds.
