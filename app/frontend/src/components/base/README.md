# UI primitive system

New frontend work should import shared primitives from this folder and from `components/cards` before adding local button, panel, badge, sheet, table or form classes.

## Base primitives

- `BaseButton`: canonical button wrapper for `.btn` variants, sizes, loading labels and disabled states.
- `BaseInput` and `BaseDropdown`: canonical labelled controls for common text and select fields.
- `FormField`: wrapper for custom form controls that still need shared label, hint and error wiring.
- `BaseList`: card stack list primitive for non-tabular collections.
- `BaseModal`: centered modal dialog for blocking decisions.
- `BaseSheet`: bottom, left or right sheet for transient mobile and utility surfaces.
- `BasePanel`: non-card panel primitive for compact sections and popover content.
- `BaseTable`: wrapper around the global `.table-wrapper` and `.data-table` styles.
- `StatusBadge`: canonical status and label pill for live, recording, offline, processing, completed and semantic tones.
- `EmptyState`: canonical empty, recoverable error and critical error copy block. Use `tone`, `toneLabel`, `actionLabel` and `retryLabel` so status is not color-only.
- `LoadingSkeleton`: canonical skeleton placeholder. Pass a specific `label` when the loading region needs clearer assistive text.
- `NotificationState`: notification-feed adapter for empty, loading and error states. Keep notification-specific copy there, use `EmptyState` for generic product surfaces.
- `PlayerError`: playback overlay adapter for critical player errors. Keep player recovery there instead of duplicating alert markup.

## Card primitives

- `GlassCard`: low-level glass surface. Use it only when a card needs direct glass controls, clickable keyboard support, loading or disabled state wiring.
- `SurfaceCard`: preferred new card primitive for page sections with optional title, description, actions, footer, loading and disabled slots.
- Domain cards in `components/cards`: keep using `StreamCard`, `StreamerCard`, `VideoCard` and `StatusCard` for their domain use cases.

## Rules for new work

1. Use `BaseButton` instead of local button classes unless a native unstyled button is required.
2. Use `SurfaceCard` or a domain card instead of adding new local `card` classes.
3. Use `StatusBadge` instead of adding local `badge` or `status-badge` variants.
4. Use `BasePanel`, `BaseSheet`, `BaseModal` and `BaseTable` before creating local panel, sheet, modal or table wrappers.
5. Add styles to a primitive only when multiple consumers need them. Keep one-off layout in the calling component.
6. Do not add new design token aliases in component styles.

## Empty, loading and error migration notes

- Migrate repeated inline retry markup to `EmptyState` with `variant="inline"`, `tone="danger"` and `retryLabel` when the error is recoverable in place.
- Keep page-level data-flow redesigns in page redesign cards. StreamersView and VideosView still own their existing loading and empty branches until those pages are redesigned.
- Keep domain overlays as adapters: `PlayerError` owns playback errors, `NotificationState` owns notification feed states, and both delegate shared layout to `EmptyState`.
- Visual QA for follow-up cards should cover empty, loading, recoverable error, critical error, action button, long copy, 390px mobile and desktop.

## Primitive affordances

- `BaseButton` supports `primary`, `secondary`, `danger`, `warning`, `success`, `info`, `accent`, `outline`, `outline-primary`, `outline-danger`, `ghost`, `link`, `text` and `delete` variants. Use `loading-label` when the visible label is hidden by a spinner.
- `GlassCard` and `SurfaceCard` support `clickable`, `disabled`, `loading`, `labelled-by` and `described-by`. Clickable cards receive keyboard focus and activate with Enter or Space unless disabled or loading. Do not use `clickable` around slots that contain links, buttons, selects or other interactive controls. Use explicit inner actions in those cards instead.
- Domain cards that need whole-body navigation plus inner actions should use a sibling stretched `router-link` or native `button` inside the card body, with inner controls layered above it. Do not put buttons or links inside another clickable card root.
- `SurfaceCard` and `BasePanel` generate an `aria-labelledby` id from their `title` slot when `labelled-by` is not provided. Pass `labelled-by` when the heading id is controlled by the parent.
- Use `BasePanel padding="sm"` for dense sections, the default `padding="md"` for normal page panels and `padding="lg"` for spacious contexts. Use `:padded="false"` only when the child layout owns all spacing.

## Token and SCSS ownership

- New styles should use canonical token names from `docs/frontend-overhaul-token-scss-plan.md`.
- App tokens and current compatibility aliases are owned by `src/styles/_variables.scss`.
- Glass-only tokens, glass mixins and glass utility classes are owned by `src/styles/_glass-system.scss`.
- `main.scss` owns import order, reset, document base styles and legacy global element defaults only.
- `_components.scss` owns existing legacy global component classes only while migration is in progress.
- Do not define CSS custom properties in Vue component styles or non-owner SCSS files.
- If a new canonical token is truly needed, document its group, add it to the owning file and update `scripts/design-token-allowlist.json` in the same change.

## Transient surface audit (C-DS-001E)

BaseSheet and BaseModal have focus trap, escape close, aria labels, focus return, body scroll lock, and reduced motion support.

BaseSheet additionally handles safe-area padding (bottom/right/left variants) and max-height with dvh units.

BaseModal has safe-area padding in fullscreen-mobile mode.

### Deferred migrations

These surfaces use `.glass-popup-*` classes from `_glass-system.scss` and cannot migrate to BaseSheet/BaseModal without a product-level redesign:

- **AppShell notification panel** (`AppShell.vue:36-86`): Uses `.glass-popup-backdrop`, `.glass-popup-panel`, `.glass-popup-header` with custom focus trap (`handlePanelTab`), custom click-outside handler, and direct NotificationFeed composition. Requires Notification Center/AppShell redesign to refactor.

- **BackgroundQueueMonitor queue panel** (`BackgroundQueueMonitor.vue:26-128`): Uses `.glass-popup-backdrop`, `.glass-popup-panel`, `.glass-popup-content` with local body scroll management and no focus trap. Requires BackgroundQueueMonitor refactor to adopt BaseSheet.

Both deferred surfaces have adequate a11y for now. They should be migrated when their parent components are redesigned.

## Visual QA handoff for follow-up cards

When a later card changes primitives or shared styles, capture visual evidence for:

- dark theme
- light theme if the app path supports it
- 390px mobile viewport
- 1440px desktop viewport
- focus rings for keyboard navigation
- status colors for success, danger, warning and info states
- button states for primary, secondary, danger and warning in normal, hover, disabled, loading and keyboard focus states
- clickable and static cards, including disabled and loading card states
- `BasePanel` in dense, default and spacious padding contexts

## Form primitive visual QA

When `BaseInput`, `BaseDropdown` or `FormField` changes, capture these states before merge:

- default label with hint text
- required label and disabled control
- error message with `aria-invalid` and `aria-describedby`
- success message and success border state
- long label wrapping without clipping
- 390px mobile viewport with software keyboard width constraints
