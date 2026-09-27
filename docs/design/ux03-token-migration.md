# UX-03 design foundation and migration contract

## Canonical chain

`src/styles/design.tokens.json` is the only editable source for the new foundation chain. `scripts/generate-responsive-tokens.mjs` validates every `{path.reference}`, rejects missing and circular references, and deterministically emits `src/styles/_foundation.generated.scss`.

The generated names are intentionally layered:

- `--sv-fdn-*`: raw palette, spacing, size, radius, motion and elevation values.
- `--sv-sem-*`: theme-dependent roles for surfaces, text, borders, actions and status.
- `--sv-cmp-*`: component roles for buttons, fields, panels, overlays and badges.

Dark roles are emitted in `:root`; light roles override only semantic values in `[data-theme="light"]`. Component roles therefore follow the active theme without a second theme source. Responsive breakpoints remain owned exclusively by `responsive.tokens.json` and the same generator.

## Compatibility and staged migration

`_foundation-bridge.scss` maps established public aliases such as `--background-card`, `--text-primary`, `--primary-color`, status colors and target sizes to the semantic chain. Existing consumers therefore retain their names and behavior. New or changed foundation primitives use `--sv-*` directly. Alias removal belongs to the later measured cleanup phase; UX-03 does not claim that legacy pages are fully migrated.

The strict UX-03 surface comprises BaseButton, BaseIconButton, BaseLink, BaseInput, BaseDropdown, BasePanel, BaseModal, BaseSheet and StatusBadge plus the isolated Vue harness. BaseSheet now uses the same `useModal` ownership as BaseModal, including stacked body locking, focus trap, Escape and focus restoration. Numeric dropdown option values retain their public type.

## Gates

- `npm run check:foundation`: source/reference validation and deterministic generated-output drift check.
- `npm run lint:tokens`: raw-token and ownership lint plus non-increasing legacy debt counts.
- `npm run test:foundation-gates`: negative reference, drift, raw-color and output-budget fixtures; the evidence helper has explicit pass, unexpected-pass and wrong-failure control tests.
- `npm run test:foundation-browser`: real Vue primitives in Chromium across 320/360/390/768/1024/1440 CSS px, both themes, five states, 200% text, both dimensions of every visible target, document overflow, Axe serious/critical, reduced motion, safe-area padding, focus trap/Escape/return and negative touch/overflow/contrast fixtures.

The harness is test-only under `tests/fixtures/foundation-harness`; it adds no public route or debug feature. Routine browser runs write their four screenshots only below the ignored `foundation-test-results/` output directory through `testInfo.outputPath()`. That directory is deliberately separate from the regular E2E suite's `test-results/`, which Playwright clears when that suite starts.

Delivery images are a separate, explicit packaging action after a successful browser run:

`npm run capture:foundation-evidence -- --source ./foundation-test-results --output /absolute/delivery/directory`

Both arguments are mandatory; there is no environment fallback or Hermes-specific path. The packager requires exactly one current copy of each mobile/desktop light/dark image, copies only those four files, and writes `FOUNDATION-SHA256SUMS` in the destination. `npm run test:foundation-capture-integration` exercises the real Chromium gate, starts a test through the regular E2E configuration (thereby clearing its own output directory), packages and SHA-256-verifies the four actual foundation captures, runs the normal foundation gate again, and re-verifies the already packaged manifest without repackaging or restoration.

## Measured legacy debt

The existing strict counters remain unexpanded: transition-all 112/112, hard-coded max-width media 31/31, and nonsemantic click surfaces 7/8. These are bounded historical debt, not a global design-system pass. Their cleanup remains assigned to UX-08; shell/view migration remains UX-04 through UX-07.
