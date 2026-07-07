# Notification Center requirements note

Date: 2026-07-07
Task: t_b4c716b3
Related: B-SPEC-001, UXF-017 screenshot finding
Scope: product and implementation requirements only. No code behavior changed by this note.

## Source facts inspected

- `.hermes/streamvault-ux-audit.md` says notification handling must let the user open Notification Center, filter unread or severity, open a target route or mark read, and on mobile present as a sheet or full route, not a cramped popover.
- `.hermes/streamvault-ux-audit.md` also says cross channel WebSocket, Push and Apprise language needs clearer UI separation, status text must accompany color, Queue and Notifications must not fight with bottom nav, and raw diagnostics must stay out of product flows.
- `.hermes/streamvault-frontend-overhaul-summary.md` says Notification Center already has read state, mark-all-read action, target links and focus behavior.
- `docs/frontend-overhaul-manual-qa-matrix.md` confirms source-level notification persistence and read state exist, but live WebSocket ingestion and real push delivery were blocked without backend or device QA.
- Screenshot evidence inspected: `.hermes/frontend-visual-evidence/notification-center-desktop.png` and `.hermes/frontend-visual-evidence/notification-center-mobile.png`.

## Required user behavior

1. Entry point
   - Keep Notification Center as a global utility from `AppShell.vue`, not a primary route or bottom navigation item.
   - Desktop can remain a modal or side sheet over the current route.
   - Mobile must behave like a top sheet or full-height sheet with body scroll locked while open. It must not become a small popover above the bottom nav.

2. Read and unread state
   - Show unread count on the header bell badge and inside the panel summary.
   - Each unread item must have a non-color-only unread indicator plus stronger surface styling.
   - Support item-level read and unread toggle.
   - Support mark all read.
   - Opening a notification target marks that item read.
   - Clear all removes local items and calls backend clear state.
   - Backend read state is timestamp based. The current backend does not store full notification rows or compute unread counts.

3. Filtering and grouping
   - Required primary filters: All and Unread.
   - Required severity filters: Critical, Errors, Warnings, Success, Info. Disabled severities should remain visible with count 0.
   - Required type filters: derive from event type counts, sorted by count, capped to the most common types.
   - Required grouping: chronological groups named Today, Yesterday, weekday, or Earlier. Group header must show item count and unread count.
   - UXF-017 mobile constraint: filter chips currently form a horizontal scroll row and long type labels can clip near the right edge. Downstream UI work should either keep horizontal chip scrolling intentional with visible affordance and no cut-off content, or collapse type filters behind a compact filter control on narrow widths.

4. Deduplication and retention
   - Deduplicate by `event_id` first, then `dedupe_key`, then fallback `type + timestamp`.
   - If a duplicate arrives, replace the existing item content while preserving read and read_at state.
   - Keep newest notifications sorted first.
   - Retain at most 100 stored notifications in local storage.
   - Non-goal: do not add backend notification history in this frontend task unless a backend task explicitly expands the API contract.

5. Target links and routes
   - Store optional `target_url` per notification.
   - Normalize legacy `/streamer/:id` targets to `/streamers/:id` before navigation.
   - Internal same-origin and root-relative targets route through Vue Router.
   - External targets open in a new tab with noopener and noreferrer.
   - Fallback target generation should use these fields when present:
     - `video_id` to `/videos/:video_id`
     - `streamer_id` to `/streamers/:streamer_id`
     - completed or finished recording with `streamer_id` and `stream_id` to `/streamer/:streamer_id/stream/:stream_id/watch`
   - Items without targets should still be readable, dismissible and markable, but should not look like primary navigation.

6. Event data fields expected by the UI
   - Identity: `event_id`, `dedupe_key`, `type`
   - Display: `severity`, `title`, `body`, `created_at`, `timestamp`
   - Channel: `source`, one of `websocket`, `push`, `apprise`, `system`, `test`
   - Navigation: `target_url`, `actions`
   - Domain context: `streamer_id`, `streamer_name`, `streamer_username`, `recording_id`, `video_id`
   - Extra card context: `data.game_name`, `data.category_name`, stream title or error fields when present

7. Channel distinction
   - WebSocket and realtime are the in-app source of Notification Center items. They arrive through the realtime store and are normalized by `toCanonicalNotificationEvent`.
   - Push is browser or installed PWA delivery. It depends on service worker, permission, subscription and VAPID setup. Push delivery should not be claimed as verified by the panel alone.
   - Apprise is external delivery through configured services such as Discord, Telegram, Slack or email. It is configured in Settings and backend services.
   - Notification Center copy should make this split clear: in-app events arrive live over WebSocket, while external delivery still uses configured Apprise and push targets.
   - Non-goal: do not merge browser push permission setup, Apprise configuration and in-app notification filtering into one control surface.

8. Mobile presentation constraints from UXF-017
   - Header actions must remain 44px touch targets.
   - The panel should be usable at 390px width without horizontal page overflow.
   - Filter chips need intentional horizontal scrolling or a collapsed mobile pattern. Long labels such as Recording Completed must not appear accidentally cut off.
   - Notification items should stack content and actions without forcing a three-column desktop grid on mobile.
   - The sheet must not hide bottom navigation state or compete with Queue. Queue and Notifications remain global utilities.
   - Body scroll must restore when the panel closes, focus should enter the panel on open, Escape and close button should return focus to the bell.

## Existing files downstream implementers should inspect or modify

- `app/frontend/src/components/AppShell.vue`
  - Owns global notification button, unread badge, dialog wrapper, focus trap, close behavior, body scroll lock, mark all read and clear all actions.
- `app/frontend/src/components/NotificationFeed.vue`
  - Owns panel content, grouped list, mark all read, clear all, item open, item read toggle and grouping.
- `app/frontend/src/components/notifications/NotificationFilters.vue`
  - Owns All, Unread, severity and type filter chips. Primary target for UXF-017 mobile filter behavior.
- `app/frontend/src/components/notifications/NotificationItem.vue`
  - Owns item layout, unread dot, severity badge, channel label, target button, read or unread toggle, dismiss action and responsive item styling.
- `app/frontend/src/components/notifications/NotificationState.vue`
  - Owns loading, empty and error states.
- `app/frontend/src/stores/notifications.ts`
  - Owns local notification list, filter state, dedupe, read state, retention and backend sync.
- `app/frontend/src/services/notificationStorage.ts`
  - Owns local storage schema and legacy read migration.
- `app/frontend/src/types/events.ts`
  - Owns realtime event aliases, canonical notification event shape, source labels, target normalization, severity inference and fallback route generation.
- `app/frontend/src/App.vue`
  - Loads notification storage, syncs backend clear state, backfills realtime recent events and subscribes notification-capable realtime event types.
- `app/routes/notifications.py`
  - Backend timestamp state for mark read, clear and state.
- `app/services/notifications/notification_dispatcher.py`
  - Backend sends WebSocket first, then browser push, then external Apprise.
- `app/services/notifications/push_notification_service.py`
  - Browser push delivery and subscription checks.
- `app/services/notifications/external_notification_service.py`
  - Apprise delivery behavior.

## Non-goals for B-SPEC-001 frontend implementation

- Do not introduce a primary notification route unless product asks for it.
- Do not add backend notification history or replay cursor in the frontend slice.
- Do not claim real push delivery or live WebSocket ingestion without backend and device QA.
- Do not expose raw WebSocket payloads, debug JSON, Apprise URLs or service worker internals in the user-facing Notification Center.
- Do not remove existing toast behavior. Toast notifications are transient feedback and Notification Center is persistent in-app history.
