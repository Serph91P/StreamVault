# StreamVault frontend inventory

Date: 2026-07-05
Branch: feat/frontend-overhaul-v2
Head: 8766fe23
Base: origin/develop
Frontend path: app/frontend

## Graphify baseline

A fresh code-only Graphify extraction was run against a temporary copy of the current frontend code and config because the full frontend tree includes docs and image assets that require a semantic LLM key. The code graph contains 1,576 nodes and 2,155 edges. The query used was:

`StreamVault frontend AppShell routes views stores realtime notifications PWA service worker design system`

Important Graphify hits from the fresh code graph:

- `SettingsView.vue` imports realtime, events, settings, notification settings, recording settings, PWA panel and multiple settings panels.
- `HomeView.vue`, `StreamerDetailView.vue` and `SettingsView.vue` remain direct realtime consumers.
- Realtime and notification concepts are now present as stores, but several large views still own page orchestration and data shaping.
- The largest remaining UI files are `VideoPlayer.vue`, `StreamList.vue`, `AdminPanel.vue`, `SettingsView.vue`, `StreamerDetailView.vue`, `VideoPlayerView.vue`, `HomeView.vue`, `LivePlayerView.vue`, `VideosView.vue` and `StreamersView.vue`.

Existing reports under `docs/frontend-overhaul-*.md` were read only as historical context. This inventory is based on current `develop` after PR #700.

## Route inventory

| Route | View | Purpose | User goal | Main actions | Components used | Stores/composables used | API dependencies | WebSocket/realtime dependencies | Notification dependencies | PWA dependencies | Styling source | Current UX problems | Current performance problems | Mobile problems | Accessibility problems | Rewrite recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/` | `HomeView.vue` | Dashboard | Understand current live, recording, queue and system status | Open live, streamer detail, videos, queue and notifications | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | rebuild around current feature parity |
| `/welcome` | `OnboardingWizardView.vue` | Welcome | Orient a new user | Continue to app | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | keep |
| `/streamers` | `StreamersView.vue` | Streamer overview | Find streamers and understand live or recording status | Search, filter, open detail, add streamer, force record where available | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | rebuild around current feature parity |
| `/videos` | `VideosView.vue` | Library | Find and play recordings | Search, filter, sort, open player | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | rebuild around current feature parity |
| `/videos/:id` | `VideoPlayerView.vue` | Video player | Play a stored recording and recover from playback issues | Play, seek, retry, inspect metadata | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | rebuild around current feature parity |
| `/subscriptions` | `SubscriptionsView.vue` | Subscriptions | Manage subscribed streamers or channels | Review and update subscriptions | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | keep |
| `/add-streamer` | `AddStreamerView.vue` | Add streamer | Add or import a streamer | Manual add or Twitch import | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | keep |
| `/add-streamer/manual` | `AddStreamerView.vue` | Manual add streamer | Add by username | Validate and save | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | keep |
| `/add-streamer/import` | `AddStreamerView.vue` | Import streamers | Import from Twitch | Fetch, select and import | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | keep |
| `/auth/setup` | `OnboardingWizardView.vue` | Setup | Complete first setup | Configure and continue | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | keep |
| `/onboarding` | `OnboardingWizardView.vue` | Onboarding | Teach core concepts | Complete onboarding | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | keep |
| `/auth/login` | `LoginView.vue` | Login | Authenticate | Sign in | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | keep |
| `/admin` | `AdminView.vue` | Admin Diagnostics | Inspect internals and run diagnostics | View WebSocket monitor, queue internals, test channels | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | capsule diagnostics |
| `/settings` | `SettingsView.vue` | Settings | Configure StreamVault without mixing diagnostics into basic settings | Save recording, notification, PWA, API and proxy settings | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | rebuild around current feature parity |
| `/streamers/:id` | `StreamerDetailView.vue` | Streamer cockpit | Inspect one streamer with status, videos, settings and events | Open live player, update recording settings, open videos | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | rebuild around current feature parity |
| `/streamer/:streamerId/stream/:streamId/watch` | `VideoPlayerView.vue` | Legacy watch route | Preserve older video links | Open player | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | keep |
| `/live/:streamer` | `LivePlayerView.vue` | Live player | Watch live stream and understand HLS or stream status | Play, retry, open streamer context | See source inventory | realtime store, notification store, composables | REST APIs through `api.ts` or `api-real.ts` | central realtime store and `useWebSocket` | notification store and target URLs where relevant | VitePWA, push flow where relevant | SCSS tokens, shared base components and scoped styles | Current source is improved from the prior overhaul, but large view files and mixed local state still make the flow hard to reason about. | Lazy route loading exists. Risk remains in large route chunks, heavy computed state and player initialization. | Bottom navigation exists, but deep flows still need real mobile PWA validation. | Shared components help, but keyboard, focus order and contrast still need manual WCAG pass. | rebuild around current feature parity |

## Views

| View | Lines |
| --- | ---: |
| `AddStreamerView.vue` | 305 |
| `AdminView.vue` | 18 |
| `HomeView.vue` | 1242 |
| `LivePlayerView.vue` | 1200 |
| `LoginView.vue` | 412 |
| `OnboardingWizardView.vue` | 928 |
| `SettingsView.vue` | 1354 |
| `StreamerDetailView.vue` | 1348 |
| `StreamersView.vue` | 1063 |
| `SubscriptionsView.vue` | 736 |
| `TheWelcome.vue` | 22 |
| `VideoPlayerView.vue` | 1243 |
| `VideosView.vue` | 1128 |

## Largest Vue files

| File | Lines |
| --- | ---: |
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

## Stores

- `app/frontend/src/stores/counter.ts`
- `app/frontend/src/stores/notifications.ts`
- `app/frontend/src/stores/realtime.ts`

## Composables

- `app/frontend/src/composables/useAuth.ts`
- `app/frontend/src/composables/useBackgroundQueue.ts`
- `app/frontend/src/composables/useCategoryImages.ts`
- `app/frontend/src/composables/useFilenamePresets.ts`
- `app/frontend/src/composables/useForceRecording.ts`
- `app/frontend/src/composables/useModal.ts`
- `app/frontend/src/composables/useNavigation.ts`
- `app/frontend/src/composables/useNotificationSettings.ts`
- `app/frontend/src/composables/usePWA.ts`
- `app/frontend/src/composables/useProxySettings.ts`
- `app/frontend/src/composables/useRecordingSettings.ts`
- `app/frontend/src/composables/useStreamers.ts`
- `app/frontend/src/composables/useStreams.ts`
- `app/frontend/src/composables/useSwipeNavigation.ts`
- `app/frontend/src/composables/useSystemAndRecordingStatus.ts`
- `app/frontend/src/composables/useTheme.ts`
- `app/frontend/src/composables/useToast.ts`
- `app/frontend/src/composables/useTouchClick.ts`
- `app/frontend/src/composables/useWebSocket.ts`

## Services

- `app/frontend/src/services/api-real.ts`
- `app/frontend/src/services/api.ts`
- `app/frontend/src/services/notificationStorage.ts`
- `app/frontend/src/services/storage.ts`

## Styles

| File | Lines |
| --- | ---: |
| `app/frontend/src/styles/_animations.scss` | 452 |
| `app/frontend/src/styles/_components.scss` | 2525 |
| `app/frontend/src/styles/_glass-system.scss` | 796 |
| `app/frontend/src/styles/_layout.scss` | 1014 |
| `app/frontend/src/styles/_mixins.scss` | 416 |
| `app/frontend/src/styles/_settings-panels.scss` | 364 |
| `app/frontend/src/styles/_tables.scss` | 435 |
| `app/frontend/src/styles/_utilities.scss` | 1565 |
| `app/frontend/src/styles/_variables.scss` | 684 |
| `app/frontend/src/styles/_views.scss` | 996 |
| `app/frontend/src/styles/main.scss` | 666 |

## Current findings

- Product routes are preserved and lazy loaded.
- App.vue is smaller than the original baseline but still 896 lines, so the second pass should verify whether it is only shell orchestration.
- Several core pages still exceed 1,000 lines, which is a strong signal for page level decomposition and design-system consolidation.
- Raw `localStorage` and `sessionStorage` property use is no longer present in frontend source outside wrappers.
- Service worker registrations were reduced to `main.ts` and `public/push-sw.js`, but the PWA strategy still needs browser and device verification.
- Debug strings remain in API, logger, WebSocket, Admin, PWA and settings areas. Some are legitimate diagnostics, but they must stay out of product flows.
