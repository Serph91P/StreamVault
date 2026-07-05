# StreamVault UI architecture audit

Date: 2026-07-05
Branch: feat/frontend-overhaul-v2
Head: 8766fe23

## Current architecture snapshot

| Layer | Current state | Risk |
| --- | --- | --- |
| App root | App.vue is 896 lines and imports app shell concerns | Better than before, but still needs proof that it is shell only |
| Routes | 17 lazy routes in Vue Router | Good foundation, but route meta and product names need cleanup |
| Views | 13 views, many over 1,000 lines | Page logic remains too broad for a product-grade UI |
| Stores | `notifications.ts`, `realtime.ts`, legacy `counter.ts` | Missing first class recording, streamer, video, settings, PWA, queue and UI stores |
| Services | `api.ts`, `api-real.ts`, `storage.ts`, `notificationStorage.ts` | API surface is still broad and type tightening is needed |
| Composables | 19 composables | Some are domain stores in disguise and should move into Pinia or services |
| Styling | 11 SCSS files, `_components.scss` has 2,525 lines | Token system exists but component ownership is still too diffuse |
| PWA | `main.ts` and `public/push-sw.js` are remaining SW related source hits | Registration is cleaner, device behavior still not proven |
| Realtime | `useWebSocket.ts` and realtime store coexist | Needs a clear boundary between transport service and domain projections |
| Notifications | notification store and storage service exist | Needs final cross channel schema and product surface review |

## Architecture pressure points

| File | Lines | Audit note |
| --- | ---: | --- |
| `app/frontend/src/components/VideoPlayer.vue` | 1786 |
| `app/frontend/src/components/StreamList.vue` | 1770 |
| `app/frontend/src/components/admin/AdminPanel.vue` | 1725 |
| `app/frontend/src/views/SettingsView.vue` | 1354 |
| `app/frontend/src/views/StreamerDetailView.vue` | 1348 |
| `app/frontend/src/views/VideoPlayerView.vue` | 1243 |
| `app/frontend/src/views/HomeView.vue` | 1242 |
| `app/frontend/src/views/LivePlayerView.vue` | 1200 |
| `app/frontend/src/components/settings/ProxySettingsPanel.vue` | 1140 |
| `app/frontend/src/views/VideosView.vue` | 1128 |
| `app/frontend/src/components/settings/RecordingSettingsPanel.vue` | 1110 |
| `app/frontend/src/views/StreamersView.vue` | 1063 |
| `app/frontend/src/components/cards/StreamerCard.vue` | 1055 |
| `app/frontend/src/components/settings/TwitchConnectionPanel.vue` | 987 |
| `app/frontend/src/views/OnboardingWizardView.vue` | 928 |
| `app/frontend/src/components/VideoModal.vue` | 901 |
| `app/frontend/src/App.vue` | 896 |
| `app/frontend/src/components/cards/StreamCard.vue` | 890 |
| `app/frontend/src/components/CleanupPolicyEditor.vue` | 842 |
| `app/frontend/src/components/VideoTabs.vue` | 831 |

## Target architecture direction

1. App.vue should be a thin root only.
2. AppShell, AppHeader, navigation, notification panel, queue panel and PWA prompt should be separate shell features.
3. Pinia should own domain state for realtime, notifications, recordings, streamers, videos, settings, PWA, queue and UI shell state.
4. Services should own API and browser infrastructure.
5. Composables should be browser or reusable UI helpers, not hidden domain stores.
6. Large views should become page orchestrators over smaller feature components.
7. Debug and diagnostics should remain Admin only.

## Current cleanup checks

- Raw browser storage property access was not found in frontend source.
- Stale manual service worker registration files are not present in source hits.
- Debug and diagnostics references still exist, but many are expected in Admin, logger and API layers.
- Several core views still mix data loading, transformation, rendering and responsive behavior.

## Recommended architecture tasks

- Split remaining huge views by feature sections before adding more UI.
- Introduce recording, streamer, video and settings stores.
- Define service boundaries for REST, realtime transport, PWA push, notification persistence and queue.
- Add route meta for product labels, auth shell and navigation behavior.
- Move AdminPanel internals into smaller diagnostics modules.
