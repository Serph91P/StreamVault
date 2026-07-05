# StreamVault UX audit

Date: 2026-07-05
Scope: Graphify and source verified frontend overhaul
Method set: Nielsen heuristic evaluation, Jobs to be Done, journey mapping, task flows, information architecture, progressive disclosure, recognition over recall, mobile first, WCAG 2.2 AA target, performance UX, design critique

## Jobs to be Done

| Job | User statement | Required product feedback | Final product surface |
| --- | --- | --- | --- |
| Monitor streamers | When I open StreamVault, I want to know who is live and recording so I can trust capture is working | Live count, recording count, queue and failures in under 3 seconds | Dashboard and Streamers |
| Understand recording state | When a stream is active, I want to know if it is being captured and if output is healthy | Recording badges, progress, active recording cards, failure notifications | Dashboard, Streamer Detail, Queue |
| Start or follow recording | When a streamer matters, I want to start or follow capture without hunting for controls | Contextual actions with confirmation and visible result | Streamer card, detail, live player |
| Find videos | When a recording is done, I want to find and play it quickly | Library filters, metadata, completed notification targets | Library and Video Player |
| Handle errors | When a job fails, I want plain language cause and next action | Critical notification, queue failure card, diagnostics link | Notification Center, Queue, Admin |
| Use mobile PWA | When away from desktop, I want app navigation and push to feel native | Bottom nav, safe area, sheets, install/update banners | App shell and PWA panel |
| Configure safely | When changing settings, I want basics and dangerous options separated | Grouped panels, labels, inline validation, diagnostics separation | Settings and Admin Diagnostics |

## Nielsen heuristic evaluation

| Heuristic | Pre-overhaul issue | Applied change | Evidence |
| --- | --- | --- | --- |
| Visibility of system status | Status was scattered across App.vue, cards, queue and notification panel | Dashboard status first layout, realtime banner, queue and notification counts | HomeView, AppShell, realtime store |
| Match real user language | Debug language and raw event names leaked into product UI | Product labels Dashboard, Library, Notification Center, Admin Diagnostics | Navigation and settings copy |
| User control and exits | Popovers and debug pages lacked clear escape patterns | BaseSheet, close labels, panels and route backed detail pages | BaseSheet and NotificationFeed |
| Consistency and standards | Buttons, cards, badges and icons had multiple systems | Shared primitives and internal SVG icon policy | Base primitives and IconSprite |
| Error prevention | Push permission could be requested too early | Permission requires explicit user intent and explanation | usePWA and PWAPanel |
| Recognition over recall | Users had to infer status from color or event strings | Status badges, filters, labels and empty states | StatusBadge and notification filters |
| Efficiency | Power users needed quick route and header actions | Header queue, notifications, theme and account utilities | AppHeader |
| Minimalist design | Product UI mixed diagnostics and test tools | Diagnostics moved to Admin, PWA tester removed | Admin and cleanup changes |
| Error diagnosis | HLS and PWA errors were technical | PlayerError, PWAPanel troubleshooting, notification severity | Player and PWA components |
| Context help | PWA and push lacked explanation | PWAPanel copy and QA documentation | PWAPanel and QA matrix |

## User journeys

### New user setup

1. Router guard sends user to setup or welcome.
2. User sees full screen setup instead of normal app chrome.
3. User completes setup or onboarding.
4. User lands on Dashboard.
5. PWA install or push appears later as an explained action, not an early permission prompt.

### Dashboard status check

1. User opens Dashboard.
2. Hero status and cards show live, recording, queue and failures.
3. User opens live player, streamer detail, queue or notification center from visible controls.
4. Realtime banner tells if connection is offline or reconnecting.
5. Empty state suggests adding streamers when nothing is active.

### Add streamer

1. User enters Streamers.
2. Add Streamer opens route backed task flow.
3. User selects manual or import.
4. Validation and errors remain near form fields.
5. Success returns user to streamer status context.

### Active recording check

1. Dashboard active recording card appears from realtime store.
2. User opens streamer detail or live player.
3. Queue panel stays globally available.
4. Failure notification deep links to the right target.

### Find recorded video

1. User opens Library.
2. Search and filters narrow videos.
3. VideoCard shows streamer, date, duration and state.
4. Player route opens with status and error recovery.
5. Missing file or playback issue is shown inline.

### Notification handling

1. User clicks bell or notification toast.
2. Notification Center opens with unread and severity filters.
3. User marks items read or opens target URL.
4. Mobile uses a sheet model instead of desktop popover behavior.
5. Dedupe and per item read state reduce noise.

### Mobile PWA

1. User opens installed PWA.
2. Bottom navigation exposes five main destinations.
3. Safe area padding protects controls.
4. Queue and notifications open as panels or sheets.
5. Offline or reconnect status is visible and actionable.

### Recording failure recovery

1. User receives failure notification.
2. Notification opens target route or admin diagnostics if needed.
3. Error card states what happened and what can be retried or inspected.
4. Diagnostics remain out of normal product flow.

### Settings change

1. User opens Settings.
2. Basic user settings are grouped by domain.
3. Advanced and diagnostic actions are separated.
4. Save or error feedback appears in context.
5. Dangerous operations require explicit action and visible status.

## Task flow design

| Flow | Entry | Intent | Needed info | Main action | Feedback | Error state | Exit | Success | Deep link | Mobile variant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Monitor system | Dashboard | Know current health | live, recording, queue, failures | scan dashboard | status cards and banner | section retry or critical alert | navigate away | status known in 3 seconds | / | single column feed |
| Manage streamer | Streamers | Find and act | status, category, recording | open detail or force record | card status update | action error toast | back to list | action visible | /streamers/:id | touch card and sheet actions |
| Watch video | Library | Play recording | metadata, file state | open video | player status | PlayerError retry | back to library | playback starts | /videos/:id | full screen player |
| Subscribe push | PWA panel | Enable background alerts | support, permission, SW state | request permission then subscribe | subscription state | denied or server sync error | disable or retry | active subscription | /settings | panel section with large buttons |
| Read notification | Bell | Understand event | severity, source, target | open or mark read | item state changes | missing target message | close panel | event acted on | target_url | bottom sheet |
| Inspect queue | Header badge | Understand background work | job state, progress, failures | open queue panel | list updates | failed job card | close panel | next action known | dashboard panel | sheet |

## Information architecture

| Layer | Decision | Rationale |
| --- | --- | --- |
| Primary navigation | Dashboard, Streamers, Library, Subscriptions, Settings | Five destinations fit desktop and mobile without crowding |
| Context routes | Streamer detail, live player, video player, add streamer | These need deep links and back behavior |
| Global actions | Notifications, Queue, PWA update, theme, account | Available everywhere without becoming tabs |
| Admin diagnostics | Admin route outside normal navigation | Debug tools stay available but not product first |
| Settings structure | User settings first, diagnostics linked out | Progressive disclosure and safety |
| Empty states | Domain specific CTA and explanation | Recognition over recall |
| Loading states | Skeleton for lists and media, localized spinners | Perceived performance |
| Error states | Inline action and diagnostics link only when useful | Recovery instead of raw exception |

## Mobile first and PWA first findings

- Bottom navigation is the correct primary mobile pattern for five destinations.
- Header utilities must remain touch sized and labeled for assistive tech.
- Queue and notifications should use sheet or panel behavior, not tiny desktop popovers.
- Push permission is a product flow and now requires explicit action.
- Service worker source of truth is VitePWA registration plus backend push import injection.
- Android and iOS push require device QA and are documented as external validation.

## WCAG 2.2 AA target audit

| Area | Finding | Applied improvement | Remaining risk |
| --- | --- | --- | --- |
| Semantics | Some old sections were div heavy | Added labels, buttons and shared components | Full axe pass still recommended |
| Keyboard | Popovers and sheets needed focusable controls | BaseSheet close and panels use buttons | Manual keyboard route pass needed |
| Focus visibility | Button systems were inconsistent | Shared primitives use consistent focus styling | Existing legacy components may still vary |
| Contrast | Dark theme mostly strong but glass can reduce contrast | Status tokens and calmer surfaces | Full token contrast audit recommended |
| Motion | Animations existed globally | Reduced motion respected in design rules | Browser manual check needed |
| Color only status | Live and failure relied on color in places | StatusBadge includes labels | Legacy pages need ongoing sweep |
| Forms | Settings had mixed label patterns | FormField primitive added | Full form review recommended |

## Performance UX audit

| Topic | Pre-overhaul issue | Applied improvement | Remaining follow-up |
| --- | --- | --- | --- |
| Route cost | Some routes and players are heavy | Router lazy loads views | Consider further chunking large player paths |
| Initial status | Dashboard needed fast scan | Skeleton and status first cards | Measure LCP on deployed backend |
| Realtime updates | Many consumers watched latest raw message | Central realtime store and listeners | Profile high event rate sessions |
| Notification updates | LocalStorage event bus mixed with App.vue | Pinia notification store and storage wrapper | Backend stable ids for all channels |
| Player cost | HLS can be heavy | Player route and status components isolate cost | Further lazy initialize player submodules if needed |
| Layout shifts | Cards needed stable states | Skeletons and shared surfaces | Measure CLS with real thumbnails |
| Bundle | Build generated expected chunks | Warnings documented | Inspect large LivePlayer chunk in follow-up |

## Design critique checklist

- Dashboard communicates main system state in one scan.
- Primary action per page is visible without digging through debug panels.
- Error states now point to retry, target route or Admin Diagnostics.
- Mobile controls are treated as first class with bottom nav and sheet model.
- Diagnostics are intentionally separated from product flows.
- UI primitives reduce one off visual decisions.
- Decorative glass is restrained through token ownership and calmer panels.
