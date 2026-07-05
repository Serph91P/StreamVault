# StreamVault frontend inventory

Date: 2026-07-05
Branch: feat/frontend-overhaul-plan
Base branch: develop
Frontend path: app/frontend
Graphify source: /opt/data/workspace/github_repos/StreamVault/graphify-out/graph.json
Graphify query used: StreamVault frontend architecture Vue routes views components stores composables PWA service worker notifications WebSocket design system

## Graphify and source baseline

Graphify was read before implementation from the sibling StreamVault graph. The graph exposed App.vue, NotificationFeed.vue, useWebSocket.ts, PWA files and backend WebSocket services as central nodes. The graph query returned broad WebSocket and notification nodes, so every finding below was verified against the worktree source.

Key source facts:

- Vue 3, Vite, TypeScript, Pinia, Vue Router, SCSS, VitePWA, Workbox and hls.js remain the stack.
- Routes are lazy loaded from app/frontend/src/router/index.ts.
- Product state is now projected through Pinia stores for realtime and notifications.
- PWA registration uses VitePWA virtual:pwa-register as the single frontend registration owner.
- Stale public service worker artifacts, public PWA tester files, public FontAwesome assets and the old product notification dashboard were removed.

## Route inventory

| Route | View | Purpose | User goal | Main actions | Components | Stores or composables | API dependencies | Realtime | Notifications | PWA | Styling source | UX issues found | Performance issues found | Mobile issues found | Accessibility issues found | Rewrite recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| / | HomeView.vue | Dashboard | Understand system, live, recording, queue and failures fast | Open streamer, open live, open video, inspect queue | StatusCard, SurfaceCard, StatusBadge, NotificationState, BackgroundQueueMonitor | realtime store, notifications store, useSystemAndRecordingStatus, useBackgroundQueue | systemApi, streamers, recordings, videos | active recordings, stream state, queue updates | critical activity and event feed | install prompt and reconnect banner visible in shell | tokens, SurfaceCard, status badges | Old home mixed summary widgets without clear hierarchy | Large status updates and list loading needed skeletons | Needed one column status feed and touch targets | Status needed text, not only color | replace |
| /streamers | StreamersView.vue | Streamer overview | Find streamer and act on current status | Search, filter, sort, open detail, force record | StreamerCard, BaseSheet, StatusBadge, EmptyState | realtime store, useForceRecording, useStreams | streamersApi | live, offline, recording reconciliation | target links to streamer detail | mobile sheet filters | tokens, cards, badges | Old list was dense and not clearly status first | Filtering and card updates needed localized state | Filters and actions needed sheet or full width cards | Filter controls needed labels and clear focus | rebuild |
| /streamers/:id | StreamerDetailView.vue | Streamer cockpit | Inspect one streamer, videos, settings and events | Open live, open video, change recording settings | SurfaceCard, StatusBadge, VideoCard, Recording settings fields | realtime store, notification store, useRecordingSettings | streamersApi, recording settings, videos | per streamer status and recording events | event timeline and target links | mobile tab layout | tokens, tabs, cards | Old detail page carried too many sections at once | Heavy page needed tabs and skeletons | Actions needed sheet or compact controls | Tabs, buttons and errors needed semantic labels | rebuild |
| /videos | VideosView.vue | Library | Find and play stored recordings | Search, filter, sort, open player | VideoCard, EmptyState, LoadingSkeleton | video services, realtime store | videos endpoints | recording completed updates | completed and failed recording targets | standalone PWA route | media card styles | Old videos felt like generic cards | Thumbnails and grid needed lazy loading and stable card height | Filter controls needed mobile sheet behavior | Missing files and errors needed clear text | rebuild |
| /videos/:id | VideoPlayerView.vue | Stored video playback | Watch a recording and recover from playback issues | Play, seek, retry, inspect metadata | VideoPlayer, PlayerStatus, PlayerError | player composables, auth token flow | video file and metadata endpoints | no direct dependency except related status | notification deep links open this route | route works in standalone mode | player styles and status components | Error state was technical and scattered | HLS/player should initialize only on route | Controls needed touch size | Player errors needed actionable labels | rebuild focused |
| /live/:streamer | LivePlayerView.vue | Live playback | Watch live stream with status context | Play, retry HLS, open streamer, inspect status | VideoPlayer, PlayerStatus, PlayerError | realtime store, useWebSocket, auth token flow | live and streamer endpoints | stream status and recording state | failures can create notifications | mobile player first layout | player styles and sheets | Old layout mixed technical HLS state with product state | HLS should lazy initialize, avoid full page reloads | Status needed collapsible sheet | HLS errors needed readable recovery | rebuild focused |
| /subscriptions | SubscriptionsView.vue | Subscriptions | Manage subscribed streamers or watched channels | View, update, open streamer | SubscriptionManager, cards | existing composables | subscription endpoints | optional stream status | target links optional | normal app shell | existing page styles | Needed to fit IA as primary destination | List needs loading states | Cards over desktop tables | Labels and keyboard order must remain | keep and align |
| /settings | SettingsView.vue | User settings | Configure recording, notifications, PWA, API keys and storage safely | Save, test where safe, reset, open diagnostics | Settings panels, PWAPanel, ApiKeysPanel, FormField, BasePanel | usePWA, useRecordingSettings, useProxySettings, storage service | settings, push, apprise, API key endpoints | settings updates can affect realtime | notification settings and push status | push permission and subscription flow | panel and form tokens | Old settings mixed basic, advanced and diagnostics | Huge settings wall needed sections and progressive disclosure | Panels needed better stacking and sticky actions | Form labels and error messages required consistency | rebuild grouped |
| /admin | AdminView.vue | Admin diagnostics | Inspect diagnostics without leaking debug into product flows | Run diagnostics, inspect queue, test channels | AdminPanel, WebSocketMonitor, BackgroundQueueAdmin | useWebSocket, realtime store | admin, diagnostics, queue, notification test endpoints | raw WebSocket monitor stays here | channel test cards stay here | PWA diagnostics stay admin only | admin panel styles | Debug UI belonged here, not product flows | Diagnostics can be heavy but admin only | Read mostly mobile layout acceptable | Raw diagnostics need labels and readable status | keep and capsule |
| /add-streamer, /add-streamer/manual, /add-streamer/import | AddStreamerView.vue | Add streamer | Add or import streamers | Manual add, Twitch import, validate | AddStreamerForm, TwitchImportForm, BaseButton, FormField | useStreamers, useToast | streamer add and import endpoints | status appears after add | success or failure notifications | standalone route | forms and cards | Flow should feel focused instead of generic page | Form submission should not reload | Import/manual need mobile step layout | Required labels and errors | rebuild visual shell |
| /auth/setup, /welcome, /onboarding | OnboardingWizardView.vue | Setup and onboarding | Complete first setup and understand app | Configure, continue, finish | Onboarding wizard components | router guard, setup state | /auth/setup | no live realtime before setup | no push permission before explanation | PWA install after setup only | auth layout styles | Push must not appear too early | Keep fast first paint | Full screen mobile flow | Focus and errors in wizard | keep and polish |
| /auth/login | LoginView.vue | Authentication | Sign in | Login, retry | Login card | auth composables | /auth/check and login endpoints | none | auth failures only | standalone safe | auth styles | Need branded product entry | Avoid blocking shell load | Mobile card fit | Form labels and errors | keep and polish |
| /streamer/:streamerId/stream/:streamId/watch | VideoPlayerView.vue | Legacy video route | Preserve existing deep links | Watch recording | VideoPlayer | player composables | legacy watch route | no direct dependency | legacy notification target fallback | route compatibility | player styles | Legacy naming conflicts with /streamers/:id | Lazy loaded | Works as full route | Needs same player accessibility | keep as compatibility |

## Component, store, composable and service inventory

| Area | Files and modules | Current role | Overhaul action |
| --- | --- | --- | --- |
| App shell | App.vue, components/app/AppShell.vue, AppHeader.vue, AppNotificationCenter.vue | Global shell, header, panels, realtime banners | App.vue reduced, shell components own layout |
| Navigation | useNavigation.ts, NavigationWrapper.vue, SidebarNav.vue, BottomNav.vue | Shared desktop sidebar and mobile bottom nav | Five primary destinations, header utilities for queue and notifications |
| Design primitives | BaseButton, BasePanel, BaseSheet, BaseTable, FormField, StatusBadge, SurfaceCard | Common UI grammar | Added and documented primitive ownership |
| Icons | IconSprite.vue, SvgIcon.vue | Internal SVG sprite policy | Removed public icons.svg and FontAwesome assets |
| Realtime | useWebSocket.ts, stores/realtime.ts, types/events.ts | Singleton connection plus central projection | Added typed listeners, dedupe, reconnect and replay awareness |
| Notifications | stores/notifications.ts, services/notificationStorage.ts, NotificationFeed.vue, notification item/filter/state components | Product notification center | Added canonical event, read state, filters, deep links |
| PWA | main.ts, usePWA.ts, PWAPanel.vue, public/push-sw.js, backend SW route | Install, update, push and notificationclick | Removed duplicate registrations and public generated SW |
| Storage | services/storage.ts | Central browser storage wrapper | Replaced scattered raw storage use in frontend source |
| Settings | SettingsView and settings panels | User configuration | Grouped user settings and moved diagnostics to admin |
| Admin diagnostics | AdminPanel, WebSocketMonitor, BackgroundQueueAdmin | Debug and diagnostics | Kept outside product navigation |
| Players | VideoPlayer, LivePlayerView, VideoPlayerView, player status/error components | HLS and media playback | Added product error and status components |

## Debug, legacy and experiment paths

| Path | Finding | Final decision |
| --- | --- | --- |
| app/frontend/public/sw.js | Committed generated Workbox file with stale assets | Removed |
| app/frontend/public/registerSW.js | Manual registration competing with VitePWA | Removed |
| app/frontend/public/pwa-test.html | Product exposed test page | Removed |
| app/frontend/public/pwa-helper.js | Old helper path | Removed |
| app/frontend/public/assets/fa-* | Orphan FontAwesome assets after icon migration | Removed |
| app/frontend/src/views/PWATester.vue | PWA test view | Removed |
| app/frontend/src/components/NotificationsDashboard.vue | Experiment dashboard | Removed |
| WebSocketMonitor.vue | Useful diagnostic | Kept in Admin Diagnostics |
| AdminPanel channel tests | Useful diagnostic | Kept admin only |

## Rewrite summary

- Keep: Vue stack, router, auth/setup routes, subscriptions, backend push and Apprise separation.
- Rebuild: Dashboard, Streamers, Streamer detail, Notification Center, Settings IA, App shell.
- Replace: raw notification localStorage ownership, duplicate PWA registrations, public generated service worker artifacts, FontAwesome public assets.
- Capsule: WebSocket monitor, push tests, raw diagnostics and queue internals in Admin Diagnostics.
