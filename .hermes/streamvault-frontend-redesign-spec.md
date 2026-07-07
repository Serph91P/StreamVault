# StreamVault frontend redesign spec

Date: 2026-07-06
Branch: feat/frontend-product-overhaul-final
Base: origin/develop at aa6a134d
Reference: PR #702 foundation, follow-up product overhaul

## Product direction

StreamVault must feel like a modern self-hosted streaming and recording control center, media library, monitoring dashboard and mobile-ready PWA. It must not feel like a technical admin panel, form warehouse, debug wall or card patchwork.

## Global UX methods applied

- Nielsen heuristic evaluation: every page must expose system status, user-language labels, safe exits, consistent patterns, error prevention and readable recovery.
- Jobs to be Done: each route is designed around the main job, first needed information and primary action.
- Task flow design: every core flow defines entry, intent, primary information, primary action, feedback, error, recovery, exit and mobile variant.
- Information architecture: global navigation, local subnavigation, settings, admin diagnostics, drawers, sheets and routes are separated deliberately.
- Progressive disclosure: status first, details on demand, debug outside normal product flows, dangerous actions separated.
- Recognition over recall: labels, icons with text where needed, status text beyond color, helpful empty states and actionable errors.
- Fitts law and mobile touch: important actions are reachable, touch targets are at least 44px, dangerous actions are not adjacent to routine actions.
- Hick law: one clear primary action per page section, secondary actions grouped, advanced and debug hidden until requested.
- WCAG 2.2 AA target: semantic structure, keyboard access, focus order, focus states, contrast, labels, errors, reduced motion and dialog focus management.
- Performance UX: stable skeletons, no unnecessary reloads, lazy players, minimal broad rerenders and no layout shifts.

## Information architecture decisions

| Area | Global or local | Destination | Rule |
| --- | --- | --- | --- |
| Dashboard, Streamers, Library, Subscriptions, Settings | Global | Sidebar on desktop, bottom nav on mobile | Always visible as primary product navigation. |
| Notifications | Global utility | Desktop panel, mobile sheet or route | Events with read state, filters and target links, not just toasts. |
| Queue / Jobs | Global utility | Compact panel or sheet, admin detail deeper | Product status first, raw internals only in Admin Diagnostics. |
| Add Streamer | Context action | Route or sheet from Streamers and empty states | Deep links remain. |
| Streamer Detail tabs | Local | Overview, Videos, Recording Settings, Events | Local segmented navigation. |
| Settings sections | Local | Category cards and sections | Basic before advanced, danger zones isolated. |
| Admin Diagnostics | Separate route | `/admin` | Raw diagnostic and test surfaces only. |
| Players | Context route | `/videos/:id`, `/live/:streamer` | Player-first with context and recovery. |
| Auth/setup | Separate shell | setup, welcome, onboarding, login | No product chrome overload and no early push pressure. |

## Shared component requirements

| Component | Purpose | Source direction | Acceptance |
| --- | --- | --- | --- |
| AppShell | Balance navigation, content and global utilities | Refine `AppShell.vue` and navigation styles | Chrome does not overpower content at 1024, 1280 or 1440. |
| PageHeader / SectionHeader | Consistent page and section hierarchy | Keep `PageHeader`; add or standardize section header pattern | Title, description, status and actions are consistent. |
| StatusBadge | Domain status grammar | Consolidate local badges into one contract | Live, recording, queued, processing, failed, offline and completed use text plus tone. |
| SurfaceCard / BasePanel | Content density and hierarchy | Use for product cards and settings groups | Panels differ by purpose: content, status, settings, danger, diagnostics. |
| EmptyState / ErrorState / LoadingSkeleton | Stable states | Extend existing primitives and add shared error state if needed | Every data area has useful loading, empty and error states. |
| BaseButton / IconButton | Action hierarchy | Keep BaseButton, add IconButton or enforce icon label rules | Icon-only actions have aria labels. |
| FormField / BaseToggle / SegmentedControl | Settings and filter consistency | Add missing primitives before page rebuilds where useful | Forms have labels, hints, errors and touch-friendly controls. |
| BaseSheet / BaseModal | Dialog and mobile panels | Use sheet for mobile utilities and modal for confirmations | Focus returns to opener, Escape closes where safe. |
| ResponsiveList / Cards | Mobile table replacement | Use cards or list below tablet widths | No horizontal product tables on mobile. |

## Core page specs

### Dashboard

| Spec item | Requirement |
| --- | --- |
| User goal | Know within 3 seconds what is live, recording, queued, failed and recently completed. |
| Main content | Compact status summary, active recordings, live streamers, queue summary, failures, recent videos and recent activity. |
| Main action | Open the most urgent active or failed item. |
| Secondary actions | Add streamer, open Library, open Queue, open Notifications. |
| Status model | connected, reconnecting, offline, live, recording, queued, failed, completed. |
| Loading state | Skeleton status cards and stable section heights. |
| Empty state | Healthy empty dashboard with Add Streamer and Settings next steps, no giant blank panels. |
| Error state | User-readable outage or API failure with retry and Admin Diagnostics link. |
| Mobile layout | Single-column status strip, compact cards, queue and notifications as sheets. |
| Desktop layout | Dense two or three-column operational layout above fold. |
| Realtime behavior | Targeted updates to counts and lists without full page reload. |
| Notification behavior | Critical events appear in summary and link to targets. |
| Accessibility | Landmarks, heading order, focusable quick actions, status text not only color. |
| Performance | No broad rerender storms; skeletons avoid layout shift. |
| Build or replace | Split dashboard sections from `HomeView.vue`; reuse status badges and cards. |
| Old components displaced | Local one-off metric panels and low-value empty sections. |
| Acceptance criteria | 3-second status comprehension, no useless empty space, screenshots at required widths. |

### Streamers

| Spec item | Requirement |
| --- | --- |
| User goal | Scan creators, know who is live or recording, and start management quickly. |
| Main content | Creator grid or responsive list with avatar, name, status, latest activity, recording state and metadata. |
| Main action | Add Streamer or open a streamer detail. |
| Secondary actions | Filter, sort, force recording where safe, open live player. |
| Status model | live, recording, offline, disabled, error, importing. |
| Loading state | Grid skeletons preserving card dimensions. |
| Empty state | Low-count or no-streamer state with Add Streamer and Twitch import paths. |
| Error state | Load failure with retry and API status hint. |
| Mobile layout | Touch-friendly list/cards, filters in sheet, clear primary CTA. |
| Desktop layout | Dense grid with compact toolbar and useful row density. |
| Realtime behavior | Live and recording badges update without resorting or jumping unexpectedly. |
| Notification behavior | Streamer event links open filtered or targeted detail. |
| Accessibility | Search labelled, filters keyboard reachable, status text visible. |
| Performance | Avoid expensive filtering on each render; paginate or virtualize only if needed. |
| Build or replace | Rework `StreamersView.vue`, `StreamerCard.vue` and filter composition. |
| Old components displaced | Isolated oversized cards and local filter controls. |
| Acceptance criteria | Modern creator-grid feel, consistent status language, mobile no horizontal scroll. |

### Streamer Detail Overview

| Spec item | Requirement |
| --- | --- |
| User goal | Control one streamer, understand current state and act safely. |
| Main content | Compact profile header, status, last activity, active recording, latest videos and relevant warnings. |
| Main action | Watch live or start/stop recording depending on state. |
| Secondary actions | Edit settings, open videos, view events, diagnostics link. |
| Status model | live, recording, offline, disabled, failed, recovering. |
| Loading state | Header and panel skeletons. |
| Empty state | Explain no recent recordings or no events with next actions. |
| Error state | Recording or data failure with recovery and diagnostics route. |
| Mobile layout | Sticky or compact local tabs, primary action near thumb reach, danger hidden deeper. |
| Desktop layout | Compact header plus cards, no giant hero. |
| Realtime behavior | Header and active recording update in place. |
| Notification behavior | Target links land on the relevant tab or section. |
| Accessibility | Tabs are keyboard usable, destructive actions confirmed. |
| Performance | Split large view sections, lazy load heavier tabs. |
| Build or replace | Rework `StreamerDetailView.vue` into control-center sections. |
| Old components displaced | Large low-value hero and cramped top-right action cluster. |
| Acceptance criteria | Feels complete for Overview, Videos, Settings and Events, with visual evidence. |

### Streamer Detail Videos

| Spec item | Requirement |
| --- | --- |
| User goal | Find this streamer's recordings quickly. |
| Main content | Media list or grid scoped to the streamer. |
| Main action | Play a recording. |
| Secondary actions | Filter, sort, reveal file status, open Library filtered to streamer. |
| Status model | ready, processing, missing, failed, archived. |
| Loading state | Media skeletons with reserved thumbnail space. |
| Empty state | Explain no recordings and link to recording settings or live status. |
| Error state | API failure with retry. |
| Mobile layout | Dense vertical media cards. |
| Desktop layout | Grid or dense list with metadata. |
| Realtime behavior | New completed recordings appear without layout jump. |
| Notification behavior | Recording-complete notifications land here or in player. |
| Accessibility | Play and menu buttons labelled. |
| Performance | Lazy thumbnails. |
| Build or replace | Share card model with Library. |
| Old components displaced | Plain rows with weak media affordance. |
| Acceptance criteria | Media feel and low-data state verified. |

### Streamer Detail Recording Settings

| Spec item | Requirement |
| --- | --- |
| User goal | Adjust per-streamer recording behavior without accidental damage. |
| Main content | Basic recording, quality, storage, automation, advanced and danger cards. |
| Main action | Save changes in current card or section. |
| Secondary actions | Reset, test safe config, view diagnostics. |
| Status model | saved, unsaved, saving, error, inherited, overridden. |
| Loading state | Form skeleton grouped by card. |
| Empty state | Not applicable; show inherited defaults explanation. |
| Error state | Field-level errors plus top summary. |
| Mobile layout | Stacked cards and sticky contextual save where safe. |
| Desktop layout | Two-column sections where density helps. |
| Realtime behavior | Warn if active recording makes some settings take effect later. |
| Notification behavior | Save or failure toasts can link back to section. |
| Accessibility | Labels, hints, errors and focus order. |
| Performance | Avoid watchers that resave or recompute whole forms unnecessarily. |
| Build or replace | Use shared FormField, BaseToggle and settings cards. |
| Old components displaced | Long unstructured form wall. |
| Acceptance criteria | Basic and advanced are visually separated and save flow is clear. |

### Streamer Detail Events

| Spec item | Requirement |
| --- | --- |
| User goal | Understand history and changes for a streamer. |
| Main content | Timeline shell for live, recording, errors, settings and notification events. |
| Main action | Open related target. |
| Secondary actions | Filter event type, open diagnostics when needed. |
| Status model | info, success, warning, failed. |
| Loading state | Timeline skeleton. |
| Empty state | Helpful explanation of future timeline content and next step. |
| Error state | Retry and diagnostics link. |
| Mobile layout | Single-column timeline. |
| Desktop layout | Timeline with side metadata where useful. |
| Realtime behavior | New events append without scroll theft. |
| Notification behavior | Same event taxonomy as Notification Center. |
| Accessibility | Timeline items have readable text and timestamps. |
| Performance | Limit history and paginate if needed. |
| Build or replace | Add event state component when backend data exists or use a ready placeholder. |
| Old components displaced | Huge blank empty panel. |
| Acceptance criteria | Empty state no longer feels unfinished. |

### Videos / Library

| Spec item | Requirement |
| --- | --- |
| User goal | Browse and play recordings like a media library. |
| Main content | Video cards with thumbnail, title, streamer, date, duration, size, status and actions. |
| Main action | Play selected video. |
| Secondary actions | Search, filter, sort, change grid/list, open streamer. |
| Status model | ready, processing, missing, failed, archived, recording. |
| Loading state | Reserved thumbnail skeletons and stable toolbar. |
| Empty state | Low-data state with Add Streamer, import or recording settings next steps. |
| Error state | Retry and backend status hint. |
| Mobile layout | One-column media cards, filters in sheet. |
| Desktop layout | Dense responsive grid or list. |
| Realtime behavior | New recordings appear with gentle update indicator. |
| Notification behavior | Target links open player or filtered library. |
| Accessibility | Card controls labelled, thumbnail alt text meaningful or decorative. |
| Performance | Lazy thumbnails, lazy player route, no layout shift. |
| Build or replace | Rework `VideosView.vue` and shared `VideoCard`. |
| Old components displaced | Small isolated card in large blank canvas. |
| Acceptance criteria | Looks like a media app and has visual evidence at all required widths. |

### Stored Video Player

| Spec item | Requirement |
| --- | --- |
| User goal | Watch a stored recording and recover from media issues. |
| Main content | Player, video context, streamer, title, date, duration and status. |
| Main action | Play or retry. |
| Secondary actions | Open streamer, copy/share link, open file diagnostics if admin. |
| Status model | loading, ready, buffering, error, missing, unsupported. |
| Loading state | Player skeleton with stable aspect ratio. |
| Empty state | Not applicable; missing video is an error state. |
| Error state | User-readable cause, Retry, Back to Library and Admin Diagnostics link when useful. |
| Mobile layout | Full-width player, large controls, context below. |
| Desktop layout | Player-first with contextual side or lower panel. |
| Realtime behavior | File processing completion can refresh status. |
| Notification behavior | Recording complete target opens this player. |
| Accessibility | Controls keyboard reachable, captions or metadata discoverable. |
| Performance | Initialize HLS only when route is active. |
| Build or replace | Split player state and recovery UI from large player components. |
| Old components displaced | Generic playback error without product context. |
| Acceptance criteria | Stored media QA passes or task is blocked with exact media reason. |

### Live Player

| Spec item | Requirement |
| --- | --- |
| User goal | Watch a live stream and understand recording/live state. |
| Main content | Live player, streamer context, live badge, recording state, quality or codec status. |
| Main action | Play live or recover stream. |
| Secondary actions | Open streamer, start recording if safe, retry HLS. |
| Status model | connecting, live, buffering, reconnecting, offline, HLS error, auth error. |
| Loading state | Stable player skeleton and connecting copy. |
| Empty state | Streamer offline state with recent videos. |
| Error state | Explain HLS/auth/token issue and next action. |
| Mobile layout | Large player controls and touch-safe actions. |
| Desktop layout | Player-first with status/context panel. |
| Realtime behavior | Live/offline and recording state update without reload. |
| Notification behavior | Live notification target opens this route. |
| Accessibility | Status text and keyboard controls. |
| Performance | Lazy HLS initialization and no premature heavy setup. |
| Build or replace | Split live status, context and recovery components. |
| Old components displaced | Mock-only error state treated as enough QA. |
| Acceptance criteria | Live HLS QA passes or blocker is documented. |

### Notification Center

| Spec item | Requirement |
| --- | --- |
| User goal | Understand what happened, triage unread items and jump to targets. |
| Main content | Read/unread list, filters, severity or type grouping, timestamps and target links. |
| Main action | Open target or mark read. |
| Secondary actions | Mark all read, dismiss, filter, view source channel explanation. |
| Status model | unread, read, critical, warning, info, success, deduped. |
| Loading state | Notification list skeleton. |
| Empty state | Explain no notifications and how push or realtime works. |
| Error state | Storage or API failure with retry. |
| Mobile layout | Bottom sheet or route with full-width rows and sticky filter. |
| Desktop layout | Header panel or route with dense list. |
| Realtime behavior | Dedupe incoming events, preserve read state and avoid noisy jumps. |
| Notification behavior | Separate in-app, push and Apprise concepts in copy. |
| Accessibility | Dialog or route semantics, focus return, labelled filters. |
| Performance | Bounded list and stable storage writes. |
| Build or replace | Rework `NotificationFeed`, `NotificationItem`, store and storage wrapper. |
| Old components displaced | Debug-like notification feed. |
| Acceptance criteria | Read/unread, filter, dedupe and target links verified. |

### Settings Overview and Sections

| Spec item | Requirement |
| --- | --- |
| User goal | Configure StreamVault safely and understand consequences. |
| Main content | Category overview for Recording, Twitch, Notifications, PWA/Push, Apprise, Storage, System, Advanced and Diagnostics link. |
| Main action | Open or save the relevant section. |
| Secondary actions | Cancel, reset, open Admin Diagnostics for tests. |
| Status model | saved, unsaved, saving, error, requires restart, admin-only. |
| Loading state | Section card skeletons. |
| Empty state | Not applicable; use setup hints where data missing. |
| Error state | Section error with field links. |
| Mobile layout | Stacked category cards and accordion or route-like sections. |
| Desktop layout | Settings app layout, not nested heavy sidebars fighting app chrome. |
| Realtime behavior | Online/offline and reconnect indicators do not erase unsaved state. |
| Notification behavior | Save success or failure can notify with target. |
| Accessibility | Form labels, hints, errors, keyboard order and focus on invalid field. |
| Performance | Avoid rendering every heavy section at once if hidden. |
| Build or replace | Rework `SettingsView.vue` and panels into grouped cards. |
| Old components displaced | Technical form warehouse and mobile-hostile tables. |
| Acceptance criteria | Basic vs advanced, danger, diagnostics and responsive tables verified. |

### Settings PWA / Push

| Spec item | Requirement |
| --- | --- |
| User goal | Install StreamVault and enable push with confidence. |
| Main content | Guided setup steps for install, notification permission, subscription and test information. |
| Main action | Install or subscribe after explanation. |
| Secondary actions | Troubleshoot denied permission, open device notes, open Admin Diagnostics test. |
| Status model | installable, installed, unsupported, permission default, granted, denied, subscribed, unsubscribed. |
| Loading state | Capability check skeleton. |
| Empty state | Explain unsupported platform. |
| Error state | Denied permission or subscribe failure with recovery. |
| Mobile layout | Step cards sized for touch. |
| Desktop layout | Guided cards, not status table only. |
| Realtime behavior | Service worker and update state visible. |
| Notification behavior | Push click target routes documented and tested or blocked. |
| Accessibility | Buttons labelled, no permission request on load. |
| Performance | One registration owner, no duplicate service worker registration. |
| Build or replace | Rework `PWAPanel`, `PWAInstallPrompt`, registration checks and `push-sw.js` click routing. |
| Old components displaced | Raw status-list feel. |
| Acceptance criteria | Device or reality-based QA exists, or final gate blocks. |

### Admin Diagnostics

| Spec item | Requirement |
| --- | --- |
| User goal | Diagnose internal failures without polluting normal flows. |
| Main content | Health, system info, WebSocket status and background jobs first. |
| Main action | Inspect or open a diagnostic group. |
| Secondary actions | Test notifications, run verification, maintenance, cleanup, repair, video diagnostics. |
| Status model | healthy, degraded, failed, running, complete. |
| Loading state | Diagnostic group skeletons. |
| Empty state | Explain no active jobs or no diagnostics data. |
| Error state | Raw endpoint error inside admin context with retry. |
| Mobile layout | Disclosure sections and stacked controls. |
| Desktop layout | Admin capsule with disclosure groups. |
| Realtime behavior | WebSocket monitor and jobs update in place. |
| Notification behavior | Test actions remain admin-only. |
| Accessibility | `details` or disclosure controls labelled, focusable and readable. |
| Performance | Hidden diagnostic groups should not trigger heavy work until opened where feasible. |
| Build or replace | Continue surgical `AdminPanel.vue` disclosure split and `AdminView.vue` copy cleanup. |
| Old components displaced | Default debug wall in normal admin view. |
| Acceptance criteria | Admin is intentionally admin-only, visually verified and static checks pass. |

### Add Streamer

| Spec item | Requirement |
| --- | --- |
| User goal | Add a streamer manually or import from Twitch. |
| Main content | Choice between manual add and import, validation, success feedback and next route. |
| Main action | Add or import. |
| Secondary actions | Back to Streamers, open settings for Twitch connection. |
| Status model | idle, validating, adding, success, error. |
| Loading state | Button loading preserves layout. |
| Empty state | Explain why adding first streamer matters. |
| Error state | Field-level username or API error with recovery. |
| Mobile layout | Full-width choices and controls. |
| Desktop layout | Focused card or route, not buried in chrome. |
| Realtime behavior | Added streamer appears in list without reload where possible. |
| Notification behavior | Success can link to detail. |
| Accessibility | Labels, errors, keyboard submit. |
| Performance | No large app reload after submit. |
| Build or replace | Polish `AddStreamerView` and form states as needed. |
| Old components displaced | Generic form-only feel. |
| Acceptance criteria | Manual and import flows smoke-tested or blocked by backend. |

### Auth / Setup / Onboarding

| Spec item | Requirement |
| --- | --- |
| User goal | Set up and sign in without being overwhelmed. |
| Main content | Focused setup or login card with clear next step and recovery. |
| Main action | Complete setup or sign in. |
| Secondary actions | Retry, support info, return path. |
| Status model | unauthenticated, setup required, loading, error, complete. |
| Loading state | Focused shell skeleton. |
| Empty state | Onboarding orientation. |
| Error state | Auth failure with explanation and retry. |
| Mobile layout | Single-column shell with safe spacing. |
| Desktop layout | Centered shell, no product sidebar overload. |
| Realtime behavior | No WebSocket or push pressure before setup. |
| Notification behavior | Push introduced only after value is explained. |
| Accessibility | Form labels, focus on error, keyboard submit. |
| Performance | Lazy product shell until auth passes. |
| Build or replace | Verify auth shell boundaries and route guards. |
| Old components displaced | Premature product or PWA prompts. |
| Acceptance criteria | Login/setup route smoke and mobile evidence. |

## Screenshot-finding response map

| Screenshot issue | Design response | Primary task |
| --- | --- | --- |
| Too much empty space | Dense status-first page composition and meaningful low-data states | E-DASH-001, F-STREAMERS-001, H-LIBRARY-001, K-SETTINGS-001 |
| Heavy app chrome | Compact shell and coherent global utilities | D-SHELL-001 |
| Streamer Detail unfinished | Control-center detail with compact header and useful tabs | G-DETAIL-001 |
| Settings as form warehouse | Settings-app IA, cards, basic vs advanced and danger separation | K-SETTINGS-001 |
| Library not media-like | Media grid/list and strong video cards | H-LIBRARY-001 |
| Streamers not creator grid | Responsive creator cards with strong status language | F-STREAMERS-001 |
| Dashboard not finished | Fold-first system status and quick actions | E-DASH-001 |
| Desktop-heavy tables | Responsive card/list replacement on mobile | K-SETTINGS-001, N-QA-001 |
| Weak hierarchy | Shared panel variants and status grammar | C-DS-001 |
| Styled but not designed | Task-flow, state and QA gates per core page | B-SPEC-001, N-QA-001 |

## Implementation order

1. Finish Phase 1 hard parity map and this spec.
2. Implement design-system primitives needed by the first pages.
3. Finalize app shell density and utility model.
4. Rebuild Dashboard, Streamers, Streamer Detail and Library.
5. Rebuild Settings, Notification Center, PWA/Push and Admin Diagnostics.
6. Validate players with realistic media or block explicitly.
7. Run visual, accessibility and performance matrix.
8. Produce scorecard and final summary only after gates have evidence.
