# Streams Display Bug - StreamerDetailView

## Problem

StreamerDetailView shows "No Streams Yet" message despite database containing recorded streams.

**Example:**
- Streamer: CohhCarnage
- Database: 4 recorded streams exist
- UI: Shows empty state with "No Streams Yet"

## Expected Behavior

All recorded streams from the database should be displayed in the StreamerDetailView streams section.

## Affected Files

- `app/frontend/src/views/StreamerDetailView.vue` - `fetchStreams()` function
- `app/routes/streamers.py` - `/api/streamers/{streamer_id}/streams` endpoint

## Debug Steps

1. Check browser console for `fetchStreams()` logs
2. Verify API response from `/api/streamers/{id}/streams`
3. Check if streams have `recording_path` field populated
4. Verify SQL query in backend route
5. Check for filtering logic that might exclude streams

## Additional Context

- Statistics are correctly computed from streams array (Total Streams, Recorded, Avg Duration)
- This suggests the data exists but isn't being fetched/displayed properly
- Issue identified during Session 9 notification tracking implementation
- Session completed before 18:00 deadline (November 14, 2025)

## Acceptance Criteria

- [ ] All recorded streams display in StreamerDetailView
- [ ] Empty state only shows when truly no streams exist
- [ ] API returns correct stream count
- [ ] Frontend correctly renders fetched streams

## Priority

Medium - Feature works but data visibility issue affects user experience
