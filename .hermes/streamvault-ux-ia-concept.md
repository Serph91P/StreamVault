# StreamVault UX concept and information architecture

Date: 2026-07-05
Branch: feat/frontend-overhaul-v2
Task: KAN2-002
Base: current frontend after the phase 1 inventory

## Source basis

This concept uses the phase 1 Graphify result and then verifies the decisions against current source files.

Graphify and source facts consumed:

- Phase 1 Graphify found 1,576 frontend code nodes and 2,155 edges for the current frontend snapshot.
- The route map in `app/frontend/src/router/index.ts` preserves Dashboard, Streamers, Library, Subscriptions, Add Streamer, Setup, Onboarding, Login, Admin, Settings, Streamer Detail, stored player, legacy watch route and Live Player.
- `app/frontend/src/composables/useNavigation.ts` currently defines Dashboard, Streamers, Library, Subscriptions and Settings as shared desktop and mobile primary tabs.
- `app/frontend/src/components/navigation/NavigationWrapper.vue` already separates desktop sidebar from mobile bottom navigation and uses safe area padding.
- `app/frontend/src/components/NotificationFeed.vue` already models unread counts, filters, target links, empty states and clear actions.
- `app/frontend/src/components/BackgroundQueueMonitor.vue` already exposes jobs, active recordings, recent tasks and failures, but it behaves as a global panel rather than a full IA destination.
- `app/frontend/src/stores/realtime.ts` and `app/frontend/src/stores/notifications.ts` are existing domain anchors for realtime and notification state.

## Product target

StreamVault should feel like a self hosted streaming and recording control center with a media library, not like an admin template or test bench.

The UI target is:

- Status first: live, recording, queue, failed, completed, offline and reconnecting are visible in plain language.
- Media native: recordings and players feel like a small media app, with useful metadata and recoverable playback errors.
- Monitoring aware: system, queue and diagnostics are easy to reach, but diagnostic detail does not dominate normal product flows.
- PWA first: installed mobile use is a first class path with bottom navigation, safe area support, sheets and clear push permission copy.
- Progressive by default: primary status and primary actions appear first, details, advanced settings and diagnostics stay one level deeper.

Non goals for implementation tasks:

- Do not remove a productive route from `.hermes/streamvault-feature-parity-map.md`.
- Do not turn this into a cosmetic button cleanup.
- Do not expose raw debug walls in Dashboard, Streamers, Library or Settings.
- Do not request push permission before the user understands value and consequence.

## Jobs to be Done

| Job | Trigger | Desired outcome | Primary destination | Supporting surfaces | Design rule |
| --- | --- | --- | --- | --- | --- |
| Monitor StreamVault health | User opens the app | Understand live, recording, queue, errors and connection state in under 3 seconds | Dashboard | Header status, Queue panel, Notification Center | Put status cards above detail lists |
| Know who is live | A streamer may be online | Identify live and recordable streamers quickly | Streamers | Dashboard live strip, Streamer Detail, Live Player | Use text plus icon plus color for status |
| Follow a recording | A recording is active or failed | See progress, owner, age, queue state and recovery action | Dashboard and Queue | Streamer Detail, Notification target links | Active recording is a product concept, not only a queue row |
| Start or adjust recording | User wants control over capture | Make the safe action obvious and risky changes confirmed | Streamer Detail | Streamers, Settings | Contextual actions near the streamer, advanced settings grouped away |
| Find a stored video | User wants to watch or verify a recording | Search, filter and play with recoverable error states | Library | Streamer Detail, Video Player | Media grid on wide screens, responsive list on mobile |
| Understand notifications | Something changed while user was away | Review what happened, filter, open target, mark read | Notification Center | Header badge, mobile sheet, target route | Notifications are events with target routes, not toasts only |
| Use StreamVault as mobile PWA | User launches installed app | Navigate with thumb, understand offline or reconnecting state, receive push | Bottom nav | PWA panel, Push flow, Notification target links | Mobile is equal to desktop, not reduced desktop |
| Configure safely | User changes behavior | Find the right section, understand impact, save or cancel | Settings | Admin Diagnostics for expert checks | Basic settings before advanced and dangerous options |
| Diagnose a failure | Recording, websocket or push fails | See user readable reason first and raw detail only when needed | Dashboard error card, Notification target, Admin Diagnostics | Queue panel, Settings diagnostics link | Product recovery first, raw diagnostics second |

## Information architecture

### Primary destinations

| Destination | Route | User question | Required content | Implementation owner |
| --- | --- | --- | --- | --- |
| Dashboard | `/` | What is happening now and what needs attention? | System status, live streamers, active recordings, critical failures, recent videos, compact jobs, quick actions | Core pages overhaul |
| Streamers | `/streamers` | Who do I follow and what is their state? | Search, filters, live/offline/recording status, add streamer, force record where available | Core pages overhaul |
| Library | `/videos` | What was recorded and can I play it? | Search, filters, responsive video cards, processing and missing file states | Core pages overhaul |
| Subscriptions | `/subscriptions` | Which subscriptions are managed? | Existing subscription management until a later IA merge is proven safe | Feature parity |
| Settings | `/settings` | How do I configure StreamVault safely? | Recording, Streamers/Twitch, Notifications, PWA/Push, Storage, System, Advanced, Diagnostics link | Settings overhaul |
| Admin Diagnostics | `/admin` | What does an expert need to debug? | WebSocket monitor, queue internals, debug helpers, raw diagnostics | Admin capsule |

### Secondary and context routes

| Route | IA role | Entry points | Rule |
| --- | --- | --- | --- |
| `/streamers/:id` | Streamer cockpit | Streamers, Dashboard, notifications, live player | Prefer tabs or sections: Overview, Recordings, Settings, Events |
| `/add-streamer`, `/add-streamer/manual`, `/add-streamer/import` | Add flow | Streamers primary action, empty state, setup | Can become a route or sheet, but deep links must remain |
| `/videos/:id` | Stored player | Library, streamer detail, notifications, legacy route | Player loads lazily and has explicit loading, error and recovery states |
| `/streamer/:streamerId/stream/:streamId/watch` | Legacy compatibility | Old links | Must remain reachable or redirect safely to the new player |
| `/live/:streamer` | Live player | Dashboard, Streamers, Streamer Detail, notifications | HLS error and reconnect states must be plain language |
| `/auth/setup`, `/welcome`, `/onboarding` | Setup shell | Router guard, first run | Separate from main app shell and no early push pressure |
| `/auth/login` | Auth shell | Router guard | Clear error, retry and return path behavior |

### Global utilities

| Utility | Desktop behavior | Mobile/PWA behavior | Notes for implementation |
| --- | --- | --- | --- |
| Header status | Shows connection, queue and notification summary without crowding navigation | Small status row or icon group above content, not inside bottom nav labels | Must not create layout shift on reconnect |
| Queue or jobs | Compact button opens a side panel or popover on desktop | Opens a bottom sheet or full screen sheet | Queue can become a primary route only if the user need grows beyond global panel |
| Notifications | Header button opens panel, `/notifications` can be added later if needed | Bottom sheet or full screen route for long history | Existing NotificationFeed can seed both forms |
| Account/session | Header menu | More or Settings section | Do not add auth controls to every page |
| Theme | Header or Settings | Settings or More | Avoid making theme a bottom nav item |
| PWA install | Quiet desktop affordance | Guided card in Settings and optional contextual prompt | Explain value before install or push request |

## Navigation decisions

### Desktop

- Keep a left sidebar as the primary navigation model because the app has stable product areas and deep status pages.
- Primary sidebar items are Dashboard, Streamers, Library, Subscriptions and Settings for now, matching `useNavigation.ts` and preserving feature parity.
- Admin Diagnostics stays out of the primary sidebar unless the user is in an admin or diagnostics context. It is reachable from Settings and error recovery links.
- Header contains global utilities only: connection status, jobs, notifications, theme or account. It should not duplicate page navigation.
- Context routes use page headers and breadcrumbs where useful, for example Streamers to Streamer Detail to Live Player.
- Active route language should use product labels: Dashboard, Streamers, Library, Settings, Admin Diagnostics.

### Mobile and PWA

- Bottom navigation remains the mobile primary navigation because it is already implemented and fits thumb access.
- Keep at most five bottom nav items. Current five items are acceptable: Dashboard, Streamers, Library, Subscriptions, Settings.
- Admin Diagnostics, Add Streamer, Notification Center, Queue, Live Player and Video Player are context routes or sheets, not bottom nav tabs.
- Panels that cover task detail should become bottom sheets on mobile: Notifications, Jobs, Add Streamer shortcuts, advanced filters and recovery actions.
- Bottom nav must respect `env(safe-area-inset-bottom)`, maintain 44px minimum targets and never hide primary content behind fixed elements.
- Installed PWA mode needs visible offline, reconnecting and update available states without browser chrome assumptions.

## Progressive disclosure rules

| Area | Show first | Reveal on demand | Never hide |
| --- | --- | --- | --- |
| Dashboard | live count, active recordings, critical failures, latest videos, queue summary | full event timeline, raw diagnostics, detailed queue history | connection failure, recording failure |
| Streamers | status, name, live and recording actions | bulk actions, advanced filters, per streamer settings | add streamer path, live or recording state |
| Streamer Detail | profile, current state, latest recordings, key actions | advanced recording settings, event history, diagnostics | current recording failure |
| Library | video cards, filters, search | metadata detail, file technical data | missing file or processing failure |
| Notifications | unread and severity filters, target action | raw event payload, source channel explanation | critical failures and target links |
| Settings | basic sections with save state | advanced, dangerous, diagnostics | validation errors and unsaved changes |
| Admin | diagnostics grouped by topic | raw logs, test helpers | admin only boundary |

## Core journeys

### New user setup

1. Router sends the user to setup, welcome or onboarding.
2. The shell is focused and does not show the full product sidebar.
3. The user completes required setup and sees a short orientation.
4. PWA and Push are introduced as optional value, not as a blocking permission prompt.
5. Success lands on Dashboard with an empty state or first action.

Success criteria:

- The user knows what StreamVault will monitor.
- The next action is Add Streamer or Review Settings.
- Push permission is not requested without an explicit button.

### Dashboard status check

1. User opens `/` from browser or installed PWA.
2. Top status shows connection, active recordings, live streamers, queue failures and critical notifications.
3. User can open the most urgent item directly.
4. If all is healthy, user sees recent recordings and quick actions.
5. If offline or reconnecting, the message is calm and actionable.

Success criteria:

- In 3 seconds the user can answer whether anything is live, recording or failing.
- No raw debug feed is required to understand health.

### Add streamer

1. User starts from Streamers or Dashboard empty state.
2. User chooses manual add or import.
3. Form explains required fields and validates near the input.
4. Success opens the new streamer context or returns to the filtered Streamers list.
5. Failure explains recovery without dumping backend detail.

Success criteria:

- Deep links to existing add routes keep working.
- Mobile flow uses a route or sheet with full width controls.

### Active recording follow up

1. User sees an active recording on Dashboard, Queue or Streamer Detail.
2. User opens the recording context.
3. Progress, runtime, streamer, output status and errors are visible.
4. Recovery action links to Streamer Detail, Live Player or Admin Diagnostics as needed.
5. Completion moves the item into recent recordings without layout jump.

Success criteria:

- Queue status and recording status use the same status language.
- Long running recordings do not look stuck only because they exceed a normal duration.

### Find and play video

1. User opens Library.
2. User filters by streamer, status or text.
3. Video card shows title, streamer, date, duration and processing or missing state.
4. User opens Video Player.
5. Player shows loading skeleton, playable content or readable recovery.

Success criteria:

- Video cards do not collapse while thumbnails load.
- HLS or missing file failures are recoverable and keyboard reachable.

### Notification handling

1. User sees a badge or opens Notification Center.
2. User filters unread, severity or event type.
3. User opens the target route or marks the notification read.
4. On mobile, this is a sheet or full route, not a cramped popover.
5. Critical events remain visible until read or cleared.

Success criteria:

- Notification source channels are clear: in app, push and external Apprise.
- Target URLs normalize to existing product routes.

### Mobile PWA use

1. User launches the installed app.
2. Bottom nav exposes top destinations and respects safe area.
3. Global jobs and notifications open as sheets.
4. Offline, reconnecting, update available and push permission states are visible.
5. Deep links from notifications open the right route.

Success criteria:

- Widths 375, 390, 430 and 768 have no horizontal scroll.
- All primary actions remain at least 44px by 44px.

### Failure recovery

1. User sees a failed recording, live player issue, push issue or queue failure.
2. UI states the problem in user language.
3. Primary recovery is visible: retry, open settings, open streamer, open diagnostics or dismiss.
4. Raw technical detail is available only behind Admin Diagnostics or details.
5. The notification or error target can be opened later.

Success criteria:

- A non developer can understand the next action.
- Admin detail exists without leaking into normal pages.

### Settings change

1. User opens Settings.
2. Sections are grouped by intent: Recording, Streamers/Twitch, Notifications, PWA/Push, Storage, System, Advanced, Diagnostics.
3. Basic fields load before advanced fields.
4. Changes have validation, save state and unsaved changes behavior.
5. Dangerous changes require confirmation and explain impact.

Success criteria:

- The user can find the right setting without scanning a giant single page.
- Advanced and diagnostics remain available but not front loaded.

## Task flows for implementation

| Flow | Entry | Required information | Main action | Feedback | Error state | Exit or undo | Deep link | Mobile variant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Dashboard triage | `/` | live, recording, queue, critical notifications | Open urgent item | Status cards and inline skeletons | Reconnect or load failed | Back to Dashboard after target | `/`, notification target | Single column cards, bottom sheets |
| Streamer search | `/streamers` | streamer name, live state, recording state | Search or filter | Results count and empty state | Load failed with retry | Clear filters | `/streamers` | Sticky search, filters sheet |
| Streamer detail action | `/streamers/:id` | profile, current status, settings, recent videos | Open live, adjust recording, review events | Toast or inline status | Action failed with reason | Cancel or revert where safe | `/streamers/:id` | Section tabs or stacked cards |
| Add streamer | `/add-streamer*` | add mode, username, import source | Validate and save | Success route and card status | Validation near input | Cancel to Streamers | existing add routes | Full width route or sheet |
| Library browse | `/videos` | filters, metadata, processing state | Open player | Skeleton thumbnails | Missing or failed file state | Back to Library | `/videos`, `/videos/:id` | Responsive list over dense grid |
| Stored playback | `/videos/:id` | video metadata, source URL, playback state | Play and recover | Player status and controls | HLS or file error with recovery | Back to Library or detail | `/videos/:id` | Player first, metadata below |
| Live playback | `/live/:streamer` | streamer status, HLS state, recording state | Watch or retry | Loading, reconnecting, live status | Offline or HLS failed | Back to Streamer Detail | `/live/:streamer` | Full width player, compact controls |
| Queue review | Header jobs | active, pending, failed, recent jobs | Open job or recovery target | Progress and status badges | Queue API or websocket stale | Close panel | future `/queue` optional | Bottom sheet |
| Notification review | Header badge | unread, severity, type, target route | Open target or mark read | Unread count updates | Target open failed | Close panel or clear | target URL | Bottom sheet or full route |
| Settings edit | `/settings` | section, field state, validation | Save | Saving, saved, error | Inline validation and retry | Cancel or reset | `/settings` | Accordions or section stack |
| Admin diagnostics | `/admin` | diagnostic topic | Inspect, run safe checks | Raw detail visible | Tool or API failed | Back to product route | `/admin` | Full route only, no cramped sheet |
| Auth/setup | `/auth/*`, `/welcome`, `/onboarding` | setup state, auth state | Login or complete setup | Progress and landing route | Auth or setup failed | Retry, sign out | existing auth routes | Focused shell without bottom nav |

## Accessibility contract

Implementation tasks must preserve these IA level expectations:

- Navigation items are links or buttons with accessible names and visible focus.
- Active route uses `aria-current="page"` where applicable.
- Sheets, dialogs and panels trap focus while open and restore focus when closed.
- Escape, close buttons and browser back behavior are defined for panels and modal routes.
- Status is never communicated by color alone. Every live, recording, failed, completed, queued and offline state has text.
- Loading, error and empty states use semantic headings or regions where helpful.
- Form labels and validation messages are connected to inputs.
- Notification and queue count changes should not cause noisy announcements, but critical failures need a polite status region.
- Motion respects `prefers-reduced-motion`.
- Target contrast is WCAG 2.2 AA.

## Performance and perceived performance contract

- Route level chunks stay lazy loaded.
- Dashboard, Streamers, Library and Settings use skeletons or stable placeholders instead of blocking spinners.
- Video and live players initialize only when the player route or component is visible.
- Media cards reserve thumbnail space to prevent layout shift.
- Global realtime updates update focused slices of state, not every page level computed chain.
- Queue and Notification panels do not fetch heavy detail until opened.
- Mobile sheets use transform based transitions and reduced motion fallback.
- Large lists are paginated or virtualized if real data proves they need it.
- Target metrics remain LCP 2.5s or better, INP 200ms or better, CLS 0.1 or better where local measurement can influence them.

## Consumption rules for downstream tasks

KAN2-003 Design System must consume:

- Status first product target.
- Status grammar for live, recording, queued, failed, completed, offline and reconnecting.
- Component needs for AppShell, PageHeader, StatusCard, NotificationItem, JobStatusItem, LoadingSkeleton, ErrorState, EmptyState, Drawer, BottomSheet and SettingsPanel.

KAN2-004 App Shell and Navigation must consume:

- Desktop sidebar plus header utilities decision.
- Mobile bottom nav with max five items.
- Admin Diagnostics outside primary navigation.
- Global jobs and notifications as panel or sheet utilities.
- Context route rules for Add Streamer, players, Streamer Detail and Auth.

KAN2-007 PWA and Mobile must consume:

- Bottom nav safe area and target size rules.
- Sheet behavior for jobs, notifications and advanced filters.
- Installed PWA states for offline, reconnecting, update available, install and push permission.
- Push permission as explicit button driven flow.

Core page implementation tasks must consume:

- The task flow table above.
- The feature parity route map in `.hermes/streamvault-feature-parity-map.md`.
- The progressive disclosure table above.
- The accessibility and perceived performance contracts above.

## Open decisions for later implementation

These are not blockers for IA, but must be resolved in code or design tasks:

- Whether Queue graduates from global utility to a full `/queue` route. Current recommendation: keep as utility until real usage or data volume requires a route.
- Whether Notifications needs a dedicated `/notifications` route. Current recommendation: build panel and mobile sheet first, then route only if history depth demands it.
- Whether Subscriptions merges into Streamers. Current recommendation: preserve route until feature parity and backend meaning are proven.
- Whether Admin Diagnostics appears under Settings only or has hidden direct navigation for admins. Current recommendation: direct route remains, primary product nav hides it.
