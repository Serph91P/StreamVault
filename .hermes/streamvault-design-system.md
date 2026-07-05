# StreamVault design system

Date: 2026-07-05
Status: defined and partially implemented in app/frontend/src/components/base, app/frontend/src/components/cards, app/frontend/src/components/icons and SCSS token files

## Design principles

1. Status first.
2. Calm by default, urgent when needed.
3. Fast paths for common actions.
4. Progressive disclosure.
5. Mobile equals first class.
6. No debug UI in product flows.
7. Clear recovery from errors.
8. Consistency over novelty.
9. Motion supports orientation, not decoration.
10. Recognition over recall.

## Product tone

StreamVault should feel like a self-hosted streaming and recording control center, a media app and a monitoring dashboard. It should not feel like an admin template, debug collection, Bootstrap card pile or desktop site squeezed onto mobile.

## Tokens

| Token group | Purpose | Implementation owner |
| --- | --- | --- |
| Color tokens | Neutral, primary and Twitch aware palette | _variables.scss |
| Semantic colors | success, warning, danger, info, muted and surface states | _variables.scss |
| Status tokens | live, recording, queued, failed, completed, offline | StatusBadge and token aliases |
| Typography scale | page title, section title, body, label, caption | _variables.scss and component rules |
| Spacing scale | consistent page, panel, grid and inline gaps | _variables.scss |
| Radius scale | cards, panels, controls and sheets | _variables.scss |
| Elevation scale | surfaces and overlays | _glass-system.scss and _variables.scss |
| Motion tokens | transition durations and easing | _variables.scss |
| Breakpoints | mobile, tablet, desktop | _variables.scss |
| Z index tokens | header, sheet, modal, toast | _variables.scss |

## Core components

| Component | Role | Rule |
| --- | --- | --- |
| AppShell | Product layout | Owns shell, not domain data |
| AppHeader | Global actions | Queue, notification, theme and account actions |
| NavigationWrapper | Desktop and mobile navigation | Five primary destinations only |
| PageHeader | Page title and primary action | Prefer in central views |
| SectionHeader | Section title and secondary action | Avoid custom heading blocks |
| StatusCard | High level metric and state card | Use for dashboard status |
| StatusBadge | Live, recording, queue, error and completion state | Always includes text |
| StreamerCard | Streamer identity and current action | Status first, touch friendly |
| VideoCard | Recording metadata and playback entry | Stable media layout |
| EmptyState | Explain absence and next action | No blank panels |
| ErrorState or PlayerError | Human readable recovery | Include retry or diagnostics target |
| LoadingSkeleton | Perceived performance | Prefer over blocking full page spinner |
| BaseButton | Buttons | No new one off button system |
| FormField | Inputs and errors | Label and help text belong together |
| BasePanel | Content surface | Use for settings and admin groups |
| BaseSheet | Mobile and transient surfaces | Touch friendly close and content area |
| BaseTable | Responsive table shell | Avoid desktop table on narrow mobile |
| NotificationItem | One event | Severity, source, target and read state |
| NotificationFeed | Notification Center shell | Filters, empty states and actions |
| PlayerStatus | Playback and stream status | Text plus badge, not color only |
| PlayerError | Recoverable playback errors | Actionable retry or fallback |

## Component rules

- Props must describe UI state, not leak raw backend payloads unless the component is a domain adapter.
- UI components do not own business logic or browser storage.
- Loading, empty and error states must be present for list and media components.
- Every interactive element must be a real button or link with an accessible label.
- Mobile touch targets should be at least 44px where practical.
- Use StatusBadge for status instead of color only spans.
- Use SvgIcon and IconSprite for app icons.
- Do not add FontAwesome, emoji status systems or new public icon files.
- Debug and test controls belong in Admin Diagnostics.
- Motion must respect reduced motion preferences.

## Status language

| State | Meaning | Visual rule | Text rule |
| --- | --- | --- | --- |
| live | Streamer is live | strong success or live token | say Live |
| recording | Capture is active | recording token, prominent | say Recording |
| queued | Work is waiting | info or queued token | say Queued |
| processing | Recording post-processing | info token | say Processing |
| failed | Action or job failed | danger token | include reason or next action |
| completed | Recording or job complete | success token | link to result when possible |
| offline | Streamer inactive | muted token | say Offline |
| reconnecting | Realtime is reconnecting | warning/info banner | offer retry when available |

## Responsive rules

| Breakpoint | Layout rule |
| --- | --- |
| 375px to 430px | Single column, bottom nav, sheets for filters and panels |
| 768px | Tablet hybrid, still touch first |
| 1024px and wider | Sidebar navigation, header utilities, multi column dashboard |
| 1200px and wider | More side panels and dense cards allowed |
| 1440px | Wider grids without losing scan hierarchy |

## Accessibility rules

- Every status has visible text.
- Forms use labels and inline errors.
- Focus states must be visible.
- Close, retry, clear and destructive actions are real buttons.
- Dialogs, sheets and popovers need close affordances and keyboard reachability.
- Reduced motion should reduce non-essential animations.
- No user task depends only on hover or tooltip content.
- Notification and realtime status changes should be visible without relying on sound or color only.

## Performance rules

- Lazy load route views.
- Use skeletons for list and media loading.
- Do not update large global arrays for small UI interactions.
- Keep WebSocket event projection centralized.
- Lazy initialize heavy player work on player routes.
- Keep layout stable for cards and thumbnails.
- Avoid deep watchers on large collections unless justified.
