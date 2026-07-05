# UI primitive system

New frontend work should import shared primitives from this folder and from `components/cards` before adding local button, panel, badge, sheet, table or form classes.

## Base primitives

- `BaseButton`: canonical button wrapper for `.btn` variants, sizes, loading and disabled states.
- `BaseInput` and `BaseDropdown`: canonical labelled controls for common text and select fields.
- `FormField`: wrapper for custom form controls that still need shared label, hint and error wiring.
- `BaseList`: card stack list primitive for non-tabular collections.
- `BaseModal`: centered modal dialog for blocking decisions.
- `BaseSheet`: bottom, left or right sheet for transient mobile and utility surfaces.
- `BasePanel`: non-card panel primitive for compact sections and popover content.
- `BaseTable`: wrapper around the global `.table-wrapper` and `.data-table` styles.
- `StatusBadge`: canonical status and label pill for live, recording, offline, processing, completed and semantic tones.

## Card primitives

- `GlassCard`: low-level glass surface. Use it only when a card needs direct glass controls.
- `SurfaceCard`: preferred new card primitive for page sections with optional title, description, actions and footer slots.
- Domain cards in `components/cards`: keep using `StreamCard`, `StreamerCard`, `VideoCard` and `StatusCard` for their domain use cases.

## Rules for new work

1. Use `BaseButton` instead of local button classes unless a native unstyled button is required.
2. Use `SurfaceCard` or a domain card instead of adding new local `card` classes.
3. Use `StatusBadge` instead of adding local `badge` or `status-badge` variants.
4. Use `BasePanel`, `BaseSheet`, `BaseModal` and `BaseTable` before creating local panel, sheet, modal or table wrappers.
5. Add styles to a primitive only when multiple consumers need them. Keep one-off layout in the calling component.
6. Do not add new design token aliases in component styles.
