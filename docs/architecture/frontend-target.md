# Frontend target architecture

## Approved direction

Keep Vue 3, TypeScript, Vite, Pinia, Vue Router, Sass, VitePWA and hls.js. Preserve StreamVault teal/purple identity, both themes, cookie auth, deep links, API paths, WebSocket messages, media semantics and saved preferences. This P0/P1 slice does not move production modules.

## Target boundaries

```text
src/app/       bootstrap, router, shell, providers, app adapters
src/shared/    tokens, pure UI, API foundation, config, common types
src/entities/  stable domain models and backend adapters
src/features/  product orchestration by feature
```

Views compose features. Shared primitives do not import API clients, stores or router. Domain adapters isolate backend payloads from component props. App adapters own router Back behavior and integration with browser lifecycle APIs.

## Ownership decisions for later materialization

| Concern | Single owner | Compatibility rule |
| --- | --- | --- |
| PWA manifest and registration | VitePWA | generated manifest and worker output are authoritative |
| responsive values | `responsive.json` then generated TS/Sass | retain current 768 player and 1024 shell behavior while migrating aliases |
| overlays | one app-provided overlay manager evolving `useModal` | one document keydown owner for the stack; preserve nested lock, Escape and focus restoration semantics without a parallel stack |
| realtime/session | one WebSocket/session authority | normalize legacy forms at the boundary |
| shell navigation | app shell | shared UI does not depend on router |
| touch contract | rendered audit plus tokens | actual target and hit testing, not CSS literal replacement |

The owner-decision source specifies generated `responsive.json`, `responsive.generated.ts`, `_responsive.generated.scss`, `useLayoutQuery(name)`, and `useOverlay`. Those are future materialization interfaces, not files added by this slice.

## Target interaction contract

- Ordinary visible actions: 44 by 44 CSS px minimum; primary and icon-only actions normally 48 by 48.
- No overlapping expanded hit areas. Hidden and disabled actions are excluded from activation checks and cannot reserve invisible overlap.
- Reflow at 320 CSS px without document-level horizontal scroll except an intentional accessible data region.
- Keyboard, screen reader, touch, coarse pointer, mouse, reduced motion and forced colors are first-class contracts.
- Mobile navigation has labels and no broad edge-swipe navigation. Width does not imply input capability.

## Regression-harness contract

`tests/audit/interactionAudit.ts` is pure DOM audit logic with RED/GREEN unit proof for undersize, overlap, hit-test obstruction and hidden/disabled exclusions. `tests/e2e/frontend-baseline.spec.ts` uses the same policy against rendered browser pages and persists stage records before each a11y step. Lighthouse additionally rejects an LHR unless its final route and exactly one source-derived rendered root match the scenario; route redirects and missing, mismatched, zero or duplicate roots have regression coverage. Current Chromium and Firefox representative artifacts are mixed baseline observations, not passing coverage: Chromium dark 1440x900 stopped at navigation with `Target crashed`; Firefox dark 390x844 recorded focus count 0; Firefox light 390x844 and light 1440x900 each retain one serious-or-critical axe finding. Run-205 WebKit reports are likewise retained as four `readiness` failures with null later-stage values and individual traces. The exception document is intentionally empty and has the narrow schema selector, route, reason, owner and expiry-followup. Broad exclusions are forbidden.

## Requirement ledger

| Prompt section/lines | Existing evidence | Gap | Phase | Artifact/test | Status |
| --- | --- | --- | --- | --- | --- |
| target architecture 451-529 | current Vue route/view/component layout | boundaries not materialized | architecture | this document, source inventory | pending |
| TypeScript/Vue 532-571 | strict TS config, inventory of `any` | legacy `any`, root lifecycle debt | quality | unit/type checks | pending |
| design system 574-677 | token lint and base components exist | duplicated primitives/styles | tokens/primitives | token parity tests | pending |
| responsive 680-715 | Sass aliases, current 768/1024 behavior | one generated source absent | responsive | future generator/check | pending |
| touch contract 718-791 | source scan and current tests | rendered universal audit now introduced, baseline violations must be collected | P1 | interaction audit | pending |
| shell, overlay, forms 853-1064 | app shell/useModal/source inventory | central ownership migration | shell/overlay/forms | keyboard and focus suites | pending |
| data/routes/player 1067-1338 | complete route/player inventory | route-by-route implementation | feature slices | 28 workflow suite | pending |
| PWA/API/realtime 1340-1552 | source inventory | duplicated/incomplete authority | PWA/API/realtime | contract tests | pending |
| accessibility/security/performance 1555-1879 | axe dependency and build numbers | complete matrix and remediation | hardening | axe, keyboard, audits, Lighthouse | pending |
