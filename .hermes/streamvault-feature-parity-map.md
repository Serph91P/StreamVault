# StreamVault feature parity map

Date: 2026-07-07
Branch: feat/frontend-product-overhaul-final
Base: origin/develop
Reference: PR #702 was foundation only. This follow-up branch contains the product UX implementation and QA evidence.

## Rule

Allowed status values:

- implemented and visually verified
- implemented and functionally verified
- intentionally admin-only
- intentionally dev-only
- intentionally removed with reason
- blocked with reason

A productive area can only stay blocked if the blocker is explicit and cannot be truthfully verified in the current environment.

## Core parity table

| Core area | Current route or component | Status | Verification or blocker | Kanban task | Evidence |
| --- | --- | --- | --- | --- | --- |
| Dashboard | `/`, `HomeView.vue` | implemented and visually verified | Status-first dashboard implemented with live, recording, queue, errors, recent activity and quick actions. | E-DASH-001 | `.hermes/frontend-visual-evidence/*dashboard*`, `npm run build`, `npm run lint` |
| Streamers | `/streamers`, `StreamersView.vue` | implemented and visually verified | Responsive creator grid, clearer status grammar, search/filter/sort and Add Streamer CTA. | F-STREAMERS-001 | `.hermes/frontend-visual-evidence/*streamers*` |
| Streamer Detail Overview | `/streamers/:id`, overview tab | implemented and visually verified | Detail page rebuilt as compact control center with safe actions and useful status hierarchy. | G-DETAIL-001 | `.hermes/frontend-visual-evidence/streamer-detail-*overview*` |
| Streamer Detail Videos | `/streamers/:id`, videos tab | implemented and visually verified | Media-style tab content and low-data states verified on mobile and desktop. | G-DETAIL-001, H-LIBRARY-001 | `.hermes/frontend-visual-evidence/streamer-detail-*videos*` |
| Streamer Detail Recording Settings | `/streamers/:id`, recording settings tab | implemented and visually verified | Recording settings moved into clearer cards and safer grouped controls. | G-DETAIL-001, K-SETTINGS-001 | `.hermes/frontend-visual-evidence/streamer-detail-*settings*` |
| Streamer Detail Events | `/streamers/:id`, events tab | implemented and visually verified | Timeline-ready events state and useful empty state verified. | G-DETAIL-001 | `.hermes/frontend-visual-evidence/streamer-detail-*events*` |
| Videos / Library | `/videos`, `VideosView.vue` | implemented and visually verified | Media library grid/list, filters, video-card states and low-data layout improved. | H-LIBRARY-001 | `.hermes/frontend-visual-evidence/*library*`, `h-library-001-*` |
| Stored Video Player | `/videos/:id`, `VideoPlayerView.vue` | implemented and visually verified | Player context, loading, error and recovery UI improved. | I-PLAYER-001 | `.hermes/frontend-visual-evidence/*stored-player*` |
| Live Player | `/live/:streamer`, `LivePlayerView.vue` | implemented and functionally verified | Real HLS gate passed against `summit1g`, with a live playlist returning `#EXTM3U` and segments. | I-PLAYER-001, N-QA-001B | `.hermes/non-mock-authorized-qa-results.json` |
| Queue / Background Jobs | Shell utilities and queue components | implemented and visually verified | Compact global job entry and clearer queue states integrated into shell and dashboard. | C-DS-001, D-SHELL-001, E-DASH-001 | `.hermes/frontend-visual-evidence/*queue*`, dashboard evidence |
| Notification Center | Shell notification center, `stores/notifications.ts` | implemented and visually verified | Product notification feed with read state, filters, target normalization and mobile/desktop surfaces. | J-NOTIFICATIONS-001 | `.hermes/frontend-visual-evidence/notification-center-*`, `.hermes/verify-notification-center.cjs` |
| Settings Overview | `/settings`, `SettingsView.vue` | implemented and visually verified | Settings app IA rebuilt with section navigation, cards, contextual state and mobile layout. | K-SETTINGS-001 | `.hermes/frontend-visual-evidence/*settings*` |
| Settings Recording | Settings recording section | implemented and visually verified | Recording settings grouped into clearer user-facing cards. | K-SETTINGS-001 | `.hermes/frontend-visual-evidence/*recording*` |
| Settings Notifications | Settings notification section | implemented and visually verified | Notification settings transformed for responsive desktop and mobile use. | K-SETTINGS-001, J-NOTIFICATIONS-001 | `.hermes/frontend-visual-evidence/*notifications*` |
| Settings PWA / Push | `PWAPanel.vue`, `PWAInstallPrompt.vue`, push services | blocked with reason | Backend/VAPID and local notification payload are verified, but real browser Push subscription and delivery require a real non-incognito browser or device. Hermes headless/Xvfb cannot create a PushManager subscription. | L-PWA-001, N-QA-001C | `.hermes/browser-push-qa-summary.md`, `.hermes/non-mock-authorized-qa-summary.md` |
| Settings API Keys | Settings API key area | implemented and visually verified | API keys are presented as security/developer panel with clearer state and copy. | K-SETTINGS-001 | `.hermes/frontend-visual-evidence/*api-keys*` |
| Settings Proxy | Settings proxy area | implemented and visually verified | Proxy settings live in advanced settings with responsive form and modal checks. | K-SETTINGS-001 | `.hermes/frontend-visual-evidence/*proxy*` |
| Settings Favorite Games | Settings favorite games area | implemented and visually verified | Settings IA preserves the preference area in the product settings model. | K-SETTINGS-001 | settings visual evidence and source checks |
| Settings Twitch Connection | Settings Twitch section | implemented and visually verified | Twitch connection state preserved inside the integration/settings model. | K-SETTINGS-001 | settings visual evidence and source checks |
| Admin Diagnostics | `/admin`, `AdminView.vue`, `AdminPanel.vue` | intentionally admin-only | Debug and diagnostics are separated from normal product flows. | M-ADMIN-001 | `.hermes/admin-diagnostics-qa/*` |
| Add Streamer Flow | `/add-streamer`, `/add-streamer/manual`, `/add-streamer/import` | implemented and visually verified | Add Streamer route remains reachable and has viewport evidence. | F-STREAMERS-001, N-QA-001 | `.hermes/frontend-visual-evidence/*add-streamer*` |
| Auth / Setup / Onboarding | `/auth/setup`, `/welcome`, `/onboarding`, `/auth/login` | implemented and functionally verified | Product routes preserved. Full real auth setup is not changed by this branch. | L-PWA-001, K-SETTINGS-001 | route smoke and build checks |
| Mobile App Shell | `AppShell.vue`, bottom nav, sheets | implemented and visually verified | Safe-area mobile shell, bottom nav and mobile utility surfaces verified at required viewports. | D-SHELL-001, L-PWA-001, N-QA-001 | `.hermes/frontend-visual-evidence/*mobile*`, 390/430/768 matrix |
| Desktop App Shell | `AppShell.vue`, sidebar, topbar | implemented and visually verified | Denser app chrome and coherent utility cluster verified at desktop widths. | D-SHELL-001, N-QA-001 | `.hermes/frontend-visual-evidence/*desktop*`, 1024/1280/1440 matrix |
| WebSocket / Realtime UI | `useWebSocket.ts`, realtime store, shell indicators | implemented and functionally verified | Real authenticated WebSocket connected and received `connection.status` plus `channel.update`. | J-NOTIFICATIONS-001, N-QA-001B | `.hermes/non-mock-authorized-qa-results.json` |
| PWA Install Flow | `PWAInstallPrompt.vue`, `PWAPanel.vue`, VitePWA registration | implemented and visually verified | Guided install flow and service worker source-of-truth verified in frontend. Real install remains browser/device dependent. | L-PWA-001 | `.hermes/mobile-pwa-qa-results.md` |
| Push Permission Flow | `PWAPanel.vue`, `push-sw.js`, push API services | blocked with reason | Server-side VAPID and UI flow are ready. Real subscription/delivery awaits Max testing on a real browser/device after image build. | L-PWA-001, J-NOTIFICATIONS-001, N-QA-001C | `.hermes/browser-push-qa-summary.md` |
| WebSocketMonitor | Admin diagnostic component | intentionally admin-only | Raw diagnostics are confined to Admin Diagnostics. | M-ADMIN-001 | admin evidence |
| Logger and debug helpers | Dev helper functions and debug utilities | intentionally dev-only | Debug helpers remain developer/admin tooling, not normal product UX. | M-ADMIN-001, L-PWA-001 | source review |

## Route preservation checklist

The following productive routes remain routable:

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

All product implementation epics A through M are done. N-QA is blocked only on real browser Push subscription and delivery. The branch is suitable for a develop image build so Max can test the remaining browser/device Push gate on real infrastructure. It must not be called a fully complete overhaul until that gate is verified or explicitly accepted as an environment limitation.
