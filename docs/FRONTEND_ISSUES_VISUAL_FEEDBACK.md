# Frontend Issues - Visual Feedback Session
**Date:** 10. November 2025  
**Status:** 🔴 Needs Work  
**Session:** Complete app walkthrough on mobile + desktop

---

## 🎨 Design System Issues

### Critical: Light Mode Colors
**Status:** 🔴 HIGH PRIORITY

**Problem:** Hardcoded teal colors in sidebar break design system consistency

**Current Code (SidebarNav.vue):**
```scss
[data-theme="light"] & {
  background: #14b8a6;  // Hardcoded teal
  color: white;
}
```

**Solution:**
- Review COMPLETE_DESIGN_OVERHAUL_SUMMARY.md color palette
- Use CSS variables that adapt properly to light mode
- Ensure active states have sufficient contrast in BOTH modes
- Follow established design language

**Files:**
- `app/frontend/src/components/navigation/SidebarNav.vue`
- `app/frontend/src/styles/_variables.scss`

---

## 📱 Streamers View (Grid Cards)

### Issue 1: Streamer Name Truncation
**Status:** 🔴 CRITICAL

**Problem:** Long streamer names are unreadable (cut off)

**Screenshot Evidence:** User provided screenshot showing truncated names

**Current Layout:**
```
[Avatar 100px] [Name (truncated)] [Actions]
```

**Proposed Solutions:**
1. **Stack vertically** (preferred):
   ```
   [Avatar centered]
   [Name (full width, max 2 lines)]
   [Live info / stats]
   ```

2. **Move name below avatar**:
   ```
   [Avatar 100px] [Live info]
   [Name (full width, centered)]
   ```

**Decision:** User wants vertical stacking

**Files:**
- `app/frontend/src/components/cards/StreamerCard.vue`

---

### Issue 2: Show Last Stream Info When Offline
**Status:** 💡 FEATURE REQUEST

**Problem:** Cards look empty when streamers are offline

**Current Behavior:**
- Offline: Only shows "Offline - X VODs"
- Live: Shows title, category, viewers

**Proposed Behavior:**
- Offline: Show last stream title + category (grayed out)
- Live: Show current stream info (colored)

**Benefits:**
- Less whitespace
- More informative
- Consistent card heights

**Example:**
```vue
<div v-if="streamer.is_live" class="live-info">
  <h3 class="stream-title">{{ streamer.title }}</h3>
  <p class="category">{{ streamer.category_name }}</p>
  <span class="viewers live">{{ streamer.viewer_count }} viewers</span>
</div>
<div v-else class="offline-info">
  <h3 class="stream-title offline">{{ streamer.last_title || 'No recent streams' }}</h3>
  <p class="category offline">{{ streamer.last_category || 'Unknown' }}</p>
  <span class="status">Offline - {{ streamer.vods_count || 0 }} VODs</span>
</div>
```

**Backend Changes Needed:**
- Add `last_title` and `last_category` to streamer model
- Query latest stream for offline streamers

**Files:**
- `app/frontend/src/components/cards/StreamerCard.vue`
- `app/models.py` (Streamer model)
- `app/api/streamers.py` (endpoint)

---

### Issue 3: Excessive Whitespace
**Status:** 🟡 MEDIUM PRIORITY

**Problem:** 
- Too much whitespace on streamers page
- "Auto Sync" and "Add Streamer" buttons have space to the right
- Not responsive across breakpoints

**Current Layout:**
```
[Auto Sync toggle] [Add Streamer button]
                                     <- wasted space
```

**Proposed Solutions:**
1. **Flex layout with space-between**
2. **Move buttons to opposite sides**
3. **Add more controls to fill space** (sort, filter, etc.)

**Responsive Behavior:**
- Mobile (< 768px): Stack vertically
- Tablet (768px-1024px): Side by side
- Desktop (> 1024px): Utilize full width

**Files:**
- `app/frontend/src/views/StreamersView.vue`

---

### Issue 4: View Details Still Shows Empty Page
**Status:** 🔴 CRITICAL BUG

**Problem:** Clicking "View Details" in dropdown still leads to empty page

**User Quote:** "ich sehe aber auch nichts in den logs oder?"

**Logs Show:**
- No errors
- Navigation happens (router.push works)
- No API calls to `/api/streamers/{id}`

**Root Cause:** Likely issue in StreamerDetailView.vue not loading data

**Debug Steps:**
1. Check if route parameter is received
2. Check if API call is made
3. Check if data is populated
4. Check if template conditionals are hiding content

**Files:**
- `app/frontend/src/views/StreamerDetailView.vue`
- `app/frontend/src/components/cards/StreamerCard.vue` (dropdown navigation)

---

## 📱 Mobile Issues

### Issue 1: Header Logout Button Off-Screen
**Status:** 🔴 CRITICAL

**Problem:** Logout button disappears off right edge on mobile

**Current Header:**
```
[StreamVault] [+ JOBS 0] [Theme Toggle] [Logout] -> disappears
```

**Proposed Solution:** Hamburger menu for mobile
```
[☰] [StreamVault] [+ JOBS 0]

Hamburger opens:
- Theme Toggle
- Logout
- (other settings)
```

**Files:**
- `app/frontend/src/components/navigation/NavigationWrapper.vue`
- Create new `MobileMenu.vue` component

---

### Issue 2: Bottom Navigation Not Fixed
**Status:** 🔴 CRITICAL

**Problem:** Bottom nav requires scrolling to reach (not fixed to bottom)

**User Quote:** "das Menü ist ja dann unten als die navigaiton aber da mus sman erst hinscrollen die ist nicht immer unten am rand"

**Current Behavior:** Bottom nav is part of page flow

**Expected Behavior:** Fixed to bottom of viewport

**Fix:**
```scss
.bottom-nav {
  position: fixed;  // Not relative!
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 100;
}
```

**Files:**
- `app/frontend/src/components/navigation/BottomNav.vue`

---

### Issue 3: Jobs Badge Misaligned
**Status:** 🟡 MEDIUM PRIORITY

**Problem:** "+" icon before jobs count is offset/misaligned

**Screenshot Evidence:** User showed misalignment in header

**Files:**
- `app/frontend/src/components/navigation/NavigationWrapper.vue` (or header component)

---

### Issue 4: Jobs Modal Not Centered
**Status:** 🟡 MEDIUM PRIORITY

**Problem:** Jobs modal positioning looks off-center

**Expected:** Modal should be centered on screen (mobile + desktop)

**Files:**
- Component that renders jobs modal

---

### Issue 5: Notifications Modal Takes Full Screen
**Status:** 🟡 DESIGN QUESTION

**Problem:** Notifications modal takes entire screen (unlike jobs modal)

**User Quote:** "Das notifiaction modal nimmt einfach das ganze ein? sollte das nicht auch so wie das jobs modal sein?"

**Decision Needed:**
- Should notifications modal match jobs modal style?
- Or is full-screen intentional for mobile?

**Files:**
- Notifications modal component

---

### Issue 6: Grid/List Switch Minimal Difference on Mobile
**Status:** 💡 DESIGN DECISION

**Problem:** Grid vs List mode barely changes on mobile

**User Quote:** "Der grid und lsit switch macht auf mobile fast keinen unterscheid die elemtne bewegen sich nur ein bischen, ist eh die frage ob der auf mobiel überhaupt sinn macht"

**Proposed Solution:**
- Hide grid/list toggle on mobile (< 768px)
- Always use single-column layout on mobile
- Show toggle only on tablet/desktop

**Files:**
- `app/frontend/src/views/StreamersView.vue`

---

### Issue 7: Scroll Position Preserved Across Page Changes
**Status:** 🟡 UX ISSUE

**Problem:** Scroll position is remembered when navigating between pages

**User Quote:** "Was auch komisch ist das wenn man die seiten wechselt das sich das quasi den stand wo man gerade hingescrollt hatte merkt über die seiten hinweg sollte man dann nicht oben landen wenn man die seite wechselt?"

**Expected Behavior:** Always scroll to top when navigating to new page

**Solution:**
```typescript
// In router/index.ts
const router = createRouter({
  scrollBehavior(to, from, savedPosition) {
    return { top: 0 }  // Always scroll to top
  }
})
```

**Files:**
- `app/frontend/src/router/index.ts`

---

## 📄 Subscription Management View

### Issue 1: Button Visibility Issues (Dark Mode)
**Status:** 🔴 HIGH PRIORITY

**Problem:** 
- "Refresh", "Resubscribe All", "Delete All" buttons hard to see in dark mode
- "Refresh" button looks different from others

**Expected:** All buttons should have consistent, visible styling

**Files:**
- Subscription management view component

---

### Issue 2: Buttons Unreadable (Light Mode)
**Status:** 🔴 CRITICAL

**Problem:** "Resubscribe All" and "Delete All" have white text (invisible on light bg)

**User Quote:** "Im light mode kann man die gar nicht lesen, weil resubscribe all und delete all weißte schrift hat"

**Fix:** Use theme-aware text colors

**Files:**
- Subscription management view component

---

### Issue 3: Missing Bottom Border on Last Item
**Status:** 🟡 VISUAL BUG

**Problem:** Last subscription card missing bottom border (all others have it)

**User Quote:** "BNei der letzten subscription ist das untere ende des randes irgendwie weg? Alle darüber hjaben das"

**Fix:** Ensure consistent borders on all cards

**Files:**
- Subscription management view component

---

## ⚙️ Settings View

### Issue 1: Notifications - Inconsistent Borders
**Status:** 🟡 VISUAL BUG

**Problem:** Notification settings have inconsistent borders

**User Quote:** "bei der notifications sind die ränder unterscheidlich?"

**Files:**
- Settings view - Notifications tab

---

### Issue 2: Buttons Unreadable and Misaligned
**Status:** 🔴 HIGH PRIORITY

**Problem:** 
- Buttons not readable
- Buttons offset/misaligned from each other

**User Quote:** "Teilweisesind die buttons überhaupt nicht leesbar und versetzt zueinander"

**Files:**
- Settings view - Notifications tab

---

### Issue 3: Streamer Notification Settings Missing Design
**Status:** 🔴 CRITICAL

**Problem:** Per-streamer notification settings not using new design at all

**User Quote:** "Nei den streamern selber wo man die auswahl treffen kann für ddie einzelnen streamer fehlt das neue desing komplett?"

**Expected:** Should use GlassCard, proper spacing, theme colors

**Files:**
- Settings view - Streamer notifications section

---

### Issue 4: Recording Settings - Streamer-Specific Settings Broken
**Status:** 🔴 CRITICAL

**Problem:** Individual streamer recording settings are "total kaputt" (completely broken)

**User Quote:** "Recording setting siseht ersmal gut aus, die streamer spezifischen settings sind dann aber total kaputt. Das muss überarbeitet werden."

**Action Required:** Complete redesign of streamer-specific recording settings

**Files:**
- Settings view - Recording tab - Streamer settings

---

### Issue 5: Favorite Games - Search Black in Light Mode
**Status:** 🟡 VISUAL BUG

**Problem:** Search input is black background in light mode (hard to see)

**User Quote:** "Favorite Gmaes ist wieder Super nur die Suche ist schwarz im light mode"

**Fix:** Use theme-aware background colors

**Files:**
- Settings view - Favorite Games tab

---

### Issue 6: PWA Settings - Buttons Not Matching Design
**Status:** 🟡 DESIGN CONSISTENCY

**Problem:** PWA settings buttons don't match desired design language

**User Quote:** "PWa kann man nochmal drüver schauen und an die gewünschte desing sprache anpassen, denke ich? Die Buttons passen noch nicht alle."

**Files:**
- Settings view - PWA & Mobile tab

---

### Issue 7: Advanced Tab - Remove Entirely?
**Status:** 💡 DESIGN DECISION

**Problem:** 
- Debug mode only via ENV variable
- Cache clear function unclear

**User Quote:** "Advance kann glaube ich komplett raus, ich wüsste nicht was man da einstllen sollen könnte der debug moode ist bis jetzt nur über eine env aktivierbar. udn welchen cache cleared das denn?"

**Decision:** Remove Advanced tab or repurpose for admin-only settings

**Files:**
- Settings view - Advanced tab

---

### Issue 8: About Section - Missing Icon?
**Status:** 🟡 VISUAL INCOMPLETE

**Problem:** Area above "StreamVault" heading looks empty (icon missing?)

**User Quote:** "About ist auch gut denke ich auch wenn ich nicht weiß was über StreamVault sein sollte das sieht so aus als sollte da was sein, vielleicht fehtl wieder ein icon"

**Expected:** App icon/logo above "StreamVault" text

**Files:**
- Settings view - About tab

---

### Issue 9: GitHub Link Not Working
**Status:** 🟡 FUNCTIONALITY

**Problem:** "GitHub" button should link to repository

**User Quote:** "Das github sollte auf das github verlinken"

**Fix:** Add proper href to GitHub repo

**Files:**
- Settings view - About tab

---

### Issue 10: Documentation Link Placeholder
**Status:** 💡 FUTURE FEATURE

**Problem:** "Documentation" button exists but docs not ready

**User Quote:** "Documenatiaon ist im repo bis jetzt noch nicht schön gemacht :D"

**Action:** Either remove button or add "Coming Soon" state

**Files:**
- Settings view - About tab

---

## 🏠 Home View

### Issue 1: Background Behind "No Recordings Yet"
**Status:** 🟡 VISUAL UNCLEAR

**Problem:** User confused by background element behind empty state

**User Quote:** "Die home seite ich weiß nicht was der hintergrund hinter no recordings yet soll"

**Action:** Review design intent, possibly remove or clarify

**Files:**
- `app/frontend/src/views/HomeView.vue`

---

### Issue 2: Quick Stats Missing Icons
**Status:** 🟡 VISUAL INCOMPLETE

**Problem:** Quick stats cards missing icons/symbols

**User Quote:** "Nei den quick stats fehlen auch symbole warscheinlich"

**Expected:**
- Total Streamers: Users icon
- Live Now: Live/red dot icon  
- Recording: Video camera icon
- Recent Videos: Film reel icon

**Files:**
- `app/frontend/src/views/HomeView.vue`

---

## ➕ Add Streamer View

### Issue 1: Needs Design Update
**Status:** 🔴 HIGH PRIORITY

**Problem:** Add streamer view not using new design system

**User Quote:** "Add streamer muss auch noch angepasst werden an das neue design dneke ich"

**Expected:**
- GlassCard components
- Proper spacing
- Theme-aware colors

**Files:**
- Add streamer view component

---

### Issue 2: Import from Twitch Section "Grausig"
**Status:** 🔴 CRITICAL

**Problem:** Import from Twitch section looks terrible

**User Quote:** "Vor allen der import von twitch also der bereich sieht grausig aus"

**Action:** Complete redesign of Twitch import UI

**Files:**
- Add streamer view - Twitch import section

---

### Issue 3: Streamer Verification Layout Broken
**Status:** 🟡 VISUAL BUG

**Problem:** After checking streamer username, elements don't fit together properly

**User Quote:** "Dann wenn man einen streamer überprüft hat passen die sachen nicht ganz ineinader wie gesagt muss eh angepasst werden"

**Files:**
- Add streamer view - Verification result

---

## 🎯 Global Issues

### Issue 1: Missing Icons Everywhere
**Status:** 🔴 HIGH PRIORITY

**Problem:** Icons missing throughout the app

**User Quote:** "das ist soweiso noch ein punkt die fehlen überall noch"

**Action Required:**
- Audit all views and components
- Add appropriate icons from icon system
- Ensure consistency

**Files:**
- All view components
- Icon sprite system

---

## 📊 Summary

**Total Issues:** 35

**Priority Breakdown:**
- 🔴 CRITICAL: 12 issues
- 🟡 MEDIUM: 15 issues  
- 💡 DESIGN DECISIONS: 5 issues
- 🟢 VISUAL POLISH: 3 issues

**By Category:**
- Streamers View: 4 issues
- Mobile: 7 issues
- Subscriptions: 3 issues
- Settings: 10 issues
- Home: 2 issues
- Add Streamer: 3 issues
- Global: 1 issue
- Design System: 1 issue

---

## 🔄 Implementation Plan

### Phase 1: Critical Bugs (Day 1-2)
1. Fix View Details navigation (empty page)
2. Fix bottom nav (make it fixed position)
3. Fix light mode text visibility (buttons, search)
4. Fix streamer name truncation
5. Fix header logout button overflow

### Phase 2: Visual Consistency (Day 3-4)
6. Update design system colors (remove hardcoded values)
7. Add missing icons throughout app
8. Fix streamer-specific settings design
9. Redesign Add Streamer view
10. Fix subscription button visibility

### Phase 3: UX Improvements (Day 5-6)
11. Implement scroll-to-top on navigation
12. Add last stream info for offline streamers
13. Fix mobile hamburger menu
14. Center modals properly
15. Fix whitespace/responsive issues

### Phase 4: Polish & Decisions (Day 7)
16. Review and implement design decisions
17. Remove/repurpose Advanced tab
18. Add GitHub/Documentation links
19. Hide grid/list toggle on mobile
20. Final testing and bug fixes

---

## ✅ Next Steps

1. **Review this document** - Confirm all issues captured correctly
2. **Prioritize** - Agree on implementation order
3. **Start with Phase 1** - Fix critical bugs first
4. **Iterative testing** - Test each fix before moving to next
5. **Document changes** - Update FRONTEND_FIXES_APPLIED.md as we go

**Ready to start implementation?** 🚀
