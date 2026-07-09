# StreamVault design system definition

Date: 2026-07-05
Branch: feat/frontend-overhaul-v2
Scope: Phase 2 design-system artifact for the frontend overhaul

## Source context

- Prompt source: `/opt/data/cache/documents/doc_44f07bf7581d_streamvault_frontend_overhaul_prompt.txt`, especially Phase 8 design-system and component requirements.
- Graphify context: parent task KAN2-001 reports a fresh Graphify extraction with 1,576 nodes and 2,155 edges. This worktree does not contain `graphify-out/graph.json`, so source verification used the current frontend files and the parent handoff.
- Verified source primitives: `app/frontend/src/styles/_variables.scss`, `app/frontend/src/styles/_components.scss`, `app/frontend/src/components/base/*`, `app/frontend/src/components/cards/*`, `app/frontend/src/components/navigation/*`, `app/frontend/src/components/notifications/*`, and the parity docs in `.hermes/`.

## Product design principles

1. Status first: every main surface must expose live, recording, queue, error and connection state before secondary detail.
2. Calm by default, urgent when needed: normal monitoring states stay quiet; recording, failures, reconnect and destructive actions use stronger tone and copy.
3. Fast paths for common actions: watch live, inspect recording, add streamer, filter videos, mark notifications and open settings must be reachable without hunting.
4. Progressive disclosure: advanced settings, diagnostics and debug details move into panels, sheets or Admin Diagnostics.
5. Mobile equals first class: mobile uses bottom navigation, safe-area spacing, 44px touch targets and sheets instead of cramped desktop tables or popovers.
6. No debug UI in product flows: raw WebSocket, logger, queue internals and PWA test surfaces belong in Admin Diagnostics or dev-only paths.
7. Clear recovery from errors: player, recording, push, API and settings failures require readable text, next action and target route.
8. Consistency over novelty: new views must reuse shared tokens and primitives before adding one-off classes.
9. Motion supports orientation, not decoration: movement is short, cancellable by reduced motion and never required to understand state.

## Token system

### Current token inventory

| Token area | Current source | Current state | Required rule |
| --- | --- | --- | --- |
| Brand color | `_variables.scss` primary teal and accent purple | Present | Use teal for primary actions and system identity. Use purple for secondary emphasis, not routine status. |
| Semantic color | success, danger, warning, info CSS variables | Present | Map domain status to semantic tokens, not local hard-coded colors. |
| Neutral color | slate scale and dark theme variables | Present | Dark-first shell uses slate 950, 900 and 800. Light theme must keep contrast parity. |
| Typography | Inter, Fira Code, text scale xs through 5xl, fluid map | Present | Page titles use 2xl or 3xl. Component labels use sm. Dense metadata uses xs or sm. |
| Spacing | 4px base scale 0 through 24 plus aliases | Present | Layout gaps use 4px multiples. Avoid custom pixel gaps unless tied to media aspect ratios. |
| Radius | sm, default, md, lg, xl, 2xl, 3xl, full | Present | Cards and panels use lg or xl. Pills and status badges use full. Bottom sheets use 2xl top corners. |
| Elevation | shadow xs through 2xl plus focus shadows | Present | Use elevation for hierarchy and overlays only. Avoid stacked heavy shadows. |
| Motion | duration 75 through 1000, ease curves, transition aliases | Present | Default interaction motion is 150ms to 250ms. Route and sheet motion is 200ms. |
| Breakpoints | xs 375, sm 640, md 768, lg 1024, xl 1200, 2xl 1440, 3xl 1920 | Present | Use `_mixins.scss` breakpoints. Do not add hard-coded component media queries. |
| Z-index | base, overlay, modal, toast | Partial | Add named shell layers for header, nav, panel, sheet and popover before more overlays. |
| Safe area | CSS custom properties used by sheet and mobile shell | Partial | Every bottom nav, sheet and mobile footer must reserve safe-area inset bottom. |

### Status tokens

| Domain status | Token | Primary UI pattern | Copy rule |
| --- | --- | --- | --- |
| live | danger or live | Red live badge with dot, optional pulse only on active live state | Always include text `Live`. |
| recording | danger or recording | Strong red badge and recording item state | Always include `Recording` or `REC` plus accessible label. |
| queued | warning | Queue item badge and compact dashboard count | Use `Queued`, not internal job wording. |
| processing | warning | Video or job badge | Use `Processing` with progress when known. |
| completed | success | Job, recording and notification done state | Use `Completed`, `Ready` or `Saved` based on route context. |
| failed | danger | Error badge plus recovery action | Use readable cause and next step. |
| offline | neutral | Muted badge or secondary metadata | Avoid implying an error. |
| reconnecting | warning | Shell connection banner or compact indicator | Explain retry state without panic. |
| connected | success or neutral | Small shell indicator | Do not over-emphasize healthy state. |

## Component model

### Current primitive map against prompt list

| Prompt component | Current primitive | Readiness | Implementation gap |
| --- | --- | --- | --- |
| AppShell | `App.vue`, `components/navigation/NavigationWrapper.vue`, `SidebarNav.vue`, `BottomNav.vue` | Partial | App shell exists but still needs a named `AppShell` boundary with header, nav, panels and responsive slots. |
| PageHeader | Local headers in views | Missing shared primitive | Create a `PageHeader` with title, description, status slot, actions and breadcrumbs or route context. |
| SectionHeader | `BasePanel` slots and local headings | Partial | Standardize title, description, actions and status count pattern. |
| StatusCard | `components/cards/StatusCard.vue` | Present | Align all dashboard and queue metrics to one prop and status grammar. |
| RecordingStatusBadge | `StatusBadge` tone recording and local classes | Partial | Add domain wrapper or helper mapping recording states to text and tone. |
| LiveStatusBadge | `StatusBadge` tone live and local card badges | Partial | Replace duplicate live badge styles in streamer and stream cards with one accessible pattern. |
| StreamerCard | `components/cards/StreamerCard.vue` | Present but oversized | Split actions menu, avatar/status header and metadata into smaller pieces before page rebuilds. |
| VideoCard | `components/cards/VideoCard.vue` | Present | Replace local `.status-badge` implementation with `StatusBadge`; keep aspect ratio and lazy thumbnail behavior. |
| EmptyState | `components/EmptyState.vue`, `NotificationState.vue` | Present | Define empty-state slots for title, body, action and secondary help across routes. |
| ErrorState | `PlayerError.vue`, `NotificationState.vue`, local view errors | Partial | Create a general route and panel error state with recovery action and diagnostic link. |
| LoadingSkeleton | `components/LoadingSkeleton.vue` | Present | Define skeleton variants for list, card grid, media player and settings panel. |
| Button | `components/base/BaseButton.vue`, global `.btn` | Present | Ensure every icon-only usage has aria label. Avoid adding new local button systems. |
| IconButton | global `.icon-btn`, local button classes | Partial | Create or document a Vue `IconButton` wrapper around `.icon-btn`. |
| Input | `BaseInput.vue`, `FormField.vue`, global form classes | Present | Use `FormField` for labels, hints and errors in all settings and add-streamer forms. |
| Select | `BaseDropdown.vue`, native selects in views | Partial | Keep one select API and migrate local select classes during page work. |
| Toggle | Local switches in settings panels | Missing shared primitive | Create `BaseToggle` with label, hint, disabled and error contract. |
| Tabs | Local tabs in `VideoTabs.vue` and settings | Partial | Define shared tab rule with keyboard behavior and mobile overflow. |
| SegmentedControl | Local filters and notification filters | Missing shared primitive | Create for view mode, severity filters and compact switches. |
| Modal | `BaseModal.vue` | Present | Keep for destructive confirmation and desktop dialogs only. Prefer sheet on mobile. |
| Drawer | `BaseSheet.vue` with left or right side | Present | Use right sheet for desktop panels and bottom sheet for mobile. |
| BottomSheet | `BaseSheet.vue` side bottom | Present | Add focus trap if future interaction requires tab containment. |
| Toast | `ToastContainer.vue`, `ToastNotification.vue` | Present | Align severity, timeout and action rules with Notification Center. |
| NotificationItem | `components/notifications/NotificationItem.vue` | Present | Ensure source channel, target route and read state are visible in dense and mobile layouts. |
| NotificationCenter | `NotificationFeed.vue`, notification store, filters | Partial | Make center a first-class page or shell panel with same item component. |
| JobStatusItem | `BackgroundQueueMonitor.vue`, `BackgroundQueueAdmin.vue` | Partial | Add shared queue item row/card with state, progress, retry and cancel affordances. |
| DataTable / ResponsiveList | `BaseTable.vue`, `BaseList.vue`, `_tables.scss` | Partial | Use table only on desktop. On mobile switch to responsive list cards with same data. |
| SettingsPanel | settings panels and `BasePanel` | Partial | Standardize basic, advanced, danger zone and diagnostics panel contracts. |
| Panels | `BasePanel.vue`, `SurfaceCard.vue`, `GlassCard.vue` | Present | Prefer `BasePanel` for settings and dense data, `SurfaceCard` for product cards. |
| Cards | `GlassCard.vue`, `SurfaceCard.vue`, domain cards | Present but duplicated | Keep GlassCard as low-level surface only. Domain cards should expose clear props and states. |
| Badges | `StatusBadge.vue`, local badges in cards and tables | Partial | Centralize status badge rendering and copy. |
| Icons | `SvgIcon.vue`, `IconSprite.vue`, many local svg uses | Partial | Use one icon API for size, title, decorative mode and text pairing. |
| Forms | `FormField`, `BaseInput`, `BaseDropdown`, settings local controls | Partial | Add toggle, textarea and validation summary before settings rebuild. |

## Component rules

1. Clear props: each component exposes product-level props or primitive-level props, not mixed backend payloads unless it is a domain component.
2. No hidden business logic in primitives: Base components do not call API services, stores or router. Domain cards may emit actions or navigate only when documented.
3. Responsive behavior is part of the contract: every card, panel, table and sheet documents desktop, tablet and mobile behavior.
4. Loading, empty and error states are not optional: every data surface has a skeleton or empty state and a recoverable error state.
5. Accessibility by default: labels, aria labels for icon-only controls, visible focus, status text, captioned tables and keyboard paths are mandatory.
6. No duplicate systems: new page work must not add another button, card, badge, modal, input or toast pattern.
7. Local classes are allowed only for layout or domain-specific composition. Visual tokens and interaction states come from shared primitives.
8. Debug and diagnostics components may be dense, but still use the same buttons, tables, badges and focus rules.

## Desktop density and shell rules

- Desktop layout uses a stable sidebar or shell navigation, a header for global actions and main content that is readable at 1024, 1200 and 1440 widths.
- Dashboard and list pages use a status strip first, then primary content, then detail panels.
- Tables are allowed for diagnostics, settings summaries and queue details when at least 600px content width is available.
- Side panels use `BaseSheet` right side for notifications, queue, filters and contextual help.
- Dense lists use 44px minimum interactive rows when clickable, visible focus and text labels for each status.

## Mobile and PWA rules

- Bottom navigation is limited to 4 or 5 primary destinations. More, diagnostics and advanced settings move to settings or a sheet.
- All primary touch targets are at least 44px in height and width.
- Bottom sheets are the default for filters, notification detail, queue detail and context actions on mobile.
- Avoid desktop tables below `md`. Use `BaseList` or route-specific responsive cards.
- Mobile content respects safe-area insets for bottom navigation, sheet footer and fixed actions.
- PWA install and push permission flows must explain value before permission prompts and must show current permission state.

## Accessibility rules

- No status is conveyed by color alone. Badges need visible text and dots are decorative.
- Icon-only actions require aria labels. Icons paired with text should be decorative unless they add meaning.
- Dialogs, modals and sheets use `role="dialog"`, `aria-modal`, close buttons and Escape where safe.
- Focus must return to the opener after closing modal or sheet surfaces.
- Tables need captions or labelled-by references when content is not self-explanatory.
- Form controls require labels, inline hints and inline errors through `FormField` or equivalent shared wrappers.
- Reduced motion must disable decorative transitions and keep orientation clear.

## Performance and fluidity rules

- Cards reserve media aspect ratios to prevent layout shifts.
- Loading states keep dimensions stable. `BaseButton` already preserves width during loading and should remain the pattern.
- Large media and HLS players initialize only when route or panel needs them.
- Lists with high counts use pagination, filters or virtualization before adding expensive animations.
- Realtime updates must update domain state in targeted batches and should not trigger broad page re-renders.
- Motion duration defaults to 150ms to 250ms and never blocks input.
- Glass effects are used for primary surfaces and overlays only. Avoid nested glass overdraw in dense lists.

## Implementation-ready component gaps

| Priority | Gap | Evidence | Acceptance criteria |
| --- | --- | --- | --- |
| P0 | Shared `PageHeader` and `SectionHeader` | Current views carry local headers and actions | Each core route can render title, description, status and actions with one pattern. |
| P0 | Status badge consolidation | `StatusBadge.vue` exists, but `VideoCard.vue` and `StreamerCard.vue` still define local badge systems | Live, recording, processing, failed, offline and completed states use one badge contract with text. |
| P0 | Responsive table to list rule | `BaseTable.vue` defaults to min-width 600px and wraps overflow | Mobile routes use `BaseList` or cards, not horizontal product tables. |
| P0 | Shared error state | Error handling exists in player and notification surfaces but not as a route primitive | API, recording, HLS and push errors share title, message, action and optional diagnostics link. |
| P1 | `IconButton` Vue primitive | Global `.icon-btn` exists, but many local icon buttons remain | New wrapper enforces aria label, size, tone and loading or disabled state. |
| P1 | `BaseToggle` and setting control contract | Settings panels use local controls | Toggle has label, hint, error, disabled and on or off text for accessibility. |
| P1 | `SegmentedControl` | Filters and view modes have local implementations | View mode, notification severity and compact filters share keyboard and selection behavior. |
| P1 | Notification Center product surface | Notification item, filter and state exist, but center is still feed/panel oriented | Desktop panel and mobile sheet or route use the same item, filters and read/unread controls. |
| P1 | Queue and job status item | Queue monitors exist in product and admin areas | Job item renders state, progress, retry, cancel and target link without exposing raw debug data. |
| P2 | Domain card decomposition | `StreamerCard.vue`, `StreamCard.vue` and `VideoCard.vue` are large and combine state, actions and style | Cards split into status header, media, metadata and action menu subparts during page work. |
| P2 | Z-index layer names | Existing z-layer map has base, overlay, modal and toast only | Add shell, header, nav, popover, sheet and tooltip layers before overlay-heavy work. |
| P2 | Icon usage standardization | `SvgIcon.vue` and `IconSprite.vue` exist alongside raw svg usage | One icon API defines decorative, labelled, size and tone behavior. |

## Non-goals for this artifact

- This file does not implement new Vue components.
- This file does not change SCSS tokens.
- This file does not remove existing routes or productive controls.
- This file is a source-of-truth contract for follow-up implementation tasks and reviews.
