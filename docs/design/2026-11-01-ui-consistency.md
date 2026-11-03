# StreamVault UI consistency

## Intent and source

The requested refinement addresses the current develop UI's inconsistent and cluttered presentation. The open channel-first candidate in PR #969 already carries the approved information architecture from issue #933. Continue that candidate (`f2b94e7973989b8702c3fc5b4af9c077e0397d4c`) rather than recreating its workflows on develop (`36e968774bb41b222296a75b3a406c0be385badd`).

The visual direction is a quiet, modern application with the clarity of shadcn-style interfaces: neutral surfaces, consistent hierarchy, legible status labels and restrained blue actions. Both themes and existing mobile behavior remain supported.

## Approach

Considered a new shadcn-vue/Nuxt UI primitive layer and a convergence of the existing Vue primitives. Use the latter: the existing app already has accessible controls, routing, overlays and preserved action behavior. Introducing Tailwind and another component layer would not by itself resolve the overlapping SCSS ownership. No new runtime dependency is needed for this work.

## Visual contract

- `design.tokens.json` is the source for semantic canvas, panel, raised, selected, text, border and action colors. Legacy CSS aliases resolve to the same semantic roles in both themes.
- Neutral dark surfaces: canvas `#101216`, panel `#191c22`, raised `#22262e`, selected/border `#343a46`; primary text `#f3f4f6`, secondary text `#c1c7d0`. Light surfaces remain neutral with white panels and readable dark text.
- Retain the existing blue brand/action scale and semantic success/warning/danger colors. Button fills use action tokens; colored text and focus use the appropriate contrast-safe foreground token.
- Normal controls and panels are opaque, without gradients, floating hover motion, pulsing whole-card outlines or layered glass pills. Shadows are reserved for actual overlays.
- Existing 44px minimum targets and 48px primary/icon targets, readable mobile fields, keyboard focus, reduced motion and 320px reflow remain requirements.
- Page headings follow one shared pattern. Browse pages share toolbar density and neutral borders. Information is grouped with spacing and dividers instead of repeated nested cards.
- Primary navigation uses one-line labels, quiet active treatment and a visible current-page indication. Collapsed navigation stays keyboard accessible.
- Channel cards are left aligned and compact; recordings keep media-focused 16:9 artwork. Live/recording status remains explicit in text/badges.
- Settings keep the existing section structure and URL behavior, with a restrained secondary navigation and visible contextual heading on mobile.

## Preservation boundaries

Keep Vue 3, TypeScript, Vite, Pinia, Vue Router, SCSS, VitePWA and hls.js. Keep the channel-first starting route and `/overview`, activity, library, channel management and all existing settings destinations. Preserve APIs, auth, realtime, recording, playback, PWA and saved state. No backend changes, runtime dependency updates, workflow/gate relaxation, feature removal, merge, release or deployment.

## Verification

Compare the existing candidate before changes, then run the frontend unit suite, type checks, token/foundation checks and a production build. Use real browser rendering with the project's synthetic fixtures for both themes, desktop and narrow mobile. Inspect channel grid/list, library filters and selection, settings, detail and global utilities. Preserve focus, selection, URL state and destructive confirmations. Report synthetic/local evidence separately from live-provider or production acceptance.
