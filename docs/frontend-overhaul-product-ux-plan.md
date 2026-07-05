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
