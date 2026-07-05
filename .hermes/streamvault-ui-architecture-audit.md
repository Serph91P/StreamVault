# StreamVault UI architecture audit

Date: 2026-07-05
Scope: app/frontend plus relevant backend WebSocket and PWA endpoints

## Executive architecture finding

The previous architecture centralized too much product logic in App.vue and component-local state. The overhaul moved StreamVault toward a shell plus domain-store model while keeping Vue 3, Vite, TypeScript, Pinia, Vue Router, SCSS, VitePWA and hls.js.

## Before and after

| Layer | Before | After |
| --- | --- | --- |
| App.vue | Layout, icon sprite, header state, mobile menu, notification storage, WebSocket message handling, queue mounts | Thin app root with icon sprite, shell, route rendering, PWA prompt, toast container and realtime banner |
| App shell | Header, sidebar, mobile menu and panels spread across App.vue and navigation components | AppShell, AppHeader and AppNotificationCenter own product shell concerns |
| Realtime | useWebSocket kept raw messages, many consumers watched latest message | useWebSocket remains connection owner, realtime Pinia store projects typed events |
| Notifications | App.vue and localStorage owned history, NotificationFeed read storage | Notification store, notificationStorage service and composed Notification Center |
| PWA | VitePWA, registerSW.js, public sw.js and usePWA manual registration coexisted | Single VitePWA registration owner, push-sw custom handler retained |
| Design system | Global SCSS, base components and one off scoped styles mixed | BasePanel, BaseSheet, BaseTable, FormField, StatusBadge, SurfaceCard and icon system established |
| Debug UI | PWA tester, notification dashboard, helper files and diagnostics leaked | Removed or moved to Admin Diagnostics |

## Target frontend architecture

```text
main.ts
  -> Pinia
  -> router
  -> VitePWA registerSW
  -> App.vue
       -> IconSprite
       -> AppShell
            -> AppHeader
            -> NavigationWrapper
            -> router-view
            -> NotificationFeed / AppNotificationCenter
            -> BackgroundQueueMonitor
            -> PWAInstallPrompt
            -> ToastContainer

Stores:
  realtime.ts
  notifications.ts
  counter.ts legacy only

Services:
  api.ts and api-real.ts
  storage.ts
  notificationStorage.ts

Typed contracts:
  types/events.ts
  types/recording.ts
  types/streamer.ts
  types/settings.ts
```

## Graphify verified hotspots

| Hotspot | Graphify or source evidence | Architectural action |
| --- | --- | --- |
| App.vue | Graphify and source showed it as large central import and logic node | Split app shell and removed domain ownership |
| NotificationFeed.vue | Graphify returned many local helper nodes and local storage behavior | Rebuilt as composed center with filters, item and state components |
| useWebSocket.ts | Graphify connected frontend and backend WebSocket concepts | Kept singleton, added listener dispatch and central store integration |
| public sw.js and registerSW.js | Source had multiple registration paths | Removed public generated worker and manual registration |
| AdminPanel.vue | Source showed dense diagnostics and test logic | Kept diagnostics under Admin only |

## Pinia store audit

| Store | Status | Responsibility | Notes |
| --- | --- | --- | --- |
| useRealtimeStore | Added | Connection status, event projection, replay awareness, dedupe and domain updates | UI consumes domain state rather than raw latest messages |
| useNotificationStore | Added | Notification list, filters, unread, dedupe, read state and target navigation | Backed by notificationStorage service |
| counter | Legacy | Vue starter style store | Not used for product state |
| Future recording store | Planned | Recordings, active recording cache and actions | Current composables remain for this PR |
| Future streamer store | Planned | Streamer list and detail cache | Current services and composables remain |
| Future settings store | Planned | Settings save and dirty state | Current settings panels remain service backed |
| Future UI store | Planned | Cross shell UI state | Local shell refs remain acceptable first step |

## Services and composables audit

| Module | Finding | Action |
| --- | --- | --- |
| services/api.ts | Service facade exists and still exposes many any typed legacy shapes | Retained for compatibility, used by new stores where possible |
| services/api-real.ts | Real endpoint layer | Retained, future type tightening recommended |
| services/storage.ts | Needed to stop random localStorage writes | Added as central wrapper |
| services/notificationStorage.ts | Needed notification persistence ownership | Added with legacy migration |
| composables/usePWA.ts | Previously registered service worker manually | Changed to resolve existing VitePWA registration |
| composables/useWebSocket.ts | Singleton was useful but not a domain store | Added listener support and kept connection concern there |
| composables/useSystemAndRecordingStatus.ts | Mixed REST fallback and realtime handling | Connected to central realtime path, future split recommended |
| composables/useRecordingSettings.ts | Settings plus realtime updates | Retained, future domain store candidate |

## Styling architecture audit

| File | Role | Rule |
| --- | --- | --- |
| _variables.scss | Canonical tokens and compatibility aliases | New semantic tokens go here first |
| _glass-system.scss | Glass and surface primitives | Keep controlled, do not make every page glass |
| _components.scss | Shared component layer | Avoid new page specific one offs here |
| main.scss | Import and global setup | No global button overrides that fight BaseButton |
| Component scoped styles | Local layout exceptions | Allowed when component specific and token based |

## PWA architecture audit

| Concern | Final decision |
| --- | --- |
| Service worker registration | `virtual:pwa-register` in main.ts owns app registration |
| Generated service worker | VitePWA generateSW emits dist/sw.js at build time |
| Custom push handling | public/push-sw.js remains and is imported by backend generated worker path |
| Old public sw.js | Removed from source control |
| Old registerSW.js | Removed from frontend source and backend fallback made no-op compatibility |
| Push permission | Request only after explicit user action |
| Notification click | Prefer target_url and normalize legacy streamer detail links |

## Architecture risks

- Some large legacy components remain, especially VideoPlayer and AdminPanel.
- API service types still contain many any warnings from pre-existing and touched areas.
- Recording, streamer, video and settings stores are planned but not all implemented in this PR.
- Full browser PWA validation requires installed mobile devices.

## Recommended next architecture PRs

1. Split VideoPlayer into controller, HLS service, controls and error presentation.
2. Introduce streamer and video Pinia stores with typed API responses.
3. Tighten API response types and reduce no-explicit-any warnings incrementally.
4. Add a dedicated Queue store if background jobs become a primary product surface.
