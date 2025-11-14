# Last Stream Info for Offline Streamers

## 🟢 Priority: MEDIUM
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 4-6 hours  
**Sprint:** Sprint 2: Mobile UX  
**Impact:** MEDIUM - Improved UX, helps users decide whether to watch VODs

---

## 📝 Problem Description

### Current User Experience: No Context for Offline Streamers

**Issue:**
When a streamer is offline, their card shows minimal information:
- ✅ Username
- ✅ Profile image  
- ✅ VOD count
- ❌ **No context about what they stream**
- ❌ **No last stream information**

**User Friction:**
1. User sees offline streamer card
2. Can't remember what content this streamer creates
3. No info about last stream (title, game, when)
4. Must click into VOD list to get context
5. Extra navigation steps to make viewing decision

**Example Current Card (Offline Streamer):**
```
┌────────────────────┐
│  [Profile Image]   │
│  johndoe123        │
│  🔴 OFFLINE        │
│  5 VODs            │  ← What do they stream? 🤷
└────────────────────┘
```

**Comparison: Live Streamer Card (Works Well):**
```
┌────────────────────┐
│  [Profile Image]   │
│  johndoe123        │
│  🟢 LIVE           │
│                    │
│  "Speedrun WR      │  ← Shows current title
│   Attempt"         │
│  Playing: Celeste  │  ← Shows current game
│  1,234 viewers     │
│                    │
│  5 VODs            │
└────────────────────┘
```

**Desired: Offline Streamer Card (With Context):**
```
┌────────────────────┐
│  [Profile Image]   │
│  johndoe123        │
│  🔴 OFFLINE        │
│                    │
│  Last Stream:      │
│  "Speedrun WR      │  ← What they last streamed
│   Attempt"         │
│  Playing: Celeste  │  ← What game
│  2 days ago        │  ← When
│                    │
│  5 VODs            │
└────────────────────┘
```

---

## 🎯 Solution Requirements

### Goal: Persist & Display Last Stream Metadata

**Backend Requirements:**
1. **Store last stream information** when stream ends
2. **Persist data** in `streamers` table (new columns)
3. **Update API response** to include last stream info for offline streamers
4. **Only send when offline** (don't send for live streamers - they have current info)

**Frontend Requirements:**
1. **Display last stream info** when `is_live = false`
2. **Show relative time** ("2 days ago", "3 hours ago")
3. **Graceful fallback** if streamer has no stream history
4. **Consistent styling** with live stream info cards
5. **Truncate long titles** to prevent overflow

---

## 📋 Database Schema Requirements

### New Columns Needed in `streamers` Table

**Migration Required:** Create new migration or use existing Migration 023 (if exists)

**Columns to Add:**
- `last_stream_title` (VARCHAR, nullable) - Title of last stream
- `last_stream_category` (VARCHAR, nullable) - Game/category of last stream
- `last_stream_thumbnail` (VARCHAR, nullable) - Thumbnail URL (optional, for future use)
- `last_stream_date` (TIMESTAMP WITH TIMEZONE, nullable) - When stream ended

**Indexing:**
- No index needed (low-cardinality, infrequent queries)

**Nullability:**
- All columns nullable (streamers who never streamed have no data)

---

## 🔄 Data Flow Architecture

### Stream Lifecycle → Metadata Persistence

```
┌─────────────────────────────────────────────────────────────┐
│         Stream Goes Live (EventSub Notification)             │
│                                                              │
│  1. stream.online event received                            │
│  2. Streamer metadata updated (title, category, etc.)       │
│  3. Recording starts                                         │
│  4. is_live = TRUE                                           │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               │ Stream is live...
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│        Stream Goes Offline (EventSub Notification)           │
│                                                              │
│  1. stream.offline event received                           │
│  2. 🔑 CAPTURE current stream metadata BEFORE marking offline│
│  3. Store in last_stream_* columns:                         │
│     - last_stream_title = stream.title                      │
│     - last_stream_category = stream.category_name           │
│     - last_stream_date = NOW()                              │
│  4. is_live = FALSE                                          │
│  5. Recording stops                                          │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│         API Request: GET /api/streamers                      │
│                                                              │
│  IF streamer.is_live:                                        │
│    ✅ Return current stream info (title, category, viewers) │
│  ELSE:                                                       │
│    ✅ Return last stream info (last_stream_*, date)         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎨 Frontend Display Requirements

### Conditional Display Logic

**When Streamer is LIVE:**
- Show current stream title
- Show current category/game
- Show viewer count
- Show "LIVE" badge with red dot animation

**When Streamer is OFFLINE:**
- Show "Last Stream:" label
- Show last stream title
- Show last stream category
- Show relative time ("2 days ago")
- Show "OFFLINE" badge

**When Streamer Has NO History:**
- Show "No stream history" fallback message
- Or hide last stream section entirely

### Relative Time Formatting Examples

- Less than 1 hour: "45m ago"
- Less than 24 hours: "8h ago"
- Less than 7 days: "3d ago"
- Less than 30 days: "2w ago"
- More than 30 days: "3mo ago"

### Text Truncation

- Maximum title length: 50 characters
- Truncate with ellipsis: "Very Long Stream Title That Goes On An..."
- Category names: Full display (usually short)

---

## 📂 Files Requiring Changes

### Backend Files

**1. Database Migration:**
- Create new migration file OR verify `migrations/023_add_last_stream_info.py` exists
- Add 4 columns to `streamers` table

**2. Event Handler:**
- `app/services/events/eventsub_service.py`
- Update `handle_stream_offline()` function
- Capture current stream metadata before marking offline

**3. Recording Service:**
- `app/services/recording/recording_service.py`
- Update stream end logic to persist metadata
- Ensure metadata stored when recording stops

**4. API Endpoint:**
- `app/routes/streamers.py`
- Update `GET /api/streamers` response
- Include `last_stream_*` fields when `is_live = false`
- Exclude these fields when `is_live = true` (use current stream data)

**5. Database Models:**
- `app/models.py`
- Add `last_stream_title`, `last_stream_category`, `last_stream_thumbnail`, `last_stream_date` to `Streamer` model
- Ensure proper type hints (Optional[str], Optional[datetime])

### Frontend Files

**1. Type Definitions:**
- `app/frontend/src/types/api.ts`
- Update `Streamer` interface
- Add optional `last_stream_*` fields

**2. Streamer Card Component:**
- `app/frontend/src/components/StreamerCard.vue`
- Add conditional display for last stream info
- Implement relative time formatting utility
- Add "Last Stream:" label section
- Style last stream info section

**3. Utility Functions (Optional):**
- `app/frontend/src/utils/time.ts` (or inline in component)
- Create `formatRelativeTime(isoDate: string): string` function

---

## ✅ Acceptance Criteria

### Functional Requirements

**Backend:**
- [ ] Migration adds 4 columns to `streamers` table
- [ ] Last stream metadata captured when stream ends
- [ ] Last stream metadata captured on `stream.offline` EventSub event
- [ ] API returns `last_stream_*` fields only when `is_live = false`
- [ ] API excludes `last_stream_*` fields when `is_live = true`
- [ ] Timestamp stored in UTC timezone

**Frontend:**
- [ ] `Streamer` type includes optional `last_stream_*` fields
- [ ] Offline streamer cards display "Last Stream:" section
- [ ] Last stream title displays (truncated if > 50 chars)
- [ ] Last stream category displays
- [ ] Relative time displays ("2d ago")
- [ ] Fallback message shows if no stream history
- [ ] Live streamer cards show current stream info (no changes)

### Data Integrity
- [ ] Metadata persists across application restarts
- [ ] Metadata updates every time stream ends
- [ ] No metadata lost during recording failures
- [ ] Graceful handling of missing metadata (null values)

### User Experience
- [ ] Offline streamers provide content context
- [ ] Users can make informed decisions about watching VODs
- [ ] Information displayed is concise and readable
- [ ] Styling matches live stream info design
- [ ] No layout shifts when switching live/offline states

---

## 🧪 Testing Requirements

### Backend Testing

**Database Verification:**
```sql
-- Check migration applied
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'streamers' 
  AND column_name LIKE 'last_stream%';

-- Verify data populated
SELECT username, last_stream_title, last_stream_date 
FROM streamers 
WHERE is_live = FALSE 
LIMIT 5;
```

**API Testing:**
- [ ] GET `/api/streamers` returns `last_stream_*` for offline streamers
- [ ] GET `/api/streamers` does NOT return `last_stream_*` for live streamers
- [ ] Timestamp format is ISO 8601 (e.g., "2025-11-13T14:23:45Z")

### Frontend Testing

**Display Testing:**
- [ ] Open StreamersView with mix of online/offline streamers
- [ ] Offline streamers show "Last Stream:" section
- [ ] Live streamers show current stream info
- [ ] Relative time formatting accurate ("2d ago")
- [ ] Long titles truncate with ellipsis
- [ ] Fallback message shows for streamers with no history

**Edge Cases:**
- [ ] Streamer with no stream history → Fallback message
- [ ] Streamer with very old last stream (> 30 days) → Shows "Xmo ago"
- [ ] Stream title with special characters → Displays correctly
- [ ] Empty/null `last_stream_title` → Graceful handling
- [ ] Missing `last_stream_date` → No crash, shows fallback

### Integration Testing
- [ ] Simulate stream going offline
- [ ] Verify metadata stored in database
- [ ] Refresh frontend → Last stream info appears
- [ ] Simulate stream going live again
- [ ] Verify last stream info hidden, current stream shown

---

## 📖 References

**Project Documentation:**
- `docs/MASTER_TASK_LIST.md` - Task #6 (Last Stream Info for Offline Streamers)
- `.github/ARCHITECTURE.md` - EventSub event handling, metadata patterns

**Related Migrations:**
- Check if `migrations/023_add_last_stream_info.py` exists
- If not, create new migration with sequential number

**Related Components:**
- `app/frontend/src/components/StreamerCard.vue` - Card display component
- `app/frontend/src/views/StreamersView.vue` - Parent view

**Related Issues:**
- Issue #11: Streamer Cards Mobile Spacing (UI polish)
- Issue #2: Multi-Proxy System (EventSub reliability)

---

## 📋 Implementation Tasks

### 1. Backend: Update Metadata on Stream End (2-3 hours)

**Migration 023 (ALREADY EXISTS):**
```python
# migrations/023_add_last_stream_info.py
op.add_column('streamers', sa.Column('last_stream_title', sa.String(), nullable=True))
op.add_column('streamers', sa.Column('last_stream_category', sa.String(), nullable=True))
op.add_column('streamers', sa.Column('last_stream_thumbnail', sa.String(), nullable=True))
op.add_column('streamers', sa.Column('last_stream_date', sa.DateTime(timezone=True), nullable=True))
```

**Service Logic:**

**File:** `app/services/recording/recording_service.py`

```python
async def _on_stream_end(self, streamer: Streamer, stream: Stream):
    """Called when stream ends - persist metadata"""
    
    # Update last stream info
    streamer.last_stream_title = stream.title
    streamer.last_stream_category = stream.category_name
    streamer.last_stream_thumbnail = stream.thumbnail_url
    streamer.last_stream_date = datetime.now(timezone.utc)
    
    await db.commit()
    logger.info(f"Persisted last stream info for {streamer.username}")
```

**Update Event Handler:**

**File:** `app/services/events/eventsub_service.py`

```python
async def handle_stream_offline(self, event: dict):
    """Stream went offline - update last stream metadata"""
    
    username = event['broadcaster_user_login']
    streamer = await get_streamer_by_username(username)
    
    if streamer and streamer.is_live:
        # Get current stream data
        active_stream = await get_active_stream(streamer.id)
        
        if active_stream:
            # Store last stream info before marking offline
            streamer.last_stream_title = active_stream.title
            streamer.last_stream_category = active_stream.category_name
            streamer.last_stream_thumbnail = active_stream.thumbnail_url
            streamer.last_stream_date = datetime.now(timezone.utc)
        
        # Mark offline
        streamer.is_live = False
        await db.commit()
```

---

### 2. Backend: Update API Response (30 minutes)

**File:** `app/routes/streamers.py`

```python
@router.get("/api/streamers")
async def get_streamers(...):
    streamers_data = [{
        "id": s.id,
        "username": s.username,
        "display_name": s.username,
        "is_live": s.is_live,
        
        # Live info (existing)
        "title": s.title if s.is_live else None,
        "category_name": s.category_name if s.is_live else None,
        "viewer_count": s.viewer_count if s.is_live else None,
        
        # NEW: Last stream info (offline only)
        "last_stream_title": s.last_stream_title if not s.is_live else None,
        "last_stream_category": s.last_stream_category if not s.is_live else None,
        "last_stream_thumbnail": s.last_stream_thumbnail if not s.is_live else None,
        "last_stream_date": s.last_stream_date.isoformat() if s.last_stream_date and not s.is_live else None,
        
        "profile_image_url": s.profile_image_url,
        "vods_count": len(s.streams)
    } for s in streamers]
    
    return {"streamers": streamers_data}
```

---

### 3. Frontend: TypeScript Type Updates (15 minutes)

**File:** `app/frontend/src/types/api.ts`

```typescript
export interface Streamer {
  id: number
  username: string
  display_name: string
  is_live: boolean
  
  // Live stream info
  title?: string
  category_name?: string
  viewer_count?: number
  
  // NEW: Last stream info (offline only)
  last_stream_title?: string
  last_stream_category?: string
  last_stream_thumbnail?: string
  last_stream_date?: string  // ISO datetime
  
  profile_image_url?: string
  vods_count: number
}
```

---

### 4. Frontend: Display Last Stream Info (1-2 hours)

**File:** `app/frontend/src/components/StreamerCard.vue`

```vue
<template>
  <div class="streamer-card" :class="{ 'is-live': streamer.is_live }">
    <!-- Profile Image -->
    <img :src="streamer.profile_image_url" :alt="streamer.display_name" />
    
    <!-- Status Badge -->
    <div class="status-badge" :class="streamer.is_live ? 'live' : 'offline'">
      <span v-if="streamer.is_live" class="live-dot"></span>
      {{ streamer.is_live ? 'LIVE' : 'OFFLINE' }}
    </div>
    
    <!-- Display Name -->
    <h3>{{ streamer.display_name }}</h3>
    
    <!-- Live Stream Info -->
    <div v-if="streamer.is_live && streamer.title" class="stream-info">
      <p class="stream-title">{{ truncate(streamer.title, 50) }}</p>
      <p class="game-name">{{ streamer.category_name }}</p>
      <span class="viewers">{{ streamer.viewer_count }} viewers</span>
    </div>
    
    <!-- NEW: Last Stream Info (Offline) -->
    <div v-else-if="!streamer.is_live && streamer.last_stream_title" class="last-stream-info">
      <p class="last-stream-label">Last Stream:</p>
      <p class="stream-title">{{ truncate(streamer.last_stream_title, 50) }}</p>
      <p class="game-name">{{ streamer.last_stream_category }}</p>
      <p class="stream-date">{{ formatRelativeTime(streamer.last_stream_date) }}</p>
    </div>
    
    <!-- Fallback: No Stream Info -->
    <div v-else class="no-stream-info">
      <p>No stream history</p>
    </div>
    
    <!-- VOD Count -->
    <div class="vod-count">
      <span>{{ streamer.vods_count }} VODs</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Streamer } from '@/types/api'

defineProps<{
  streamer: Streamer
}>()

function truncate(text: string, maxLength: number): string {
  if (!text || text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

function formatRelativeTime(isoDate?: string): string {
  if (!isoDate) return ''
  
  const date = new Date(isoDate)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  
  const minutes = Math.floor(diffMs / 60000)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days < 7) return `${days}d ago`
  if (days < 30) return `${Math.floor(days / 7)}w ago`
  return `${Math.floor(days / 30)}mo ago`
}
</script>

<style scoped lang="scss">
.last-stream-info {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-tertiary);
  border-radius: var(--border-radius-sm);
  border-left: 3px solid var(--border-color);
  
  .last-stream-label {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 8px;
  }
  
  .stream-title {
    font-size: 14px;
    color: var(--text-primary);
    font-weight: 500;
    margin-bottom: 4px;
  }
  
  .game-name {
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 4px;
  }
  
  .stream-date {
    font-size: 12px;
    color: var(--text-tertiary);
    font-style: italic;
  }
}

.no-stream-info {
  margin-top: 12px;
  padding: 12px;
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
  font-style: italic;
}
</style>
```

---

## 📂 Files to Modify

**Backend:**
- `app/services/recording/recording_service.py` (update on stream end)
- `app/services/events/eventsub_service.py` (update on offline event)
- `app/routes/streamers.py` (add last_stream_* fields to response)

**Frontend:**
- `app/frontend/src/types/api.ts` (update Streamer interface)
- `app/frontend/src/components/StreamerCard.vue` (display last stream info)

**Migration:**
- `migrations/023_add_last_stream_info.py` (ALREADY EXISTS - verify and run if needed)

---

## ✅ Acceptance Criteria

**Backend:**
- [ ] Migration 023 applied (last_stream_* columns exist)
- [ ] Last stream info stored when stream ends
- [ ] Last stream info stored when offline event received
- [ ] API returns last_stream_* fields only when offline
- [ ] Last stream date is timezone-aware (UTC)

**Frontend:**
- [ ] Streamer type includes last_stream_* fields
- [ ] Last stream info displays when streamer offline
- [ ] Relative time formatting works ("2d ago")
- [ ] Text truncation prevents overflow
- [ ] Graceful fallback if no previous stream
- [ ] "Last Stream:" label clear and styled

**Data Integrity:**
- [ ] Last stream info persists across restarts
- [ ] Info updates every time stream ends
- [ ] Thumbnail URLs valid and accessible
- [ ] No info shown for streamers who never streamed

**UX:**
- [ ] Offline streamers have context (what they stream)
- [ ] Users can decide whether to watch VODs
- [ ] Info is concise and readable
- [ ] Styling consistent with live stream info

---

## 🧪 Testing Checklist

**Backend Testing:**
```bash
# Test stream offline event
curl -X POST http://localhost:8000/api/test/stream-offline/johndoe123

# Verify last stream info stored
psql streamvault -c "SELECT username, last_stream_title, last_stream_date FROM streamers;"

# Check API response
curl http://localhost:8000/api/streamers | jq '.streamers[] | select(.is_live == false)'
```

**Frontend Testing:**
- [ ] Streamer goes offline → Last stream info appears
- [ ] Info shows correct title, game, date
- [ ] Relative time formatting accurate
- [ ] Long titles truncate properly
- [ ] Thumbnail displays (if shown)
- [ ] "No stream history" fallback works

**Edge Cases:**
- [ ] Streamer with no previous streams → Fallback message
- [ ] Streamer with very old last stream → Shows correct date
- [ ] Title with special characters → Displays correctly
- [ ] Very long game name → Truncates or wraps
- [ ] Missing last_stream_date → Graceful handling

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md` (Task #6)  
**Related:** `migrations/023_add_last_stream_info.py` (Schema changes)  
**Architecture:** `.github/ARCHITECTURE.md` (Metadata handling)

---

## 🤖 Copilot Instructions

**Context:**
Add "Last Stream" info display for offline streamers to provide context about their content. Users currently see no info when streamers are offline, making it hard to decide whether to watch VODs.

**Critical Patterns:**
1. **Store metadata on stream end:**
   ```python
   streamer.last_stream_title = stream.title
   streamer.last_stream_date = datetime.now(timezone.utc)
   await db.commit()
   ```

2. **Conditional API response:**
   ```python
   "last_stream_title": s.last_stream_title if not s.is_live else None
   ```

3. **Relative time formatting:**
   ```typescript
   if (minutes < 60) return `${minutes}m ago`
   if (hours < 24) return `${hours}h ago`
   if (days < 7) return `${days}d ago`
   ```

4. **Graceful fallback:**
   ```vue
   <div v-if="!streamer.is_live && streamer.last_stream_title">
     <!-- Show last stream info -->
   </div>
   <div v-else-if="!streamer.is_live">
     <p>No stream history</p>
   </div>
   ```

**Migration Status:**
- Migration 023 ALREADY EXISTS - verify it's applied with `python migrations/manage.py status`
- If not applied: `python migrations/manage.py upgrade`

**Backend Updates:**
1. Update `recording_service.py` → Store on stream end
2. Update `eventsub_service.py` → Store on offline event
3. Update `streamers.py` → Add last_stream_* to API response

**Frontend Updates:**
1. Update `types/api.ts` → Add last_stream_* fields
2. Update `StreamerCard.vue` → Display info when offline
3. Add relative time formatting utility

**Testing Strategy:**
1. Simulate stream offline event
2. Verify last stream info stored in database
3. Check API response includes fields
4. Verify frontend displays correctly
5. Test edge cases (no history, old streams)

**Files to Read First:**
- `migrations/023_add_last_stream_info.py` (schema)
- `app/services/events/eventsub_service.py` (offline event handling)
- `app/components/StreamerCard.vue` (current display logic)

**Success Criteria:**
Offline streamers show "Last Stream" info (title, game, date), users have context for VOD browsing, graceful fallback if no history.

**Common Pitfalls:**
- ❌ Showing last stream info when streamer is live (should show current stream)
- ❌ Not using timezone-aware datetime (use `datetime.now(timezone.utc)`)
- ❌ Missing null checks (some streamers have no history)
- ❌ Forgetting to commit database changes
- ❌ Not testing API response format
