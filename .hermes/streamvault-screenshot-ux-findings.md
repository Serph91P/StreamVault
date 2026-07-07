# StreamVault screenshot UX findings

Date: 2026-07-06
Branch: feat/frontend-product-overhaul-final
Base: origin/develop at aa6a134d, PR #702 merged
Status scale: open, in progress, fixed, verified

## Purpose

The user supplied screenshots after PR #702 and called out visible product issues. These are treated as real defects, not optional polish. Each finding below maps to a concrete implementation task so later work cannot close as documentation-only.

| ID | Visible problem | Affected pages | Violated UX principle | Concrete design measure | Kanban task ID | Status |
| --- | --- | --- | --- | --- | --- | --- |
| UXF-001 | Too much empty space and low useful density. Large panels stretch without content value. | Dashboard, Streamers, Library, Settings, Streamer Detail | Minimalist design, information scent, fold prioritization | Recompose pages around compact status strips, denser cards, useful low-data states and responsive content grids. | E-DASH-001, F-STREAMERS-001, G-DETAIL-001, H-LIBRARY-001, K-SETTINGS-001 | open |
| UXF-002 | Sidebar and topbar feel heavy and occupy too much room. Global actions look bolted on. | Desktop App Shell, Mobile App Shell, Dashboard | Aesthetic and minimalist design, Fitts law, recognition over recall | Reduce chrome weight, prioritize global utilities, make queue, notifications, theme and logout a coherent utility cluster. | D-SHELL-001 | open |
| UXF-003 | Streamer Detail uses a large red hero with little useful information. | Streamer Detail Overview | Visibility of system status, progressive disclosure | Replace large hero with compact control header showing profile, status, live or recording state, last activity and primary action. | G-DETAIL-001 | open |
| UXF-004 | Streamer Detail actions are squeezed together and destructive actions sit near routine actions. | Streamer Detail all tabs | Error prevention, user control, danger separation | Move destructive actions into overflow or danger zone with confirmation. Keep primary actions visible and safe. | G-DETAIL-002 | open |
| UXF-005 | Streamer Detail tabs look tiny and lost, overview has only simple metric cards and empty space. | Streamer Detail Overview, Videos, Events, Recording Settings | Information architecture, Hick law, status visibility | Rebuild detail as a control center with segmented subnavigation, contextual panels, recent recordings, current recording state and event timeline shell. | G-DETAIL-003 | open |
| UXF-006 | Events empty state sits in a huge blank area. | Streamer Detail Events | Help and documentation, recognition over recall | Add timeline-ready empty state explaining which events will appear and how realtime updates work. | G-DETAIL-004 | open |
| UXF-007 | Videos in Streamer Detail are plain rows with weak media affordance. | Streamer Detail Videos | Match between system and user expectation, media UX | Use media cards or dense media list with thumbnail, title, date, duration, size, processing state and actions. | G-DETAIL-005, H-LIBRARY-002 | open |
| UXF-008 | Recording Settings are a long form wall with weak grouping. | Streamer Detail Recording Settings, Settings Recording | Progressive disclosure, form usability | Split into settings cards for basic, quality, storage, automation, advanced and danger. Keep save actions contextual. | G-DETAIL-006, K-SETTINGS-002 | open |
| UXF-009 | Settings feel like a technical form warehouse with nested sidebar plus app sidebar. | Settings Overview and subsections | Information architecture, cognitive load, Hick law | Rebuild Settings as a modern settings app with category cards, clear section navigation, basic vs advanced split and admin diagnostics escape hatch. | K-SETTINGS-001 | open |
| UXF-010 | API Keys panel is raw and developer-heavy. | Settings API Keys | Match to user language, security clarity | Present as a Security and Developer panel with key state, risk explanation, copy, regenerate and revoke affordances. | K-SETTINGS-003 | open |
| UXF-011 | PWA and Mobile reads like a status list instead of a guided setup. | Settings PWA and Push | Task flow design, permission priming | Build a guided install and push flow with value explanation, prerequisites, permission state, subscribe state and recovery copy. | L-PWA-001 | open |
| UXF-012 | Notification Settings use broad desktop tables that will break or scroll on mobile. | Settings Notifications, Subscriptions | Responsive design, WCAG reflow | Keep tables only on desktop. Add responsive cards or lists below tablet widths. | K-SETTINGS-004, N-QA-RESPONSIVE-001 | open |
| UXF-013 | Library does not feel like a modern media library. A small card sits in a huge blank region. | Videos / Library | Media UX, information density, low-data design | Rebuild with stronger media grid and list, filters, search, low-data composition and video cards with thumbnail and metadata. | H-LIBRARY-001 | open |
| UXF-014 | Streamers does not feel like a modern creator grid. Cards look isolated and status language is not strong enough. | Streamers | Recognition over recall, status consistency | Rework creator cards and grid density, strengthen live, recording and offline status, make Add Streamer primary. | F-STREAMERS-001 | open |
| UXF-015 | Dashboard is improved but still feels empty or stretched in some sections. | Dashboard | Visibility of system status, fold prioritization | Rebuild above-the-fold around live, recording, queue, failures and recent activity with compact quick actions. | E-DASH-001 | open |
| UXF-016 | Visual hierarchy is weak. Panels look too similar regardless of purpose. | All core pages | Consistency and standards, semantic hierarchy | Define status, content, settings, danger, diagnostics and media panel variants in the design system and apply them. | C-DS-001 | open |
| UXF-017 | Modern colors exist, but product polish and flow are missing. | All product flows | End-to-end task flow, performance UX, WCAG | Use Nielsen, JTBD, task flows and responsive QA as acceptance gates for each core route. | B-SPEC-001, N-QA-001 | open |

## Gate rule

No final overhaul PR may be called complete while any productive route still shows the same finding without either a fixed and visually verified status or a blocked status with a concrete reason.
