# #1015 UX foundation — implementation ledger

## Contract

Issue/PR repository and push remote: `Serph91P/StreamVault`; base `develop`; branch `feat/1015-ux-foundation`; board `streamvault`, task `t_0a50864e`. Own delta starts at published prerequisite #969 `b7c489944bb05575831990bb386d57447e7c028f`. Scoped commit/push/draft PR authorized; no merge/deploy/issue closure.

Goal: one product-integrated foundation for channels, recordings and activity. Backend/store owners remain authoritative; acceptance is never completion. Preserve existing functions, theme tokens and modal/toast ownership. #1004/#1005/#1012 and other domain fixes stay with their owners.

## Product playbook

Operate mode: quiet neutral surfaces, a clear primary action, German product vocabulary, spacing/dividers rather than nested cards. Existing accepted issue/concept supplies product truth; no discovery interview or mockup restart. `design.tokens.json` remains the only semantic token source. Native inputs/selects and the proven modal stack stay unless a measured primitive probe demonstrates a concrete advantage.

## Steps / shared interfaces

1. Bind source with Graphify and Serena; inspect actual components, consumers and tests. Clean b7 verified; Graphify 0.9.92 indexed 677 tracked code files (`no_known_gaps` within suffix/shell scope), real useToast query resolved to source; Serena useModal overview resolved in exact worktree.
2. RED→GREEN: extend **existing EmptyState** with typed presentation states (not a fetch/store engine), retain its legacy interface; toast live semantics, close name and touch target; Base form hint/error associations. Test rendered output and dismiss behavior.
3. Connect browse/detail/form/operation consumers: channel collection resource states, channel-detail load failures, recording settings native Base fields and owner-provided pending/result feedback. Shared presentation states cannot infer confirmation from HTTP or timers.
4. Probe actual selective Reka imports against installed Vue/TS/Vite; inspect official docs, peers/license/security and bundle measurements. Keep working primitives if replacement adds cost without closing a proven gap.
5. Extend existing foundation harness for min/max, field errors, states and nested overlays; run unit/static/foundation gates, REAL/MOCK provenance/budgets, built-browser regressions and actual local backend acceptance separately from fixtures.
6. Self-review for correctness, gate integrity, test value and real QA. Scoped commits, branch push, draft PR (Closes #1015, dependency #969), exact-head CI/security review, same-card independent review.

Shared interfaces: EmptyState legacy props must remain compatible with all existing callers; state presentation consumes owner facts only. RecordingSettingsPanel update event remains unchanged; parent owns asynchronous persistence and exposes pending/result props. Modal useModal and useToast singleton stay unchanged.

## Review correction B1

- Scope: restore the existing pointer dismissal for AppShell notifications and BackgroundQueueMonitor only; retain the existing modal stack, focus container, keyboard routing and isolation of lower overlays/background.
- Reproduction: four REAL production-frontend pointer cases (both panels × both themes) fail after an actual outside click at (5,500), plus the separate-backdrop stack unit test fails because the active backdrop is inert. This matches MDN's native inert contract, not a CSS or transition issue.
- Fix: optional explicit backdrop ref on the existing modal owner; only the top stack entry's registered backdrop remains interactive. Both actual consumers register their own ref. No CSS-class wildcard exemption, extra stack, dependency or state platform.
- Budget-preserving cleanup within the affected owner: combine duplicate lifecycle watches, use native stack `.at(-1)`/collection iteration, remove redundant closed-state guards and the unused notification trigger ref. Existing keyboard, autofocus, unmount and restore behavior stays tested. Budgets are unchanged; MOCK initially failed at 1,196,683 raw / 381,043 gzip, final is 1,196,522 / 381,000 (zero gzip reserve).
- Fresh final-source checks: 664 units / 4 existing skips; 49 foundation; types/lint (0 errors / 135 warnings)/tokens/generator; 34 REAL + 34 MOCK settings, 19 REAL HTTP-fixture state/parity/pointer cases, 22 channel/dialog cases, 18 actual Chromium/Firefox/WebKit foundation cases; repeat MOCK clean-build identity. REAL is 1,193,392 / 380,071; precache REAL81/MOCK80. Exact-head CI/security and final real-backend replay are recorded in the correction handoff; do not reuse earlier heads as final evidence.

## Final forward-composition correction

- Develop advanced to04f75376 (#1044/#946) during CI. Normally merged as4c9d73ce; four new retention tests reproduced RED on their old native-ID locator, then8/8GREEN using the actual German label/for relationship. All retention transport/store assertions unchanged; the published fix is preserved, not reimplemented.
- Composed MOCK1196812/381080RED. Existing foundation cleanup only: authoritative modal-stack size replaces duplicate lock counter; native Object.assign restores only saved lock styles; named isolation tuples; equivalent toast icon lookup/direct remove alias. A separate field-helper probe increased gzip and was discarded; no new helper/platform/dependency remains.
- Final product inputs: REAL1193304/380024;MOCK1196421/380980 (20gzipBytes reserve), both unchanged gates; two clean MOCKbuilds identical.677Units/4existingSKIP,49Foundation,types/lint0errors135warnings/tokens/generator,34REAL+34MOCKSettings,19State/Parity,22Channel/Dialog,18Foundation+12B1Pointer/Nested actual-engine cases,2original actualSQLite/media/restart/replay journeys PASS. Final CI/security/head binding belongs in correction handoff, no earlier green reused.

## Evidence / progress

- Intake complete: correct clean branch/head/remotes and live issue/PR metadata. Owner's inventory drift was restored before this run. Initial graph output and binding are external scratch, not repository artifacts.
- Implementation and local verification complete; independent same-card review and final exact-head CI remain gates. Product commits d6b1974c/f14e6cd; published prerequisite merged normally, then integrated develop21126206. The final follow-up changes only deliberately programmatic overlay tests and generated source locations.
- RED→GREEN evidence covers presentation states, toast semantics, associated persistent field guidance, pending draft retention, stale channel retention, detail retry, nested background isolation and rendered timestamp alignment. No thresholds, timeouts, references or existing assertions relaxed.
- Local: 504 units / 4 existing skips; 49 foundation gates; types/lint/tokens/generator; 14 built REAL HTTP-fixture cases; both real production-factory/SQLite/media journeys; 18 foundation browser cases across actual Chromium/Firefox/WebKit and six existing dialog/stack replays pass. REAL and MOCK budgets/provenance/precache and MOCK consecutive-build identity pass. MOCK gzip headroom is only 103 bytes; do not raise the budget.
- Full initial local engine run is not all green: 213 pass / 46 existing skip / 25 fail, consisting of four now-corrected hidden-trigger test adapters and 21 local container visual-reference differences. Native first-head CI passed all 21 references (234 pass / 46 skip / exactly those four adapters failed). Final exact-head CI must be read afresh, not inferred from these results.
