# StreamVault frontend PR #702 gap report

Date: 2026-07-06
Branch: feat/frontend-product-overhaul-final
Base: origin/develop at aa6a134d
Reference PR: #702, `feat: complete frontend overhaul v2`, merged 2026-07-06
Frontend path: app/frontend

## Executive summary

PR #702 was a useful foundation pass, not a finished product overhaul. It added architecture cleanup, a new shell boundary, initial page header work, domain stores and several QA or design artifacts. Its own PR body and QA files explicitly recorded missing viewport, Lighthouse, axe, Web Vitals, real WebSocket, real HLS and real push delivery validation. The feature parity map still used non-final status values such as `rebuild further`, `keep and improve`, `keep`, `capsule`, `admin-only` and `partial` language. Therefore this follow-up must create real implementation tasks for the core product pages, not another documentation-only closure.

## What PR #702 really improved

Evidence: `gh pr view 702`, `git show --stat aa6a134d^..aa6a134d`, `.hermes/streamvault-frontend-overhaul-summary.md`, `.hermes/streamvault-frontend-qa-report.md`.

| Area | Improvement | Evidence |
| --- | --- | --- |
| App shell | `App.vue` was reduced and `AppShell.vue` was introduced. | PR #702 changed `App.vue` by 355 lines and added `components/AppShell.vue` with 380 lines. |
| Shared page pattern | `PageHeader.vue` was added. | `app/frontend/src/components/base/PageHeader.vue` added in PR #702. |
| Domain state | Recording, queue and notification state were improved or extracted. | Added `stores/recordings.ts`, `stores/backgroundQueue.ts`, `services/recording.ts`; updated notification store. |
| PWA ownership | VitePWA registration path was cleaned up and push worker import was checked. | PR summary and QA report list VitePWA ownership and `push-sw.js` import check. |
| Notification center | Read state, mark all read, target links and focus behavior were improved. | PR summary and changed files include `NotificationFeed.vue`, `NotificationItem.vue`, notification store. |
| Admin separation | Some debug or test actions moved toward Admin Diagnostics or dev-only paths. | PR summary and QA report mention PWA and notification test actions moved from normal settings. |
| Documentation and planning | Multiple `.hermes` artifacts were created. | Ten `.hermes/*.md` files added in PR #702. |
| Local static checks | Frontend lint tokens, type-check, build and lint passed in that PR. | PR #702 body and QA report. |

## What was only documented or only foundation

| Area | Why it is not final |
| --- | --- |
| UX direction | `.hermes/streamvault-ux-ia-concept.md` describes desired IA, journeys and progressive disclosure, but many central screens still require rebuild tasks. |
| Design system | `.hermes/streamvault-design-system.md` defines desired primitives and gaps, but the artifact itself does not implement the missing components. |
| Feature parity | `.hermes/streamvault-feature-parity-map.md` preserved routes, but several productive routes stayed at non-final statuses. |
| QA | `.hermes/streamvault-frontend-qa-report.md` documents limitations for viewport, Lighthouse, axe, Web Vitals, real backend WebSocket, HLS and push device testing. |
| Visual finish | The user-provided screenshots after PR #702 still show empty space, heavy chrome, unfinished detail views, settings form walls and weak media UX. |
| Page structure | Several core views were touched, but PR #702 did not prove the Dashboard, Streamers, Library, Settings and Streamer Detail flows are finished product experiences. |

## Source-verified drift and component gaps

Additional read-only subagent review after the initial report confirmed several concrete gaps that are useful for implementation planning:

- `App.vue` is lighter than before, but it still contains inline icon sprite ownership while `components/icons/IconSprite.vue` also exists. The root is therefore not yet a pure orchestration shell.
- Navigation labels treat `/videos` as Library, but `VideosView.vue` still renders a `PageHeader` title of `Videos`, so product language is not fully aligned.
- The design-system artifact still names unimplemented or unconsolidated primitives: `SectionHeader`, `IconButton`, `BaseToggle`, `SegmentedControl`, shared `ErrorState`, consolidated status badges and queue or job status items.
- The architecture audit still asks for large view splitting, additional Recording, Streamer, Video, Settings, PWA and UI stores, route metadata for labels, auth and shell behavior, and `AdminPanel` modularization.
- Many local `btn-*`, badge, toggle, filter and card patterns remain in product pages, so PR #702 did not fully enforce the target component system.

## Core pages not final after PR #702

| Core area | Current PR #702 parity status or evidence | Gap to close |
| --- | --- | --- |
| Dashboard | `rebuild further` in parity map | Must become status-first, dense and understandable in under 3 seconds with live, recording, queue, errors and recent activity visible. |
| Streamers | `rebuild further` in parity map | Needs creator-grid overhaul, stronger status language, denser cards, better filters and clear Add Streamer CTA. |
| Streamer Detail | `rebuild further` in parity map | Needs compact control-center header, safe action hierarchy, rebuilt Overview, Videos, Recording Settings and Events. |
| Videos / Library | `rebuild further` in parity map | Needs modern media library composition, stronger video cards, low-data states, search/filter/sort polish and mobile media layout. |
| Settings | `rebuild further` in parity map | Needs settings-app IA, basic vs advanced split, danger zones, contextual save, responsive notification tables and guided PWA/Push flow. |
| Stored Video Player | `keep and improve` in parity map | Needs visual and functional verification of loading, HLS or file error recovery, mobile controls and lazy initialization. |
| Live Player | `keep and improve` in parity map | Needs real or realistic HLS validation, status language, mobile controls and recovery states. |
| Notification Center | `keep and improve` in parity map | Needs first-class product surface, filtering, read/unread, dedupe, target links and mobile sheet or route evidence. |
| PWA and Push | `keep, test actions moved to Admin Diagnostics` in parity map | Needs guided install and permission flow plus real or reality-based device QA. |
| Admin Diagnostics | `capsule` or `admin-only` wording | Needs final separation from normal flows and disclosure of raw diagnostics. |
| Add Streamer, Auth and Setup | `keep and improve` or `keep` | Needs mobile and onboarding evidence, not just route preservation. |

## Non-final status values still present

The PR #702 parity map includes terms that the new prompt forbids as final states:

- `rebuild further`
- `keep and improve`
- `keep`
- `capsule`
- `admin-only`
- `partial pass`
- `known validation limits`
- `mock mode`
- `limitations`

These must be replaced only after real implementation and verification with allowed final states:

- `implemented and visually verified`
- `implemented and functionally verified`
- `intentionally admin-only`
- `intentionally dev-only`
- `intentionally removed with reason`
- `blocked with reason`

## QA limitations from PR #702 that remain hard gates

| Gate | PR #702 state | Follow-up requirement |
| --- | --- | --- |
| Viewport matrix | Not fully covered. 1280 desktop and one 375 mobile capture only. | Capture 390, 430, 768, 1024, 1280 and 1440 where tooling allows. Block final completion if impossible. |
| Lighthouse | Not run. | Run Lighthouse or document real blocker. Do not mark performance passed without measurement. |
| axe | Not run. | Run axe or equivalent accessibility scan. Do not replace with visual inspection only. |
| Web Vitals | LCP, INP and CLS not measured. | Measure or mark performance gate blocked. |
| Real backend WebSocket | Mock mode only. | Validate against real backend or explicitly block this QA task. |
| HLS media playback | Mock mode could not validate real media. | Validate stored and live playback with realistic media or block. |
| Push device delivery | Not validated. | Validate real or reality-based device push flow, or block PWA gate. |
| Mobile tables | Not proven across requested widths. | Replace or verify responsive card/list alternatives. |
| Visual evidence | Incomplete matrix. | Store required evidence under `.hermes/frontend-visual-evidence/`. |

## User flows still klunky or unfinished

| Flow | Current issue | Implementation direction |
| --- | --- | --- |
| Open app and assess health | Dashboard still has empty and stretched sections in screenshots. | Above-the-fold status summary with queue, live, recording, failures and recent activity. |
| Scan streamers | Cards feel isolated and low density. | Creator grid or list with strong live, recording and offline language plus fast filters. |
| Manage one streamer | Large hero, cramped actions and empty tabs undermine control-center feel. | Compact streamer header, separated danger actions, segmented subnav and useful tab content. |
| Find media | Library low-data state looks like a small card in blank space. | Media-first grid/list, strong video cards, filters and useful low-data state. |
| Configure safely | Settings feel like long technical forms. | Category cards, contextual saves, basic and advanced separation, danger zones. |
| Enable PWA or Push | Existing UI reads like a status list. | Guided setup flow with permission priming, state, next action and recovery. |
| Use notifications | Center improved but not proven as product feature across desktop and mobile. | Filterable notification product surface with target links and read state verification. |
| Use on mobile | Bottom nav exists, but full matrix not proven and tables remain risky. | Mobile-first layout checks, 44px targets and responsive table alternatives. |

## Views likely still too large or hard to maintain

PR #702 reduced some files, but current follow-up must inspect and potentially split these areas before implementation. A read-only line-count check after PR #702 flagged these hotspots:

| File | Approximate size after PR #702 | Why it matters |
| --- | --- | --- |
| `app/frontend/src/components/VideoPlayer.vue` | 1786 lines | Player state, media controls and recovery UI are too coupled for final player QA. |
| `app/frontend/src/components/StreamList.vue` | 1770 lines | Stream list behavior likely mixes status, filtering and rendering concerns. |
| `app/frontend/src/components/admin/AdminPanel.vue` | 1772 lines | Diagnostics remain too monolithic for a clean admin capsule. |
| `app/frontend/src/views/StreamerDetailView.vue` | 1461 lines | Control-center tabs, actions and settings need decomposition. |
| `app/frontend/src/views/VideoPlayerView.vue` | 1280 lines | Stored playback route needs clearer loading, recovery and context boundaries. |
| `app/frontend/src/views/SettingsView.vue` | 1247 lines | Settings still risks becoming a form warehouse without section components. |
| `app/frontend/src/views/HomeView.vue` | 1242 lines | Dashboard needs smaller status-first sections and clearer realtime projection. |
| `app/frontend/src/views/LivePlayerView.vue` | 1238 lines | Live playback needs separated HLS, status and recovery concerns. |
| `app/frontend/src/views/VideosView.vue` | 1059 lines | Library needs media browsing components and store-backed state. |
| `app/frontend/src/components/cards/StreamerCard.vue` | 1055 lines | Creator card needs split status header, metadata and actions. |
| `app/frontend/src/views/StreamersView.vue` | 982 lines | Search, filters, list state and responsive creator grid need cleaner boundaries. |

The exact split should be driven by the redesign spec and verified against source before coding.

## Missing tests and product acceptance

Required but not proven by PR #702:

- Full route visual evidence matrix.
- Mobile Settings verification.
- Mobile Notification Center verification.
- Keyboard traversal across dialogs, sheets, forms and bottom navigation.
- Automated or equivalent accessibility check.
- Lighthouse or Web Vitals production-preview measurement.
- Real backend WebSocket behavior.
- Real or realistic HLS stored and live playback.
- Real or reality-based push device delivery.
- Responsive transformation for desktop-heavy tables.
- Before and after visual rationale for screenshot findings.

## Screenshot problems still considered open

See `.hermes/streamvault-screenshot-ux-findings.md`. The following categories remain open until implementation plus visual evidence proves otherwise:

- Empty space and weak density.
- Heavy app chrome.
- Unfinished Streamer Detail control center.
- Settings as form warehouse.
- Library lacking media-app feel.
- Streamers lacking creator-grid polish.
- Dashboard not fully status-first.
- Desktop-heavy tables.
- Weak hierarchy across panels.
- Modern colors without complete modern UX.

## Phase 0 decision

The follow-up must proceed with real Kanban implementation tasks. Documentation alone is explicitly insufficient. The next required artifacts are:

1. A hard feature parity map using only allowed final statuses.
2. A concrete redesign specification per core page.
3. Implementation tasks that modify `app/frontend/src`, `app/frontend/public` or frontend styles.
4. Visual evidence under `.hermes/frontend-visual-evidence/` before any final complete PR.
5. A QA scorecard that blocks completion if any hard gate is missing.
