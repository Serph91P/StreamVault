# Dashboard UX Overhaul Implementation Plan

Date: 2026-07-06
Task: `t_ce296709`
Scope: `/` route only, preserving Dashboard feature parity.

## Goal

Make the Dashboard understandable within 3 seconds on desktop and mobile by turning the current operational data into a clear status hierarchy: live, recording, queue, errors, and recent activity. Use status visibility, JTBD, and performance UX. Do not add a debug wall or expose raw internals on the dashboard.

## Current source findings

- `app/frontend/src/views/HomeView.vue` already owns the `/` dashboard route, fetches streamers, videos, active recordings, queue fallback data, and subscribes to realtime stream, recording, queue, and task events.
- The route already has a hero, `dashboard-brief`, `StatusCard` metrics, live streamer panel, active recordings panel, latest videos panel, queue panel, failures panel, and realtime activity panel.
- The current layout duplicates the first read across `dashboard-brief` and `summary-section`. This helps visibility but creates scanning noise before the user reaches live, recording, queue, error, and activity details.
- Mobile behavior currently stacks the main and sidebar columns at `xl`, uses a two-column brief grid at `md`, and single-column stats at `sm`. The plan should keep this responsive direction but make the first mobile viewport contain the status answer plus the most urgent action.

## UX decision

Use one top-level operational snapshot as the first-read layer, then keep the existing detail panels as the second-read layer.

1. First read, within 3 seconds:
   - A single headline explains the highest priority state.
   - Five compact status tiles answer: live count, recording count, queue state, errors, latest activity.
   - One primary action jumps to the highest priority section.
2. Second read:
   - Live and active recording details stay in the main column.
   - Queue, errors, and activity stay in the right rail on desktop and below primary content on mobile.
3. Priority order:
   - Errors first.
   - Live streamers second.
   - Active recordings third.
   - Queue work fourth.
   - Quiet state last.
4. Non-goal:
   - No debug wall, raw WebSocket log, raw queue dump, or admin diagnostics inside Dashboard. Detailed internals remain in Admin or the global queue panel.

## Implementation tasks

### Task 1: Consolidate the first-read dashboard snapshot

Files:

- Modify: `app/frontend/src/views/HomeView.vue`
- Likely no new component unless the markup grows. If extracted, create `app/frontend/src/components/dashboard/DashboardStatusSnapshot.vue`.

Steps:

1. Keep the existing `dashboardStateHeadline`, `dashboardStateDescription`, `dashboardStatusLine`, `primaryAction`, and `dashboardBriefItems` computed values as the single source of truth.
2. Remove or demote the duplicate `summary-section` metric row from the initial viewport. If product wants to keep all five `StatusCard` metrics, move them below the first detail row or make them a compact secondary row after the brief.
3. Ensure the five snapshot items use text plus icon and not color alone:
   - Live: online count and tracked count.
   - Recording: active recording count and recording streamer count.
   - Queue: state label plus active and pending counts.
   - Errors: alert count plus no-alert state.
   - Recent activity: event count plus latest event title.
4. Keep the primary action behavior in `handleDashboardPrimaryAction`, scrolling to live, recordings, queue, failures, or routing to `/videos`.

Acceptance checks:

- Desktop first viewport shows headline, all five status categories, and one action without needing the user to parse detailed cards.
- Mobile first viewport shows headline, at least the highest priority action, and all five category answers without horizontal overflow.
- Dashboard route still fetches streamers, videos, active recordings, and queue fallback data.

### Task 2: Make active states visually scannable without changing data contracts

Files:

- Modify: `app/frontend/src/views/HomeView.vue`
- Reuse: `app/frontend/src/components/base/StatusBadge.vue`
- Reuse: `app/frontend/src/components/base/BasePanel.vue`
- Reuse: `app/frontend/src/components/EmptyState.vue`
- Reuse: `app/frontend/src/components/LoadingSkeleton.vue`

Steps:

1. For the live panel, keep `StreamerCard` and the existing `force-record` behavior. Add only dashboard-local section copy or panel action changes needed to clarify why the section matters.
2. For active recordings, keep the existing card links to `recordingStreamerLink` and `recordingLiveLink`. Add duration or started-time copy only from existing `started_at` or `created_at` fields. Do not add a new API call.
3. For queue, keep `queueStats`, `activeTasks`, `recentTasks`, `totalProgress`, `queueStateLabel`, and `queueBadgeTone`. Show active, pending, failed, and workers with labels. Keep the fallback refresh button but make the copy user-facing, for example `Refresh queue status` instead of `Refresh queue fallback`.
4. For errors, keep `failureItems` built from failed queue tasks and critical or error realtime events. Make the zero state clearly positive and the non-zero state clearly actionable.
5. For recent activity, keep `recentActivity` limited to 6 events and reversed newest first. Keep severity badge text visible.

Acceptance checks:

- Live, recording, queue, errors, and recent activity each have an empty, loading or error path where applicable.
- Existing dashboard actions still work: add streamer, open library, force record, open streamer, open live, refresh queue, retry failed loads.
- No raw event payloads, task JSON, or backend debug fields appear on the dashboard.

### Task 3: Desktop layout behavior

Files:

- Modify: `app/frontend/src/views/HomeView.vue` scoped styles.
- Reference: `app/frontend/src/styles/_variables.scss` and `app/frontend/src/styles/main.scss` for existing tokens only.

Steps:

1. Keep the current desktop grid idea: `dashboard-main` as the primary content column and `dashboard-sidebar` as the secondary status column.
2. On desktop, order content as:
   - Snapshot at top.
   - Main column: Live Streamers, Active Recordings, Latest Videos.
   - Sidebar: Queue, Failures and Alerts, Realtime Activity.
3. Make the sidebar visually subordinate but sticky only if it does not conflict with app shell scrolling. If sticky is risky, skip it.
4. Keep density calm: avoid adding more cards than the current five status answers plus detail panels.
5. Use current tokens and primitives. Do not add new CSS custom properties.

Acceptance checks:

- At 1440px, the user can identify whether anything is live, recording, queued, failing, or recently changed from the top of the route.
- The sidebar does not compete with the live and recording panels.
- No new horizontal overflow is introduced.

### Task 4: Mobile layout behavior

Files:

- Modify: `app/frontend/src/views/HomeView.vue` scoped styles.
- Reference: `app/frontend/src/components/navigation/BottomNav.vue` only if spacing changes collide with bottom nav safe area.

Steps:

1. Preserve the existing breakpoint behavior that collapses `dashboard-layout` to one column below `xl`.
2. Below `md`, make the snapshot action full width and keep touch targets at least 44px.
3. Keep the status tile grid at two columns below `md` with the Recent activity tile full width, or switch to one column below `sm` if text truncates.
4. Keep the detail order mobile-friendly:
   - Snapshot.
   - Live Streamers.
   - Active Recordings.
   - Queue.
   - Failures and Alerts.
   - Realtime Activity.
   - Latest Videos can remain before the sidebar sections only if the implementer confirms the top mobile question is still answered within the first viewport.
5. Do not introduce a separate mobile debug menu or duplicate queue wall.

Acceptance checks:

- At 390px, the first screen answers the highest priority state and exposes a clear next action.
- No status tile requires horizontal scrolling.
- Queue and notifications remain global utilities, not primary mobile tabs.

### Task 5: Verification and QA

Files:

- `app/frontend/src/views/HomeView.vue`
- Any new `app/frontend/src/components/dashboard/*` file if extraction is used.

Commands:

```bash
cd app/frontend
npm run lint
npm run type-check
npm run build
```

Manual checks:

- Desktop viewport around 1440px on `/`.
- Mobile viewport around 390px on `/`.
- States to cover with mock data or controlled API responses: all quiet, live streamer present, active recording present, queue active or pending, failed queue task, critical realtime event, no recordings yet, API error retry.
- Verify no forbidden dash characters were added in touched files with `grep -rP "[\x{2013}\x{2014}]" <touched-files>`.

## Exact files likely to change

Primary:

- `app/frontend/src/views/HomeView.vue`

Possible extraction if `HomeView.vue` becomes harder to scan:

- `app/frontend/src/components/dashboard/DashboardStatusSnapshot.vue`
- `app/frontend/src/components/dashboard/DashboardQueueSummary.vue`
- `app/frontend/src/components/dashboard/DashboardActivityList.vue`

Files to reuse, not rewrite:

- `app/frontend/src/components/base/BasePanel.vue`
- `app/frontend/src/components/base/StatusBadge.vue`
- `app/frontend/src/components/EmptyState.vue`
- `app/frontend/src/components/LoadingSkeleton.vue`
- `app/frontend/src/components/cards/StreamerCard.vue`
- `app/frontend/src/components/cards/VideoCard.vue`
- `app/frontend/src/stores/realtime.ts`
- `app/frontend/src/services/api.ts`
- `app/frontend/src/services/api-real.ts`

## Definition of done

- Dashboard keeps feature parity: live streamers, active recordings, queue, failures, latest videos, realtime activity, add streamer, library, retry, force record, streamer link, live link, and queue refresh remain available.
- Within 3 seconds, desktop and mobile users can answer: what is live, what is recording, what is queued, what is broken, and what just happened.
- Mobile layout explicitly supports 390px width with no horizontal overflow and 44px action targets.
- Desktop layout keeps the current primary plus sidebar hierarchy without adding a debug wall.
- All checks listed above pass or have a documented blocker with command output.
