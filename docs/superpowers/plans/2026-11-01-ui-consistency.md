# StreamVault UI consistency implementation plan

> **For agentic workers:** Use the task ownership below, then independent code review and browser verification. Tasks with disjoint files may run concurrently.

**Goal:** Finish the current channel-first candidate with one calm, consistent visual system.

**Architecture:** Converge existing SCSS tokens and Vue components. Preserve all product behavior in PR #969; no additional UI framework.

**Tech Stack:** Vue 3, TypeScript, Vite, SCSS, Pinia, Vue Router, Vitest, Playwright.

**Spec:** `docs/design/2026-11-01-ui-consistency.md`

## Global constraints

- Work from existing PR #969 head f2b94e7973989b8702c3fc5b4af9c077e0397d4c on its isolated worktree.
- Preserve routes, actions, saved state, APIs, auth, realtime, player and PWA behavior.
- Preserve 44px minimum targets, 48px primary/icon targets, 320px reflow, mobile 16px inputs, keyboard and reduced-motion behavior.
- No new runtime dependencies, backend edits, gate relaxation, merge or deployment.
- Component colors use existing semantic tokens; no extra global override stylesheet.

## Review focus

- Dark action fills versus colored foreground contrast; aliases must not turn dark-theme links into unreadable blue text.
- Unknown/error recording status must remain distinct from zero recordings.
- Selected/filtered library and channel state must survive layout changes and failed actions.
- Collapsed navigation and settings selection must keep usable names and focus; fixed chrome must not overlap content.
- Overlay stacking, focus return and body scroll behavior must remain unchanged.

## Task 1: Foundation and primitive convergence

**Ownership:** `src/styles/*`; base controls/panels/status except `PageHeader.vue`; `SurfaceCard.vue`; related focused tests.

- [x] Consolidate the theme aliases into the semantic colors in the spec; regenerate foundation output.
- [x] Give shared buttons/inputs/panels consistent flat presentation; remove conflicting duplicate styling where touched.
- [x] Retain loading accessible names and target/focus contracts. Add a behavioral regression only where a behavior actually changes.
- [x] Run relevant base units, token and foundation checks. Report exact files and results.

## Task 2: Browse, overview and media surfaces

**Ownership:** `StreamersView.vue`, `VideosView.vue`, `HomeView.vue`, `StreamerDetailView.vue`, `StreamerCard.vue`, `VideoCard.vue`, `StreamCard.vue`; their focused tests.

- [x] Re-read the current candidate before editing; earlier develop audit is not the current implementation.
- [x] Unify browse toolbars and quiet summary presentation; preserve all controls and saved state.
- [x] Make channel cards compact and left aligned; keep explicit details/menu actions and recording/status semantics.
- [x] Remove redundant overview containers/metrics and decorative glows; preserve all useful data and cleanup actions.
- [x] Keep route-backed detail tabs and player/library return semantics. Run relevant view/card tests.

## Task 3: Shell and settings

**Ownership:** `AppShell.vue`, navigation components, `PageHeader.vue`, `SettingsView.vue`, `ActivityView.vue` and relevant tests.

- [x] Flatten header utilities and simplify navigation labels/active treatment while preserving all destinations/actions.
- [x] Give the page header consistent density, secondary text and responsive action wrapping.
- [x] Flatten settings navigation and content hierarchy; retain selection/URL state and mobile guidance.
- [x] Add focused behavior tests for any changed navigation/selection behavior; run existing shell/settings tests.

## Task 4: Integration and review

- [x] Run the whole frontend unit suite, type checks, lint, design-token/foundation checks and REAL/MOCK production builds as required by browser harnesses.
- [x] Browser-check representative screens in both themes at desktop and mobile widths; inspect screenshots and behavior, including keyboard/overlays.
- [x] Run relevant existing browser suites and update only deliberately changed visual references after inspection.
- [x] Get independent diff review, resolve concrete regressions, and record verification limits.
- [x] Publish a reviewable update to the existing draft PR only after checking that its head has not changed.

## Completion evidence

See `docs/design/2026-11-01-ui-consistency-review.md` for decisions, before/after captures, final verification, independent review findings and the 16 reproduced external-avatar console failures. The full browser suite is not claimed entirely green. Publication uses a fast-forward update to the existing draft PR #969 with an expected-head lease; no merge or deployment.
