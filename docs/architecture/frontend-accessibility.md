# Accessibility baseline and test plan

## Target

WCAG 2.2 AA is the minimum. Automated axe is necessary but cannot establish keyboard, focus, screen-reader, touch or native-platform acceptance alone.

## Existing evidence and findings

- `axe-core` is locked at 4.13.0 and existing E2E tests inject it, but the initial `npm run test:e2e` had 96 launch failures before page execution because the exact Chromium binary was missing.
- The source inventory records native dialogs, `v-html`, non-semantic click targets, direct DOM mutations, target-size candidates and every relevant route/component path.
- Focus, overlay and native confirmation hotspots include AppShell, BaseModal, BaseSheet, VideoModal, Notifications, Streamers, Videos and subscription components.
- The initial touch-audit helper was independently shown to miss closed-details summary, visually exposed aria-hidden and role-slider controls. P1 RED tests now preserve these categories; the three new tests passed after the implementation correction. Semantic hiding is an accessibility finding, not a reason to omit a visible hit target from geometry audit.
- Chromium collection exercised the same serialized helper on all 17 source-derived router scenarios across the required matrix and both themes. It recorded 1168 hit-test, 608 overlap and 270 undersized findings in 748 observations. Four representative axe/tree/keyboard observations recorded four serious or critical axe results. These are recorded findings, not waived acceptance.

## Harness coverage

| Layer | Contract | Evidence type |
| --- | --- | --- |
| unit | undersized, overlap, hit-test, hidden/disabled exclusions, closed summary, aria-hidden, role slider | 7 focused Vitest assertions |
| browser | axe serious/critical results, accessibility-relevant headings, Tab focus, screenshots | Playwright baseline project artifacts |
| future manual | landmarks, reading order, dialogs, player controls, validation errors, screen-reader behavior | documented native/browser observation |

The browser audit targets buttons, links, form controls, summary, relevant ARIA roles including slider, tabindex candidates and rendered geometry. It deliberately neither force-clicks nor accepts broad selector exclusions.

## Accessibility requirement ledger

| Prompt section/lines | Current evidence | Required phase/test | Status |
| --- | --- | --- | --- |
| semantics 1560-1578 | source inventory | native button/link replacement, named icons, headings/landmarks | pending |
| keyboard 1579-1593 | current overlay and card tests | route, overlay, menu, player keyboard workflows | pending |
| focus 1595-1604 | useModal hotspot decision | focus-visible, trap, restoration, obscured-focus tests | pending |
| contrast/motion 1606-1628 | existing style/axe scan | both-theme axe and reduced-motion/forced-color matrix | pending |
| reflow/text 1629-1638 | viewport matrix declared | 200% text and 400% reflow checks | pending |
| interaction 1640-1649 | rendered audit helper | complete route/overlay/player target audit | pending |
| manual inspection 1650-1664 | no manual/native proof | documented assistive-technology checklist | pending |

No moderate, serious or critical issue is waived by an empty exception file. Later exceptions require selector, exact route, reason, accountable owner and expiry/follow-up issue.
