# #1015 UX foundation

## Product contract and real consumers

The application remains an Operate UI: channels, recordings and activity; quiet neutral surfaces, one clear primary action and German product terminology. This is the foundation increment, not the domain redesign assigned to #1016–#1023.

| Pattern | Shared ownership | Product consumer |
| --- | --- | --- |
| Browse | Existing page header, toolbar and EmptyState; distinct confirmed-empty/filter-empty/error, dated stale data | StreamersView preserves previously confirmed channels when refresh fails; retry is inline |
| Detail | Existing object header, BaseButton, BaseModal and EmptyState | StreamerDetailView no longer calls a failed request “not found”; a named inline retry returns to the existing fetch owner |
| Form | Native BaseInput/BaseDropdown; persistent hints alongside associated announced errors | Global recording quality, filename preset/template and codecs in RecordingSettingsPanel |
| Operation | Existing settings store/API owner supplies pending and final state to the form | SettingsView keeps pending until save plus GET readback confirms the submitted values; a 202 body alone never produces success; failure remains inline |

`types/presentation.ts` is a typed **presentation vocabulary**, not a resource cache, fetch layer or mutation engine. Unknown, loading, confirmed-empty, filter-empty, fresh, stale (with confirmed timestamp), offline, forbidden (403) and error remain distinct from pending, confirmed-success, partial and failure. Callers choose state from their existing truth owner; neither the component nor a toast infers business completion. Context-specific copy, retry and content remain caller-owned. The existing EmptyState facade retains its legacy props and supports the new optional state without a parallel component platform.

`design.tokens.json` remains the only authored token source. Shared feedback surface/text/border/spacing roles resolve through the existing generator in both themes and are consumed by EmptyState and ToastContainer. No palette, framework, theme engine or budget replacement. Base native fields retain browser keyboard behavior and their current event/value contracts.

## Interactions

The existing useModal stack remains the only keyboard/focus owner. A new nested-dialog browser regression exposed missing background isolation despite working Escape/focus trapping. The stack now saves/restores `inert` and `aria-hidden` on siblings along the top dialog's ancestor path. Closing the upper overlay restores the previous one before restoring focus. The same BaseModal/BaseSheet facades use the German dismiss name “Dialog schließen”. No second trap or overlay stack is installed.

The existing useToast singleton is unchanged. ToastContainer announces ordinary statuses politely and errors urgently, hides decorative icons from accessible names, and supplies a 44px named close button. Reduced motion disables toast movement; focus uses the shared token.

The existing foundation harness is the small component/pattern overview, not a new product route. It exercises all states, short and long field contents, persistent hints/errors, disabled/pending controls, both themes and nested modal/sheet ownership.

## Reka UI decision and local probe

Official sources read: [introduction](https://reka-ui.com/docs/overview/introduction), [Dialog](https://reka-ui.com/docs/components/dialog). Reka supports unstyled progressively adopted Vue primitives, with Dialog owning modal focus, Escape and inert background. This overlaps the existing stack, so adapting that owner is smaller than replacing it or stacking traps.

Live registry metadata: `reka-ui@2.11.0`, MIT, peer `vue >=3.4.0`. An isolated scratch installation used exactly Vue 3.5.43; `npm audit --json` reported **0 known vulnerabilities** for that probe's dependency graph. This is not a claim about all product security findings (#968 remains separately owned).

Real local Vite 8.3.3 production-library probe, Vue external on **both** sides, same toolchain and actual source imports:

| Imported facade/primitive family | JS bytes | Node gzip bytes |
| --- | ---: | ---: |
| Actual existing BaseModal, including useModal/focus dependencies | 5,134 | 2,168 |
| Only Reka DialogRoot/Trigger/Portal/Overlay/Content/Title/Description/Close | 42,747 | 11,563 |

The current TypeScript 6 compiler accepted the actual Reka imports with bundler resolution (`tsc --ignoreConfig --noEmit --moduleResolution bundler --module esnext --target es2022 --skipLibCheck .../reka.ts`). The first invocation correctly required TS6's `--ignoreConfig`; no compiler downgrade was used. The figures are library-output comparisons, not a fabricated full-application bundle delta or a declaration that Reka cannot ever fit. The probe exports the exact named family, excludes Vue and does not include unrelated Reka components. The existing facade additionally emits 920 CSS bytes (400 Vite gzip bytes); Reka is unstyled.

Decision: **retain the proven native/Base primitives in this increment**. There is no demonstrated unmet complex primitive need after the scoped stack adaptation. Adding the family would add measured code and introduce a competing modality owner, while product budgets have very little remaining JavaScript headroom. Reka remains a viable selective option for a later real combobox/menu requirement; it is not rejected on unsupported compatibility or security claims. No product dependency or lockfile change results from the probe.

## Preservation / integration boundaries

- #1004/PR1008 recording labels, #1005/PR1007 notification help and #1012 storage contrast remain existing separately owned fixes. This foundation does not rewrite their consumers or claim full application A11y acceptance before their integration.
- Existing API/store, auth/session, realtime, player, cleanup and storage semantics remain owned by their current modules. Pending is no longer a temporary component-local flag around a synchronous emit.
- The generated frontend inventory is regenerated from actual current source. Its known b7 drift removes two already absent breakpoint declarations (96→94); the rest records new files and current source locations. No obsolete b7 inventory is treated as the current source of truth.
- Initial own product base is #969 `b7c489944bb05575831990bb386d57447e7c028f`. The owner subsequently published #969 `204bf25e5d697702e326e471dc672b581cf4792e` containing the separately reviewed #975 dependency prerequisite; integrate that normally, with no copied patch or history rewrite.

## Verification status

Evidence is recorded in the same-card handoff and final verification section once all final-head checks complete. Interim runs: 502 unit passes / 4 existing skips; types and lint (0 errors / 132 warnings) pass; built REAL stateful settings fixtures 8/8 pass at 320/390/1024/1440 in both themes, including held pending, GET-confirmed save/reload, accepted-but-unpersisted 202 and failed saves. New modal isolation regression failed before adaptation, then passed alongside existing focus restoration. These interim numbers are not a final-head CI or whole-product acceptance claim.

No physical devices, installed PWA, live provider or manual screenreader acceptance is claimed. Browser names and final backend/DB effects are reported separately from synthetic HTTP fixtures. No merge, release, deployment or issue closure is performed by this worker.
