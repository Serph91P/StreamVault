# Quick Reference - Remaining Frontend Tasks
**Last Updated:** 11. November 2025 (After Session 3 Verification)

---

## ✅ Progress Overview

**Total Tasks:** 59  
**Completed:** 16 (27%)  
**Remaining:** 43 (73%)

---

## 🔴 HIGH PRIORITY (Actually Need Work)

### 1. Settings Tables Mobile Responsive ⚠️
**Effort:** 6-8 hours | **Impact:** High | **Difficulty:** Medium

**Problem:** Tables in Notification & Recording settings don't work on mobile

**Files:**
- `app/frontend/src/components/settings/NotificationSettingsPanel.vue`
- `app/frontend/src/components/settings/RecordingSettingsPanel.vue`

**Solution:** Transform tables to cards on mobile (< 768px)

---

## 🟡 MEDIUM PRIORITY (Quick Wins)

### 2. Last Stream Info for Offline Streamers
**Effort:** 4-6 hours | **Impact:** High | **Difficulty:** Medium

**Backend:**
- Add fields to Streamer model: `last_stream_title`, `last_stream_category`, `last_stream_date`
- Create migration with backfill
- Update API response

**Frontend:**
- Show grayed-out last stream info in StreamerCard when offline
- Reduces whitespace, better visual consistency

**Files:**
- Backend: `app/models.py`, `app/routes/streamers.py`, `migrations/`
- Frontend: `app/frontend/src/components/cards/StreamerCard.vue`

### 3. Favorite Games - Light Mode & Spacing
**Effort:** 1-2 hours | **Impact:** Medium | **Difficulty:** Easy

**Tasks:**
- Fix search input background in light mode (use `var(--background-card)`)
- Add spacing between category image grid items

**File:** `app/frontend/src/components/settings/FavoritesSettingsPanel.vue`

### 4. Add Streamer Modal - Minor Polish
**Effort:** 2-3 hours | **Impact:** Low-Medium | **Difficulty:** Easy

**Optional Improvements:**
- Add icon to username input field
- Improve OR divider visual contrast
- Widen callback URL container on mobile

**Files:**
- `app/frontend/src/views/AddStreamerView.vue`
- `app/frontend/src/components/AddStreamerForm.vue`
- `app/frontend/src/components/TwitchImportForm.vue`

**Note:** Current implementation already quite good, these are polish items

---

## 🟢 LOW PRIORITY (Can Wait)

### 5. Settings View - 10+ Minor Issues
**Effort:** 12-20 hours | **Impact:** Medium | **Difficulty:** Various

**Issues:**
- Borders inconsistency
- Button alignment
- PWA panel styling
- Advanced tab (remove or keep?)
- About section links
- Network tab borders
- Streamer notification matrix redesign
- Per-streamer settings modal
- Animation toggle functionality
- Sidebar active state edge cases

**Recommendation:** Break into smaller tasks, tackle one at a time

---

## ⏸️ DEFERRED (Not Urgent)

### 6. Various Polish Items
- Grid/List toggle on mobile (minimal difference)
- Last subscription bottom border
- Jobs modal centering
- Notifications modal size
- Quick Stats icon sizes
- Recent Recordings background
- Video stat card width

---

## 📋 Recommended Order

### Day 1 (3-4 hours) - Quick Wins
1. Favorite Games Light Mode & Spacing (1-2h)
2. Add Streamer Modal Polish (1-2h)

### Day 2-3 (6-8 hours) - Mobile Critical
3. Settings Tables Mobile Responsive (6-8h)

### Day 4-5 (4-6 hours) - Feature Enhancement
4. Last Stream Info for Offline Streamers (4-6h)

### Day 6+ (Ongoing) - Polish
5. Settings View Minor Issues (break into smaller tasks)

---

## 🚀 Today's Recommendation

**Start with #3: Favorite Games - Light Mode & Spacing**

**Why:**
- Easiest task (1-2 hours)
- High visibility
- Low risk
- Builds momentum
- Perfect for getting back into the code

**Implementation:**
1. Open `FavoritesSettingsPanel.vue`
2. Find search input CSS
3. Replace hardcoded background with `var(--background-card)`
4. Add `gap` to category grid container
5. Test in light mode
6. Build & commit

---

## 🎯 Success Metrics

**Sprint Goal (Next 20 hours):**
- ✅ Complete Tasks #3, #4 (Quick wins - 3-5h)
- ✅ Complete Task #1 (Mobile responsive - 6-8h)
- ✅ Complete Task #2 (Last stream info - 4-6h)
- ⏳ Start Task #5 (Settings polish - ongoing)

**By end of sprint:**
- 20/59 tasks complete (34%)
- All high-priority tasks done
- Mobile experience excellent
- Card layouts optimized

---

**Let's do this! 🚀**
