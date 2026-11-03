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
| Actual existing BaseModal, including adapted useModal/focus dependencies | 5,841 | 2,418 |
| Only Reka DialogRoot/Trigger/Portal/Overlay/Content/Title/Description/Close | 42,747 | 11,563 |

The current TypeScript 6 compiler accepted the actual Reka imports with bundler resolution (`tsc --ignoreConfig --noEmit --moduleResolution bundler --module esnext --target es2022 --skipLibCheck .../reka.ts`). The first invocation correctly required TS6's `--ignoreConfig`; no compiler downgrade was used. The figures are library-output comparisons, not a fabricated full-application bundle delta or a declaration that Reka cannot ever fit. The probe exports the exact named family, excludes Vue and does not include unrelated Reka components. The existing facade additionally emits 920 CSS bytes (400 Vite gzip bytes); Reka is unstyled.

Decision: **retain the proven native/Base primitives in this increment**. There is no demonstrated unmet complex primitive need after the scoped stack adaptation. Adding the family would add measured code and introduce a competing modality owner, while product budgets have very little remaining JavaScript headroom. Reka remains a viable selective option for a later real combobox/menu requirement; it is not rejected on unsupported compatibility or security claims. No product dependency or lockfile change results from the probe.

## Preservation / integration boundaries

- #1004/PR1008 recording labels and #1005/PR1007 notification help are now integrated from develop. Recording controls retain their German accessible names and unique native label targets behind the Base facades. #1012 storage contrast remains separately owned and is still required before full #1015 issue acceptance; this PR does not duplicate that fix or claim whole-application AA compliance.
- Existing API/store, auth/session, realtime, player, cleanup and storage semantics remain owned by their current modules. Pending is no longer a temporary component-local flag around a synchronous emit.
- The generated frontend inventory is regenerated from actual current source. Its known b7 drift removes two already absent breakpoint declarations (96→94); the rest records new files and current source locations. No obsolete b7 inventory is treated as the current source of truth.
- Initial own product base was #969 `b7c489944bb05575831990bb386d57447e7c028f`. #969 and the separately reviewed #975 dependency prerequisite are now develop ancestors, integrated by normal forward merges without copied patches or history rewrites.

## Worker verification before owner integration (historical)

Evidence is recorded in the same-card handoff and final verification section once all final-head checks complete. Interim runs: 502 unit passes / 4 existing skips; types and lint (0 errors / 132 warnings) pass; built REAL stateful settings fixtures 8/8 pass at 320/390/1024/1440 in both themes, including held pending, GET-confirmed save/reload, accepted-but-unpersisted 202 and failed saves. New modal isolation regression failed before adaptation, then passed alongside existing focus restoration. These interim numbers are not a final-head CI or whole-product acceptance claim.

Subsequent source verification: 504 unit passes / 4 existing skips, 49 foundation-gate passes, types/lint/tokens/generated-foundation pass. The expanded built REAL fixture suite passes 14/14, adding empty/filter-empty/loading/stale-with-retained-channels/403/offline/error/retry at 320/390/1440 in both themes. Visual inspection found a timestamp falling into the icon column; the rendered geometry regression failed (x37 vs heading x148) before explicit content-column placement, then passed. The existing harness passes all six browser cases, including 200% text, touch sizes, Axe, reduced motion, forced colors and nested isolation/focus restore. An initial nested-keyboard test issued Shift+Tab before autofocus; it now first asserts actual initial focus, with no timeout or assertion relaxation.

The existing `tests/browser_acceptance/run.py` also passed both desktop-light and mobile-dark against the REAL build with disposable production factory/routers/services, SQLite and media, zero API fulfills, codec Save/Reload/DB readback, separate channel overrides/cleanup/management, real Uvicorn restart/replay/dedupe, job completion and decoded playback/seek/delete. Owned test container was removed. Repeat against the final source artifact before handoff.

Final local execution repeated both real journeys successfully, with no page errors or failed business API responses. All 18 foundation cases pass in the actual Playwright Chromium/Firefox/WebKit engines. A full local Noble-container run returned 213 pass / 46 existing skips / 25 fail: four deliberately programmatic stack tests still searched for now-inert background controls, plus 21 visual-reference comparisons. The adapter correction explicitly includes hidden controls only for those programmatic DOM clicks and **adds** inert-background/only-top-dialog assertions; all six existing desktop/mobile dialog replays then pass. Native initial CI passed all 21 references (234 browser passes / 46 skips / exactly four adapter failures). No snapshots or tolerances changed, and the local whole-suite result is not represented as all green.

REAL output: 1,191,938 application JS bytes / 379,983 gzip bytes, 82 precache entries. MOCK: 1,195,088 / 380,897, 81 entries, two clean builds byte-identical. Existing budgets pass with only 103 gzip bytes of MOCK headroom. The inherited full dependency audit still reports 27 dev-package entries (2 low / 25 moderate), whereas runtime-only audit reports zero; final PR scanner artifacts and exact-head checks are separately recorded in the handoff.

The source inventory was regenerated after removing owned test/build outputs. The generator excludes `test-results` but not `foundation-test-results`; its generated `.last-run.json` must not enter the source inventory. With those owned outputs removed it reproducibly reports 331 frontend files / 205 backend routes, retaining the documented 94-breakpoint source count. No generator policy or gate was changed. Source and dependency worktree remain available for review; temporary artifacts are retained separately as evidence.

No physical devices, installed PWA, live provider or manual screenreader acceptance is claimed. Browser names and final backend/DB effects are reported separately from synthetic HTTP fixtures. No merge, release, deployment or issue closure is performed by this worker.

## Owner integration verification

The owner integrated the existing develop fixes without replacing their regression tests. Types, the complete unit suite (635 passed / 4 existing skips), lint (0 errors / 136 warnings), token lint and foundation generation checks passed. The recording/notification settings browser suites passed 34 REAL and 34 MOCK cases; the combined state/parity suite passed 15 cases. The unchanged six-case foundation harness passed in all three actual Playwright engines (18 cases), separately from emulated device sizes.

The first combined MOCK artifact exceeded the existing raw-JS and gzip budgets. The fix groups the already co-loaded app entry/runtime and shared feedback, without eagerly loading channel settings. A new cold-channel browser regression verifies that boundary. Repeated static demo metadata is expanded once; an assert-based full-value comparison against the pre-change export confirmed all 12 public recording objects unchanged, including legacy paths. The pure annotation preserves removal of demo-only data from REAL artifacts. No dependency, minifier replacement, budget, timeout, visual reference or assertion relaxation was used.

| Final application artifact | JS bytes | Node gzip bytes | Precache entries |
| --- | ---: | ---: | ---: |
| REAL | 1,193,233 | 379,976 | 81 |
| MOCK | 1,196,483 | 380,954 | 80 |

Both artifacts pass the unchanged output and precache checks with Node 22.23.3 / Vite 8.3.3. MOCK headroom remains small; subsequent features must continue to satisfy the same limits. The source-only inventory contains 352 frontend paths / 205 backend routes, excluding generated harness output.

The real factory/routers/services, disposable SQLite/media and desktop-light/mobile-dark journeys were repeated successfully with zero API fulfills, page errors or failed business responses. Their durable effects include codec save/readback/reload, separate channel overrides, cleanup and management, actual process restart/replay/deduplication, queued job completion and decoded playback/seek/delete. Final exact-head CI, security report readback and independent same-card review remain separate mandatory handoff gates. #1012 and whole-issue acceptance remain with the owner; no physical-device, provider, installed-PWA or manual screenreader result is inferred from these tests.
