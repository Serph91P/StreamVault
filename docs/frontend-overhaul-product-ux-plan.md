# StreamVault Product and UX Plan

Date: 2026-07-05
Depends on: `docs/frontend-overhaul-analysis.md`

## Product direction

StreamVault should feel like a modern self-hosted media and recording control center for Twitch streams. The design should be dark-first, calm, technical and status-rich. It should not become a generic admin dashboard.

Core principles:

- Recording and live status are first-class visual signals.
- The app shell must work on desktop and installed mobile PWA.
- Notifications are a product feature, not a debug log.
- Diagnostics live in Admin Diagnostics, not in normal navigation.
- Realtime and Push are separate channels with shared event contracts.
- UI primitives are shared, typed and accessible.

## Final information architecture decision

Source verification: the current router exposes Home, Streamers, Videos, Subscriptions, Settings, Admin, Add Streamer, setup, onboarding, login, streamer detail, video player and live player routes. The current primary navigation is defined in `app/frontend/src/composables/useNavigation.ts` and renders the same five tabs in desktop sidebar and mobile bottom nav: Home, Streamers, Videos, Subs and Settings. App-level notifications and queue controls currently live in `App.vue` header actions and mobile menu, while Admin is routable but outside primary navigation.

Final target model:

| Layer | Desktop target | Mobile/PWA target | Decision |
| --- | --- | --- | --- |
| Primary navigation | Sidebar with Dashboard, Streamers, Library, Subscriptions and Settings | Bottom nav with the same five items | Keep five primary destinations to avoid crowding. Rename Home to Dashboard and Videos to Library in product copy when implementation starts. |
| Global actions | Header icons for Notifications, Queue, PWA update/install and account | Header actions plus sheets launched from badges | Notifications and Queue are global utilities, not primary tabs. |
| Context routes | Streamer detail, live player, video player, add streamer | Full-screen routes with back affordance | Keep as routes because they need deep links and direct notification targets. |
| Secondary settings | Twitch, Recording, Favorites, Proxy, Notifications, PWA, API Keys, Logging | One focused panel per screen with sticky save | Settings is user-facing configuration only. |
| Admin diagnostics | Admin route outside normal primary navigation | Read-mostly diagnostics route reachable from Settings or privileged menu | WebSocket monitor, push tests, queue internals and raw diagnostics belong here, not in user flows. |
| Transient surfaces | Notification popover, Queue panel, PWA update banner | Bottom sheets and banners | Use sheets for temporary tasks that should not reset the user journey. |

Route and surface decisions:

| Surface | Final shape | Primary entry | Deep link target | Notes |
| --- | --- | --- | --- | --- |
| Dashboard | Page | Primary nav | `/` | Operational overview and first landing after auth. |
| Streamers | Page | Primary nav | `/streamers` | Search, filters and bulk status scanning. |
| Add Streamer | Modal-like route or sheet over Streamers | Streamers CTA | `/add-streamer` plus import/manual subroutes | Current routes can remain, but the visual model should feel like a focused task. |
| Streamer detail | Page | Streamer card, notification, search | `/streamers/:id` | Cockpit with tabs and status-specific actions. |
| Live player | Page | Dashboard, streamer detail, streamer card | `/live/:streamer` | Player-first route with status side panel or mobile sheet. |
| Library | Page | Primary nav | `/videos` | Stored recordings browser. |
| Video player | Page | Video card, notification | `/videos/:id` and legacy watch route | Full-screen playback route. |
| Active recordings | Dashboard panel plus optional route later | Dashboard card, Queue panel | Later `/recordings/active` if needed | Start as panel and sheet. Promote only if usage requires a dedicated route. |
| Queue | Panel or sheet | Header badge, Dashboard status strip | No route in first pass | Admin keeps detailed internals. User queue stays concise. |
| Notification Center | Popover or sheet with optional page later | Header bell, mobile menu or badge | Event target URLs, not notification page by default | Product history with filters and read state. Add a page only if history depth needs it. |
| Settings | Page with section navigation | Primary nav | `/settings` | User settings only. Diagnostics link out to Admin. |
| Admin diagnostics | Page | Privileged menu or Settings diagnostics link | `/admin` | Keep outside bottom nav and sidebar primary list. |
| Setup and onboarding | Full-screen flow | Router guard | `/auth/setup`, `/welcome`, `/onboarding` | No WebSocket and no push permission request before explanation. |
| Login | Full-screen flow | Router guard | `/auth/login` | Branded auth card. |
| PWA install and push | Settings panel, prompt, onboarding sheet | Install prompt, Settings, mobile status sheet | Push notification click target URL | Permission request only after user intent. |

## Target journeys

### Journey 1: monitor active recording

1. User lands on Dashboard and sees live, recording, queue and failure summary.
2. User opens an active recording card.
3. Desktop shows player or detail context with a status side panel. Mobile opens the live player route with status in a sheet.
4. Queue progress stays available through the header badge or sheet.
5. Failure events create a notification with a direct target back to the recording, streamer or video.

### Journey 2: manage a streamer

1. User opens Streamers from primary navigation.
2. User searches or filters by live, recording or offline.
3. User opens Streamer detail.
4. Detail page shows profile status, videos, recording settings and event timeline as tabs.
5. Primary actions remain contextual: open live player, open latest video, adjust recording and notification settings.

### Journey 3: find and play a recording

1. User opens Library.
2. User filters by streamer, date, category, processing state or error state.
3. User opens Video player.
4. Playback errors stay in the player route and also create critical notification events when appropriate.
5. Completed recording notifications deep link directly to the video.

### Journey 4: configure notifications and PWA push

1. User opens Settings, then Notifications or PWA.
2. In-app, Web Push and Apprise are separated as settings sections.
3. PWA push explains browser support, service worker state and permission impact before triggering the browser prompt.
4. Permission denied and subscription errors stay in the PWA panel with troubleshooting steps.
5. Admin-only test sends and raw diagnostics move to Admin Diagnostics.

### Journey 5: handle background jobs

1. User sees a queue badge or Dashboard queue summary.
2. User opens the Queue panel or mobile sheet for active and recent jobs.
3. Routine progress stays in the queue UI.
4. Failed jobs create notifications with target links.
5. Detailed internals, retries and post-processing diagnostics stay in Admin.

### Journey 6: first setup and installed app flow

1. Router guard sends unauthenticated or unconfigured users to setup, onboarding or login.
2. Setup uses a full-screen product-branded flow with no normal app chrome.
3. Push permission is not requested during first setup.
4. After setup, Dashboard becomes the first product page.
5. Installed PWA users get safe-area aware navigation, update banners and platform-specific install or push guidance.

## Design review checklist

- Dashboard, Streamers, Streamer detail, Library, live player, video player, Settings, Admin, Notifications, Queue and PWA each have a decided page, panel or sheet shape.
- Primary navigation remains five destinations on desktop and mobile.
- Admin diagnostics are reachable but not mixed into normal user navigation.
- Notifications have read state, filtering, severity, target links and event schema alignment.
- Queue is visible globally but detailed internals stay in Admin.
- Mobile routes use bottom nav for primary destinations and sheets for temporary global surfaces.
- PWA push permission is only requested after explanation and user action.
- Every page has explicit empty, loading and error states before implementation begins.

## 1. Dashboard / Home

| Topic | Plan |
| --- | --- |
| Zweck | Operational overview for active recordings, live streamers, latest videos, failures and queue. |
| Nutzeraktionen | Open live player, open active recording, review latest video, retry or inspect failures, open queue. |
| Statusinfos | Live count, recording count, queue status, failed jobs, latest completed videos, WebSocket state. |
| Desktop | Two-column or three-column dashboard with hero status strip, live/recording cards and side activity panel. |
| Mobile/PWA | Single-column status feed with compact cards and sticky bottom nav. Queue and notifications open as sheets. |
| Empty State | No active streams, clear add-streamer CTA and explanation. |
| Loading State | Skeleton status cards and list skeletons. |
| Error State | Inline retry banner per section, not full-page failure. |
| Realtime | Central realtime store updates live, recording and queue summaries. |
| Notifications | Critical failures appear in Notification Center and toast. Non-critical updates remain in activity feed. |
| Komponenten | AppSection, StatusSummaryCard, LiveStreamerCard, RecordingCard, QueueSummary, ActivityFeed. |
| Stores/Services | realtimeStore, notificationStore, streamers service, recordings service, videos service, queue service. |

## 2. Streamer-Uebersicht

| Topic | Plan |
| --- | --- |
| Zweck | Scan, search, filter and manage streamers. |
| Nutzeraktionen | Add streamer, search, filter live/recording/offline, open detail, start force recording if allowed. |
| Statusinfos | Live, offline, recording, category, current title, last seen, notification enabled. |
| Desktop | Dense card/list toggle with filters top bar. |
| Mobile/PWA | Full-width touch cards, sticky search/filter sheet. |
| Empty State | Add first streamer with Twitch import/manual actions. |
| Loading State | Card skeleton grid. |
| Error State | Retry and backend status hint. |
| Realtime | Stream online/offline/channel update updates cards through central event store. |
| Notifications | Notification setting badges, deep links from notification to streamer detail. |
| Komponenten | StreamerCard, FilterBar, StatusBadge, RecordingIndicator, AddStreamerCTA. |
| Stores/Services | streamerStore, realtimeStore, notificationSettings service. |

## 3. Streamer-Detailseite

| Topic | Plan |
| --- | --- |
| Zweck | One streamer cockpit for profile, current status, settings, latest videos and event history. |
| Nutzeraktionen | Toggle recording settings, start/stop force recording, open live player, open latest video, adjust notifications. |
| Statusinfos | Live state, recording state, current stream title/category, last recordings, recent events. |
| Desktop | Profile header plus tabs: Overview, Videos, Recording Settings, Events. |
| Mobile/PWA | Profile header and segmented tabs. Actions become bottom sheet menu. |
| Empty State | No videos/events yet. |
| Loading State | Header skeleton plus tab skeletons. |
| Error State | Per-section retry and not-found state. |
| Realtime | Updates current status and active recording by streamer id. |
| Notifications | Event timeline uses same canonical notification/event schema. |
| Komponenten | StreamerHero, StatusBadge, RecordingSettingsForm, StreamerTimeline, VideoGrid. |
| Stores/Services | streamerStore, recordingSettings service, video service, realtimeStore. |

## 4. Live-Status / Live Player

| Topic | Plan |
| --- | --- |
| Zweck | Watch live stream or active recording preview with clear technical status. |
| Nutzeraktionen | Play, pause, quality select, codec mode, open Twitch, retry HLS, report issue. |
| Statusinfos | Live/recording/offline, HLS state, codec mode, retry count, latency if available. |
| Desktop | Wide player with side panel for status and events. |
| Mobile/PWA | Player-first layout, controls large enough for touch, status in collapsible sheet. |
| Empty State | Stream is offline, offer streamer detail and latest videos. |
| Loading State | Player skeleton and connection indicator. |
| Error State | HLS error details with retry and fallback. |
| Realtime | Stream offline stops live status, recording updates remain visible. |
| Notifications | Critical playback or recording failures create notification event. |
| Komponenten | LivePlayerShell, PlayerStatusBar, HlsErrorPanel, CodecSelector. |
| Stores/Services | live service, realtimeStore, playback composable, auth token service. |

## 5. Recordings / Videos / Mediathek

| Topic | Plan |
| --- | --- |
| Zweck | Browse and play stored recordings. |
| Nutzeraktionen | Search, filter, sort, open player, delete if allowed, view metadata. |
| Statusinfos | Duration, streamer, date, category, processing state, errors. |
| Desktop | Responsive grid/list with filters and detail preview. |
| Mobile/PWA | Compact cards, filter sheet, native-feeling player route. |
| Empty State | No videos yet, explain recording setup. |
| Loading State | Grid skeleton. |
| Error State | Retry and partial results support. |
| Realtime | Recording completed/available adds or updates video card. |
| Notifications | Click from recording completed opens video. |
| Komponenten | VideoCard, MediaGrid, FilterBar, VideoMetadata, EmptyState. |
| Stores/Services | videos service, realtimeStore, notificationStore. |

## 6. Recording-Status / aktive Recordings

| Topic | Plan |
| --- | --- |
| Zweck | Show active recordings and processing state. |
| Nutzeraktionen | Open streamer, open live player, inspect output, cancel if allowed. |
| Statusinfos | Recording duration, path, streamer, title, processing queue, errors. |
| Desktop | Dashboard panel and optional dedicated route. |
| Mobile/PWA | Sheet from dashboard or bottom nav badge. |
| Empty State | No active recordings. |
| Loading State | Active recording skeleton rows. |
| Error State | Failed status with reason and next action. |
| Realtime | Active recordings update, recording started/stopped/completed. |
| Notifications | Failed and completed events link to detail/video. |
| Komponenten | ActiveRecordingCard, RecordingTimeline, StatusBadge. |
| Stores/Services | recordingStore, realtimeStore, queue service. |

## 7. Background Jobs / Queue

| Topic | Plan |
| --- | --- |
| Zweck | Observe and manage background tasks. |
| Nutzeraktionen | Inspect active/recent jobs, cancel stream tasks, refresh fallback. |
| Statusinfos | Running, queued, completed, failed, retry count, progress. |
| Desktop | Header badge and right panel, Admin page for details. |
| Mobile/PWA | Bottom sheet with active jobs first. |
| Empty State | No active jobs. |
| Loading State | Row skeletons. |
| Error State | Queue unavailable with REST fallback. |
| Realtime | Queue stats and task status updates via realtimeStore. |
| Notifications | Failed jobs create notification; routine progress stays in queue UI. |
| Komponenten | QueuePanel, QueueTaskRow, ProgressBadge. |
| Stores/Services | queueStore, realtimeStore, queue API. |

## 8. Notification Center

| Topic | Plan |
| --- | --- |
| Zweck | Durable in-app history of important stream, recording, system and queue events. |
| Nutzeraktionen | Mark read/unread, filter, clear, open target, inspect details. |
| Statusinfos | Severity, type, time, source, read state, dedupe state. |
| Desktop | Header popover plus full page or right panel. |
| Mobile/PWA | Bottom sheet or dedicated notification route. |
| Empty State | All caught up with explanation. |
| Loading State | Timeline skeleton. |
| Error State | Storage/backend sync warning and retry. |
| Realtime | WebSocket events add/update notification history while app is open. |
| Notifications | Web Push opens target route and syncs notification as read if backend supports it. |
| Komponenten | NotificationCenter, NotificationItem, NotificationFilters, NotificationBadge. |
| Stores/Services | notificationStore, realtimeStore, storage service, backend notification API. |

## 9. Settings

| Topic | Plan |
| --- | --- |
| Zweck | User-facing configuration grouped by domain. |
| Nutzeraktionen | Configure Twitch, recording, favorites, proxy, notifications, PWA push, API keys. |
| Statusinfos | Connection status, enabled states, validation, last saved. |
| Desktop | Section sidebar with focused panels. |
| Mobile/PWA | Segmented categories, one panel per screen, sticky save actions. |
| Empty State | Per-panel not configured state. |
| Loading State | Panel skeleton. |
| Error State | Field-level and panel-level errors. |
| Realtime | Settings should not depend on WebSocket except status indicators. |
| Notifications | Separate tabs: In-app, Web Push, Apprise, Diagnostics. |
| Komponenten | SettingsShell, SettingsPanel, FormField, SaveBar, DiagnosticsCard. |
| Stores/Services | settings service, notificationSettings service, pwa service. |

## 10. Admin

| Topic | Plan |
| --- | --- |
| Zweck | Technical diagnostics and privileged operations. |
| Nutzeraktionen | Inspect WebSocket connections, queue internals, post-processing, push diagnostics. |
| Statusinfos | System health, logs, debug endpoint results. |
| Desktop | Dense admin panels with clear danger zones. |
| Mobile/PWA | Read-mostly diagnostics, no cramped tables. |
| Empty State | No diagnostics available. |
| Loading State | Table and panel skeletons. |
| Error State | Endpoint unavailable with raw diagnostic details. |
| Realtime | WebSocket monitor belongs here if retained. |
| Notifications | Test push and test websocket actions live here or in Admin Diagnostics. |
| Komponenten | AdminDiagnostics, WebSocketMonitor, PushDiagnostics, QueueAdmin. |
| Stores/Services | admin service, diagnostics service. |

## 11. Auth / Setup / Onboarding

| Topic | Plan |
| --- | --- |
| Zweck | Focused setup and login flow. |
| Nutzeraktionen | Login, first setup, Twitch connection, recording setup, welcome completion. |
| Statusinfos | Auth state, setup progress, Twitch token status. |
| Desktop | Centered auth card with product branding. |
| Mobile/PWA | Full-screen app-like setup with safe areas. |
| Empty State | Not applicable. |
| Loading State | Button loading and step skeleton. |
| Error State | Clear auth/setup errors, no loop reloads. |
| Realtime | No WebSocket on auth/setup routes. |
| Notifications | Do not request push permission during first setup before explanation. |
| Komponenten | AuthLayout, SetupWizard, OnboardingStep, AuthCard. |
| Stores/Services | auth composable, setup service. |

## 12. PWA Install / PWA Status / Push Permission Flow

| Topic | Plan |
| --- | --- |
| Zweck | Help users install StreamVault and enable background push correctly. |
| Nutzeraktionen | Install PWA, review status, enable push, unsubscribe, troubleshoot. |
| Statusinfos | Installed, standalone, online/offline, SW registered, update available, permission state, subscription state. |
| Desktop | Settings panel plus install prompt when eligible. |
| Mobile/PWA | Friendly onboarding sheet with platform-specific steps for Android and iOS. |
| Empty State | Browser not supported with alternatives. |
| Loading State | Checking support/subscription. |
| Error State | Permission denied, VAPID missing, subscription failed, invalid subscription. |
| Realtime | Online/offline and reconnect banners visible in app shell. |
| Notifications | Permission request only after explanation and user click. Push click deep links into the app. |
| Komponenten | PWAStatusPanel, PushPermissionCard, InstallPrompt, UpdateAvailableBanner. |
| Stores/Services | pwaStore or usePWA refactor, service worker service, push API. |

Push click platform notes:

- Android Chrome shows Web Push notifications for installed PWAs and browser tabs after the user grants notification permission. A click should focus an existing StreamVault tab when possible, then route in-app through the service worker `navigate` message.
- iOS and iPadOS Web Push requires Safari 16.4 or newer and a StreamVault app installed from Share > Add to Home Screen. Browser tabs alone do not receive Web Push.
- Notification payloads should prefer `data.target_url`, then `data.internal_url`, then `data.url`. Legacy streamer links shaped as `/streamer/:id` are normalized to `/streamers/:id`; recording watch links shaped as `/streamer/:streamerId/stream/:streamId/watch` remain supported by the current router.
- Manual verification matrix: Android Chrome installed PWA, Android Chrome browser tab, iOS or iPadOS Home Screen app, and unsupported iOS browser tab. If a platform is unavailable, document it as unverified rather than marking it passed.

## Cross-cutting target architecture

- `stores/realtime.ts`: owns connection, event stream, connection state, dedupe and future replay.
- `stores/notifications.ts`: owns in-app notifications, read/unread, filters, actions and persistence adapter.
- `services/storage.ts`: wraps localStorage and possible IndexedDB use.
- `types/events.ts`: typed `RealtimeEvent` and `NotificationEvent` unions.
- `components/app/AppShell.vue`: owns layout only.
- `components/app/AppHeader.vue`: owns header actions only.
- `components/notifications/NotificationCenter.vue`: product notification surface.
- `components/pwa/PWAStatus.vue`: install, update and push state.
- `components/ui/*`: stable primitives for Button, Card, Modal, Drawer, Sheet, Table, Badge and FormField.

## Realtime replay backend gap

KAN-015 source check found the current backend WebSocket endpoint at `app/main.py` `/ws` only accepts a live socket and keeps it open. `ConnectionManager` broadcasts events directly to active sockets and does not persist an event log, expose event ids, or provide a `since` cursor/replay endpoint. The frontend can show reconnect state, retry on online and visible events, refresh REST-backed status after reconnect, and dedupe repeated live events, but missed-event replay needs backend support for durable event ids and a replay API.
