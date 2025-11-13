# Issue Execution Plan - Parallele Bearbeitung

**Letzte Aktualisierung:** 13. November 2025  
**Status:** ✅ Ready for Execution

---

## 🚀 Quick Start: Alle Issues parallel starten

### Phase 1: Parallele Ausführung (4 Issues gleichzeitig)

```bash
# Issue #9: Video Player Controls Mobile
gh issue create \
  --title "Video Player Controls Mobile Responsive" \
  --body-file docs/github_issues/09-video-player-controls-mobile.md \
  --label "type:frontend,priority:high,agent:mobile-specialist,sprint:mobile-ux"

# Issue #10A: Watch View - Video Layout
gh issue create \
  --title "Watch View - Video Layout Mobile Optimization" \
  --body-file docs/github_issues/10a-watch-view-video-layout-mobile.md \
  --label "type:frontend,priority:high,agent:mobile-specialist,sprint:mobile-ux,parallel-safe"

# Issue #10B: Watch View - Info Panel
gh issue create \
  --title "Watch View - Collapsible Info Panel Mobile" \
  --body-file docs/github_issues/10b-watch-view-info-panel-collapsible.md \
  --label "type:frontend,priority:high,agent:mobile-specialist,sprint:mobile-ux,parallel-safe"

# Issue #12: Chapters Panel Component
gh issue create \
  --title "Chapters Panel Mobile Responsive" \
  --body-file docs/github_issues/12-chapters-panel-mobile.md \
  --label "type:frontend,priority:medium,agent:mobile-specialist,sprint:mobile-ux,parallel-safe"
```

**Erwartete Completion Time:** 60-90 Minuten (bei paralleler Bearbeitung)

---

### Phase 2: Sequentielle Ausführung (wartet auf #12)

```bash
# Issue #10C: Watch View - Chapter Drawer (NUR NACH #12 ABSCHLUSS!)
gh issue create \
  --title "Watch View - Chapter Drawer Integration Mobile" \
  --body-file docs/github_issues/10c-watch-view-chapter-drawer-integration.md \
  --label "type:frontend,priority:high,agent:mobile-specialist,sprint:mobile-ux,depends-on:#12"
```

**Dependency Check vor Start:**
- ✅ Issue #12 merged?
- ✅ `ChapterPanel.vue` component existiert?
- ✅ Keine offenen Konflikte in `WatchView.vue`?

**Erwartete Completion Time:** 45-60 Minuten

---

### Phase 3: Verbleibende Mobile UX Issues

```bash
# Issue #11: Streamer Cards Spacing
gh issue create \
  --title "Streamer Cards Mobile Spacing & Touch Targets" \
  --body-file docs/github_issues/11-streamer-cards-mobile-spacing.md \
  --label "type:frontend,priority:medium,agent:mobile-specialist,sprint:mobile-ux,parallel-safe"

# Issue #13: Notifications Panel
gh issue create \
  --title "Notifications Panel Mobile Responsive" \
  --body-file docs/github_issues/13-notifications-panel-mobile.md \
  --label "type:frontend,priority:medium,agent:mobile-specialist,sprint:mobile-ux,parallel-safe"

# Issue #14: Add Streamer Modal
gh issue create \
  --title "Add Streamer Modal Polish & UX Improvements" \
  --body-file docs/github_issues/14-add-streamer-modal-polish.md \
  --label "type:frontend,priority:medium,agent:feature-builder,sprint:polish,parallel-safe"
```

**Erwartete Completion Time:** 90-120 Minuten (bei paralleler Bearbeitung)

---

## 📊 Execution Matrix

| Issue | File | Time | Dependencies | Parallel-Safe | Phase |
|-------|------|------|--------------|---------------|-------|
| #9 | `VideoPlayer.vue` | 30-45m | None | ✅ Yes | 1 |
| #10A | `WatchView.vue` (Video Section) | 30-45m | None | ✅ Yes | 1 |
| #10B | `WatchView.vue` (Info Section) | 30-45m | None | ✅ Yes | 1 |
| #12 | `ChapterPanel.vue` | 60-90m | None | ✅ Yes | 1 |
| #10C | `WatchView.vue` (Drawer) | 45-60m | ❌ **Needs #12** | ❌ No | 2 |
| #11 | `StreamerCard.vue` | 60-90m | None | ✅ Yes | 3 |
| #13 | `NotificationPanel.vue` | 60-90m | None | ✅ Yes | 3 |
| #14 | `AddStreamerModal.vue` | 90-120m | None | ✅ Yes | 3 |

---

## 🎯 Recommended Execution Strategy

### Option A: Maximum Parallelization (Schnellster Weg)

**Sprint 1 (Phase 1):** 4 Issues gleichzeitig
```
Day 1:
┌─────────┬─────────┬─────────┬─────────┐
│ #9      │ #10A    │ #10B    │ #12     │  ← Alle parallel starten
└─────────┴─────────┴─────────┴─────────┘
         60-90 Minuten (längste Task bestimmt Dauer)

Day 2:
┌─────────┐
│ #10C    │  ← Wartet auf #12, dann starten
└─────────┘
    45-60 Minuten
```

**Sprint 2 (Phase 3):** 3 Issues gleichzeitig
```
Day 3:
┌─────────┬─────────┬─────────┐
│ #11     │ #13     │ #14     │  ← Alle parallel starten
└─────────┴─────────┴─────────┘
      90-120 Minuten
```

**Total Time:** ~4-5 Stunden (über 3 Tage verteilt)

---

### Option B: Conservative (Sicherer, etwas langsamer)

**Sprint 1:**
```
Day 1: Issues #9, #10A (parallel) → 45-60 Minuten
Day 2: Issues #10B, #12 (parallel) → 60-90 Minuten
Day 3: Issue #10C (sequential) → 45-60 Minuten
```

**Sprint 2:**
```
Day 4: Issues #11, #13 (parallel) → 90 Minuten
Day 5: Issue #14 (solo) → 90-120 Minuten
```

**Total Time:** ~6-7 Stunden (über 5 Tage verteilt)

---

## ⚠️ Wichtige Hinweise

### Before Starting Any Issue

1. **Check Dependencies:**
   ```bash
   # Issue #10C braucht #12 completed
   gh issue view 12 --json state --jq '.state'
   # Muss "CLOSED" sein!
   ```

2. **Verify No Conflicts:**
   ```bash
   # Check if WatchView.vue has uncommitted changes
   git status app/frontend/src/views/WatchView.vue
   ```

3. **Assign to Correct Agent:**
   ```bash
   # Tag issue with agent label
   gh issue edit <issue-number> --add-label "agent:mobile-specialist"
   ```

### After Each Issue Completion

1. **Merge Immediately:**
   ```bash
   # Don't let PRs stack up
   gh pr merge <pr-number> --auto --squash
   ```

2. **Pull Latest:**
   ```bash
   git pull origin develop
   ```

3. **Update Status:**
   ```bash
   # Update MASTER_TASK_LIST.md with ✅
   ```

---

## 🔍 Monitoring Progress

### Check Issue Status
```bash
# List all open mobile UX issues
gh issue list --label "sprint:mobile-ux" --state open

# Check specific issue
gh issue view 9 --json state,assignees,labels
```

### Check PR Status
```bash
# List all open PRs
gh pr list --state open --label "copilot-generated"

# Check if PR is ready to merge
gh pr view <pr-number> --json mergeable,statusCheckRollup
```

### Track Completion
```bash
# Count completed issues
gh issue list --label "sprint:mobile-ux" --state closed | wc -l

# Total mobile UX issues
gh issue list --label "sprint:mobile-ux" | wc -l
```

---

## 📈 Expected Results

### Phase 1 (After 60-90 minutes)
- ✅ Video player full-width on mobile
- ✅ Video controls touch-friendly (48px+)
- ✅ Info panel collapsible on mobile
- ✅ ChapterPanel component created

### Phase 2 (After 45-60 minutes more)
- ✅ Chapter drawer functional (bottom/side)
- ✅ Swipe gestures working
- ✅ Complete mobile watch experience

### Phase 3 (After 90-120 minutes more)
- ✅ Streamer cards optimized for touch
- ✅ Notifications panel mobile-friendly
- ✅ Add Streamer modal polished

**Total Time:** 4-5 Stunden (bei maximaler Parallelisierung)

---

## 🎓 Lessons Learned

### ✅ Was funktioniert hat

**Issue Splitting:**
- Große Issues (3-4h) in kleine Sub-Tasks (30-60m) aufgeteilt
- File-Overlap vermieden (#10A/B/C arbeiten an verschiedenen Sections)
- Dependencies klar dokumentiert (#10C wartet auf #12)

**Parallel-Safe Labeling:**
- `parallel-safe` Label hilft bei Priorisierung
- Issues ohne Dependencies können alle gleichzeitig laufen
- Agent-Empfehlungen (`agent:mobile-specialist`) helfen

**Problem-Only Issues:**
- Issues beschreiben PROBLEM, nicht LÖSUNG
- Copilot kann eigene Implementierung wählen
- Acceptance Criteria klar definiert

### ⚠️ Zu beachten

**WatchView.vue Conflict Risk:**
- Issue #10C muss warten bis #12 fertig ist
- Beide würden sonst gleichzeitig `WatchView.vue` ändern
- Sequential execution bei Dependencies zwingend

**Testing After Each PR:**
- Jede Sub-Task isoliert testen
- Mobile Testing auf echten Geräten (Safari iOS!)
- Vor nächster Sub-Task bestätigen dass alles funktioniert

---

## 🤖 Copilot Commands

### Assign Issue to Agent
```bash
# In issue comments
@copilot with agent mobile-specialist: Start working on this issue

# Or mention in issue body
Agent Recommendation: mobile-specialist
```

### Request Progress Update
```bash
@copilot: What's the status of this issue? Any blockers?
```

### Request Testing
```bash
@copilot: Run tests for this PR and verify all acceptance criteria
```

---

## 📚 Related Documentation

- **MASTER_TASK_LIST.md** - Komplette Task-Liste (59 Tasks)
- **COPILOT_OPTIMIZATIONS.md** - Setup-Details, Best Practices
- **AGENTS.md** - Agent-Übersicht und Selection Guide
- **DESIGN_SYSTEM.md** - Frontend-Patterns, Touch-Target Standards

---

**Next Action:** Run Phase 1 parallel execution (4 issues) ⚡

*Erstellt: 13. November 2025*
