# Frontend dependency advisory disposition (#968)

## Scope and result

Checked against develop `36e968774bb41b222296a75b3a406c0be385badd` on 2026-10-31 using Node 22.23.3 / npm 10.9.9. All identified nodes are development dependencies. This is build/test supply-chain exposure, not evidence of an exploitable shipped Vue runtime vulnerability.

| State | Full lock audit | Installed audit after npm ci | Runtime (`--omit=dev`) |
| --- | --- | --- | --- |
| Original develop | 18 unique advisory IDs / 35 affected entries: 4 high, 27 moderate, 4 low | Same | 0 |
| Reused published high fix | 8 unique IDs / 31 entries: 0 high, 27 moderate, 4 low | Not separately measured at this intermediate state | Not separately measured |
| This candidate | 3 unique IDs / 27 entries: 0 high, 25 moderate, 2 low | Same | 0 |

Full audits still exit **1**. `npm audit --audit-level=high` exits **0**, but is not a complete clean audit. Entries include dependent-package effects; do not add them to unique advisory counts. No exclusions, security thresholds, budgets, browser coverage, assertions or snapshots changed.

## Compatible repairs

- Reuse only published lock-only commit `207ce46bafb9f460fabebb559f07eb0613c39358` from PR #969, not its product changes: jsdom -> Undici 8.12.3 and Lighthouse -> Puppeteer 25.16.0 -> chromium-bidi -> Zod 4.6.7. This resolves the nine Undici IDs and one Zod ID already addressed there; they are not new findings here.
- Remove the stale `fast-uri: 3.1.8` override. Workbox -> AJV's existing `^3.0.1` resolves 3.1.9. Fixes [GHSA-w74x-v6f9-j3xg](https://github.com/advisories/GHSA-w74x-v6f9-j3xg), [GHSA-xhq7-xmqj-769h](https://github.com/advisories/GHSA-xhq7-xmqj-769h), [GHSA-wjr9-j795-jxcr](https://github.com/advisories/GHSA-wjr9-j795-jxcr), [GHSA-333x-w4r6-6crp](https://github.com/advisories/GHSA-333x-w4r6-6crp).
- Remove the stale `serialize-javascript: 7.1.2` override. Workbox -> @rollup/plugin-terser's existing `^7.0.3` resolves 7.1.4 (first patched version 7.1.3). Fixes [GHSA-m5mm-p8h7-m29v](https://github.com/advisories/GHSA-m5mm-p8h7-m29v). npm initially retained the old node despite targeted update; removing only that stale lock node and letting npm resolve it regenerated the patched registry version without an override.

Four isolated real-package assertions fail on fast-uri 3.1.8 / serialize-javascript 7.1.2 and pass on the installed candidate: encoded-scheme preservation, parent-relative reference preservation, ambiguous-host error and terminal function-source `</script` escaping. No network requests or exploit against an application were performed.

## Remaining advisories: upstream-compatible repair unavailable

Primary GitHub advisory API and live npm package metadata were checked for each entry. The following are explicit unresolved dispositions, **not scanner waivers or an assertion of zero risk**. Do not force npm's suggested historical parent downgrades or transitive major overrides.

| Advisory / installed origin | Actual chains and exposure | Current fix situation / disposition |
| --- | --- | --- |
| [GHSA-gcqx-w48m-w2h4](https://github.com/advisories/GHSA-gcqx-w48m-w2h4), low, deepmerge 4.3.1 | vite-plugin-pwa 1.3.0 -> workbox-build 7.4.1 -> @rollup/plugin-node-resolve 16.0.3 -> deepmerge. Prototype poisoning requires attacker-controlled merge input. The installed resolver calls `deepMerge({}, defaults)` for its frozen internal defaults; it does not pass HTTP/user input there. Untrusted build dependencies/configuration remain a supply-chain trust boundary. | GHSA reports no patched version; npm latest remains 4.3.1 and latest resolver still requires `^4.2.2`. No compatible patched chain exists. Keep finding visible; upstream patch or separately reviewed resolver migration required. |
| [GHSA-3g3m-2fjr-6pw4](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4), moderate, glob 11.1.0 and 13.0.6 | vite-plugin-pwa -> workbox-build -> glob 11; @vue/test-utils 2.5.1 -> js-beautify 2.0.3 -> glob 13. AbortSignal cancellation can leave traversal running, allowing CPU/I/O exhaustion with hostile patterns/trees. Workbox's installed `getFileDetails` uses `globSync` on build output with cwd/follow/ignore and no signal. js-beautify CLI uses `globSync`, also without signal. This is not proof that every dependency entry point is unreachable. | First patched 14.0.2; latest 14.0.3. Latest Workbox still declares `^11.0.1`, latest js-beautify `^13.0.6`, latest test-utils still uses js-beautify. Both repaired major versions are outside current parent contracts. Keep finding visible pending compatible upstream adoption or an explicitly scoped migration with compatibility review. |
| [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249), moderate, minimatch 10.2.6 | ESLint/config-array, typescript-eslint/typescript-estree, test-utils -> js-beautify -> editorconfig/glob, Workbox -> glob and off-main-thread -> ejs -> jake -> filelist. Pattern preprocessing at optimizationLevel >=2 can amplify CPU/memory. Repository lint/test/build patterns are checked-in configuration and local source/build trees, not request parameters. This includes glob-mediated use; do not claim every optimization path is absent. | First patched 11.0.1; latest 11.0.3. Live latest ESLint 10.14.0 and typescript-estree 8.72.1 still require minimatch10; other installed parent ranges also require10. No compatible patched chain established. Keep finding visible; do not force a global major override across unrelated consumers. |

## Executed compatibility evidence

- Fresh `npm ci` succeeds; complete lock and installed audit outcomes above are real executions. Runtime audit and unchanged high-only command pass separately.
- `npm run type-check`, `lint:check`, `lint:tokens`, `check:foundation`, `test:unit`, `test:foundation-gates`: pass. Unit suite: 435 passed / 4 existing skipped.
- REAL production build, MOCK deterministic `test:build-output`, both output budgets and both precache checks: pass, 91 unique precache entries. Limits unchanged.
- Real Chromium fixture configurations: websocket setup 1 pass; system headers 30; long player 9; Pixel player 23; native carousel 3.
- Lighthouse collector on the actual MOCK build, mobile/desktop cold/warm, succeeds using the updated Lighthouse/Puppeteer chain in the native Playwright Linux container.
- Entire unchanged default browser suite runs Chromium, Firefox and WebKit: **171 passed, 46 skipped, 21 failed**. An independent archive of unchanged develop, freshly installed and built in the same container image, reproduces the **same 21 failure names** and totals. Failures are visual references in `pr5-dialogs-a11y`, `pr5-responsive-shell` and `stream-history`; no references were regenerated. This is a genuine pre-existing gate failure, not a successful browser acceptance.

## Completion boundary

This candidate is not an issue-completion or merge claim. Three origins remain unresolved as described above, and the clean-browser / green exact-head-CI delivery requirement is not yet met. Keep #968 open. The owner must resolve the existing develop visual-gate prerequisite without importing the entire #933 product diff or weakening reference checks. Review of the bounded dependency delta must not be confused with whole-product approval.
