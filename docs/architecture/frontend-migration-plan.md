# Frontend modernization migration plan and requirement ledger

## Scope boundary

This branch delivers P0 inventory, measured build/gate baseline and executable regression-harness foundations. It does not claim broad production modernization, native acceptance, backend changes, Docker/CI changes, release or deployment.

## Staged migration

1. P0/P1: inventory, baseline reports, deterministic mock harness, rendered target audit, narrow exception schema.
2. Responsive/token owner: one generated responsive source, parity tests, behavior-preserving aliases.
3. Shared UI owner: evolve useModal and primitives with one overlay manager and focus/lock invariants.
4. Shell/forms/data owners: route-specific mobile layouts, safe areas, responsive data views and validation.
5. API/realtime/PWA owner: typed compatibility boundary, lifecycle ownership, manifest/worker consolidation.
6. Player owner: local media fixture, cleanup/error/keyboard landscape contracts.
7. Hardening owner: a11y, security, performance budgets, CI materialization and full integration/native acceptance.

## Complete prompt ledger

| Prompt lines/section | Existing evidence | Gap | Proposed phase | Test/artifact | Status |
| --- | --- | --- | --- | --- | --- |
| 5-49 repository and mission | verified base/issue/prompt SHA | full program remains | all | handoff | pending |
| 63-95 product targets/identity | existing Vue/themes observed | device-specific UX | route owners | matrix/screenshots | pending |
| 101-180 compatibility | API/router/WS source inventory | contracts not fully exercised | API/integration | API/WS media tests | pending |
| 186-235 quality/touch policy | new helper and matrix declared | route results | P1/hardening | JSON geometry reports | pending |
| 238-328 phase 0 | generated JSON, six docs, gate logs, Chromium artifact reports | Firefox/WebKit and native capture remain blocked | P0/P1 | baseline reports | captured with open defects |
| 331-403 viewport matrix | exact config values and Chromium 17-route/22-row/both-theme collection | run Firefox/WebKit after approved runtime setup | P1 | Playwright artifacts | partial: Chromium only |
| 405-448 staged delivery | commit plan | later production slices | owners | phase commits | pending |
| 451-571 architecture/TS | source finding/target contract | migration | architecture | unit/type suite | pending |
| 574-715 tokens/responsive | owner decision source | generator not materialized | responsive | parity/boundary tests | pending |
| 718-850 touch/mobile layout | helper and audit contract | actual route/overlay audit | mobile | audit report | pending |
| 853-1001 shell/overlays | source hotspots/owner decision | central manager | shell/overlay | focus/lock cases | pending |
| 1004-1122 forms/data | source inventory | shared primitives and mobile data | forms/data | keyboard/reflow tests | pending |
| 1124-1245 route requirements | routes inventoried | each route modernization | feature owners | workflow matrix | pending |
| 1248-1338 player/HLS | local fixture and source audit | browser/backend player contracts | player | local HLS, MP4/Range tests | pending |
| 1340-1552 PWA/API/realtime | source inventory | authoritative owners | PWA/API/realtime | worker, auth, WS tests | pending |
| 1555-1879 accessibility/security/perf | docs/build data | full hardening | hardening | axe/manual/Lighthouse | pending |
| 1881-2041 test infrastructure | Vitest/Playwright baseline | component/real-backend fixture tiers | test owners | 28 workflow suite | pending |
| 2043-2129 CI/CD | current CI read | no CI changes authorized now | CI owner | blocking jobs/artifacts | pending |
| 2132-2253 explicit hotspots | inventory and source notes | focused remediation | respective owner | source-backed regressions | pending |
| 2256-2418 Definition of Done | categories tracked below | all final criteria | all owners | final acceptance ledger | pending |
| 2421-2487 commits/PR | Conventional commit requirement | eventual final PR content | finalizer | 30-item PR checklist | pending |

## Critical E2E workflow ledger

1 initial setup; 2 onboarding; 3 login; 4 logout confirmation; 5 dashboard/realtime; 6 streamer search/filter; 7 detail/back scroll; 8 add streamer; 9 enable/disable auto recording; 10 start/stop synthetic recording; 11 live player; 12 live error recovery; 13 library search/filter; 14 layout change; 15 multi-select; 16 cancel/confirm deletion; 17 stored player; 18 notification open/close; 19 mark read; 20 clear notifications; 21 queue; 22 settings save; 23 failed save recovery; 24 PWA install; 25 PWA update; 26 offline/online; 27 WS reconnect; 28 session expiry.

P0/P1 exercises deterministic mock route geometry and cross-engine a11y harness design only. It does not mark these 28 workflows passed.

## Definition-of-done tracker

Architecture, mobile, touch targets, accessibility, players, PWA, quality, performance, compatibility and verification are each pending final owner acceptance. Required final evidence includes real backend smoke, mock visual suite, local HLS tests, both themes, portrait/landscape, installed-PWA where automation permits and reports attached to PR/CI. No placeholder or broad TODO can be accepted at finalization.

## Integration prerequisites and capability boundaries

The local fixture at `/opt/data/profiles/developer/work/streamvault-frontend-modernization/local-hls/` is a six-second H264/AAC VOD with three TS segments, FFmpeg-decoded successfully. It is credential-free and proves fixture generation/decoder capability only, not browser playback, live behavior, auth or backend routing.

The source audit at `/opt/data/profiles/developer/work/streamvault-frontend-modernization/integration-prerequisites.md` records that real app startup has migration, image, EventSub and cleanup effects; test startup must isolate environment explicitly. Stored playback is Range-served MP4/file and demands legacy `session`; normal login supplies access/refresh cookies. Preserve a fresh-login stored-media regression rather than masking it with a seeded legacy session. Live HLS playlist and segments require actual playback-token tests. Current mock stored video points to a public Google sample and must be replaced by local fixture use before hermetic player acceptance.

Browser install is not browser acceptance. Chromium can launch in the owner probe, but Firefox needs `libgtk-3-0t64` and WebKit needs GTK4/GStreamer-related libraries. The full engine matrix remains pending until task-owned dependencies or a matching verified container are available. Native Android/iOS/Windows/macOS evidence is a separate manual gate.

## Final PR 30-item checklist

1. Executive summary
2. Exact base and candidate head
3. Motivation
4. Baseline evidence
5. Existing architecture
6. Target architecture
7. Design system
8. Mobile policy
9. Touch audit
10. Accessibility
11. Route changes
12. API compatibility
13. WebSocket compatibility
14. PWA behavior
15. Player behavior
16. Browser matrix
17. Screenshots
18. Performance evidence
19. Bundle evidence
20. Tests
21. CI
22. Docker
23. Preference migration
24. Rollout
25. Rollback
26. Limitations
27. Risks
28. Follow-ups
29. Changed files
30. Explicit `develop` target
