# Optimize N+1 Database Queries

## 🟢 Priority: MEDIUM
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 2-3 hours  
**Sprint:** Sprint 3: Polish & Enhancements  
**Impact:** HIGH - 50-70% performance improvement, critical for scalability

---

## 📝 Problem Description

### Current Performance Issue: N+1 Query Anti-Pattern

**Symptoms:**
- API endpoints respond slowly (200-500ms when should be < 100ms)
- Database connection pool shows high usage
- Logs show many sequential queries instead of single JOIN
- Performance degrades linearly with data growth

**Root Cause: Lazy Loading Relationships**

When fetching database records with relationships, SQLAlchemy by default uses **lazy loading**:
1. Execute 1 query to fetch main records (e.g., 30 streams)
2. For each record, execute additional query when accessing relationship (30 queries for streamer)
3. **Total: 1 + 30 = 31 queries** (should be 1 query with JOIN)

**Example Scenario:**
```
User opens Stream History page →
Backend fetches 30 streams →
Frontend displays each stream with streamer name →
Backend makes 30 additional queries (one per streamer lookup) →
Response time: 200-500ms (should be 50-100ms)
```

---

## 🔍 Affected Endpoints & Impact

### 1. Stream List Endpoint
**File:** `app/routes/streams.py`  
**Endpoint:** `GET /api/streams`

**Current Behavior:**
- Query 1: Fetch all streams (30 records)
- Queries 2-31: Fetch streamer for each stream (30 additional queries)
- **Total:** 31 queries
- **Response time:** 200-500ms

**Expected:**
- Single query with JOIN
- **Total:** 1 query
- **Response time:** 50-100ms

---

### 2. Streamer List Endpoint
**File:** `app/routes/streamers.py`  
**Endpoint:** `GET /api/streamers`

**Current Behavior:**
- Query 1: Fetch all streamers (15 records)
- Queries 2-16: Count streams for each streamer (`len(streamer.streams)`)
- **Total:** 16 queries
- **Response time:** 300-700ms

**Expected:**
- Single query with JOIN
- **Total:** 1 query  
**Response time:** 150ms

---

### 3. Streamer Detail Endpoint
**File:** `app/routes/streamers.py`  
**Endpoint:** `GET /api/streamers/{id}`

**Current Behavior:**
- Query 1: Fetch streamer by ID
- Query 2: Fetch all streams for streamer
- **Total:** 2 queries
- **Response time:** 100-200ms

**Expected:**
- Single query with eager loading
- **Total:** 1 query
- **Response time:** 50ms

---

### 4. WebSocket Status Updates
**File:** `app/routes/websocket.py`  
**Function:** Broadcasting recording status

**Current Behavior:**
- Query 1: Fetch active recordings (5 records)
- Queries 2-6: Fetch stream for each recording
- Queries 7-11: Fetch streamer for each stream
- **Total:** 11 queries (1 + 5 + 5)
- **Update frequency:** Every 5 seconds
- **Database load:** 132 queries/minute

**Expected:**
- Single query with nested eager loading
- **Total:** 1 query
- **Database load:** 12 queries/minute (91% reduction)

---

## 🎯 Solution Requirements

### Goal: Implement Eager Loading

Use SQLAlchemy's `joinedload()` to fetch relationships in single query with SQL JOIN.

**Key Concepts:**
1. **Eager Loading** - Load relationships immediately (not lazily)
2. **Joined Loading** - Use SQL JOIN to fetch related data in same query
3. **Nested Loading** - Load multi-level relationships (Recording → Stream → Streamer)

**Performance Target:**
- Stream list: < 100ms (from 200-500ms)
- Streamer list: < 150ms (from 300-700ms)
- WebSocket updates: < 50ms per query (from 100-200ms)
- Database query reduction: 50-70%

---

## 📋 Implementation Requirements

### 1. Identify All N+1 Query Locations

**Search Patterns:**
- Queries without eager loading: `.query(Model).all()` without `.options()`
- Relationship access in loops: `for item in items: item.relationship.field`
- Property access: `model.relationship_name`

**Files to Audit:**
- ✅ `app/routes/streams.py` - Stream endpoints
- ✅ `app/routes/streamers.py` - Streamer endpoints
- ✅ `app/routes/websocket.py` - WebSocket status
- ✅ `app/routes/recordings.py` - Recording management
- ✅ `app/services/recording/recording_service.py` - Recording service
- ✅ `app/services/cleanup/cleanup_service.py` - Cleanup operations

---

### 2. Update Stream List Endpoint

**Requirements:**
- Eager load `Stream.streamer` relationship
- Single query with JOIN
- Response data unchanged (transparent optimization)
- No breaking changes to API contract

**Expected Behavior:**
- Database logs show 1 query with JOIN
- Response time improves 50-70%
- Frontend receives same data structure

---

### 3. Update Streamer List Endpoint

**Requirements:**
- Eager load `Streamer.streams` relationship for VOD count
- Avoid loading full stream data (only count needed)
- Consider using `selectinload()` for large collections

**Expected Behavior:**
- VOD counts calculated without additional queries
- Response time < 150ms
- Memory usage reasonable (not loading unnecessary data)

---

### 4. Update WebSocket Status Queries

**Requirements:**
- Nested eager loading: `Recording → Stream → Streamer`
- Update every 5 seconds without query storm
- Reduce database load by 90%

**Expected Behavior:**
- Single query fetches all needed data
- WebSocket updates remain real-time
- Database connection pool usage decreases significantly

---

### 5. Update Streamer Detail Endpoint

**Requirements:**
- Eager load streamer's stream collection
- Load related recordings if accessed
- Optimize for detail page rendering

**Expected Behavior:**
- Single query loads streamer + all streams
- Detail page renders immediately
- No loading spinners or delays

---

## ✅ Acceptance Criteria

### Performance Metrics
- [ ] Stream list endpoint: < 100ms (currently 200-500ms)
- [ ] Streamer list endpoint: < 150ms (currently 300-700ms)
- [ ] Streamer detail endpoint: < 50ms (currently 100-200ms)
- [ ] WebSocket status query: < 50ms (currently 100-200ms)
- [ ] Database query count reduced 50-70%

### Code Quality
- [ ] All relationship access uses eager loading
- [ ] No lazy loading in API endpoints
- [ ] Nested relationships use chained `joinedload()`
- [ ] SQL logs show JOIN queries (not sequential SELECT)

### Verification Testing
- [ ] Enable SQLAlchemy query logging
- [ ] Count queries before optimization (baseline: 1 + N)
- [ ] Count queries after optimization (target: 1)
- [ ] Benchmark response times (before vs after)
- [ ] Verify API responses unchanged (same data structure)

### No Regressions
- [ ] All existing tests pass
- [ ] Frontend displays correct data
- [ ] WebSocket updates work correctly
- [ ] No missing data in responses
- [ ] No memory leaks from over-eager loading

---

## 🧪 Testing Requirements

### Query Count Verification

**Enable SQLAlchemy Logging:**
```python
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
```

**Expected Before Optimization:**
- Stream list (30 records): 31 queries logged
- Streamer list (15 records): 16 queries logged
- WebSocket update (5 recordings): 11 queries logged

**Expected After Optimization:**
- Stream list: 1 query with JOIN
- Streamer list: 1 query with JOIN
- WebSocket update: 1 query with nested JOIN

### Performance Benchmarking

**Tools:**
- `curl` with `time` command
- Apache Bench (`ab`) for load testing
- PostgreSQL query analyzer (`EXPLAIN ANALYZE`)

**Metrics to Collect:**
- Average response time (before/after)
- 95th percentile response time
- Database connection pool usage
- Queries per second

### Functional Testing
- [ ] Stream list displays correctly
- [ ] Streamer list shows accurate VOD counts
- [ ] WebSocket status updates in real-time
- [ ] Streamer detail page loads completely
- [ ] No missing relationships or null data
- [ ] Pagination works correctly
- [ ] Filtering works correctly

---

## 📖 References

**SQLAlchemy Documentation:**
- [Eager Loading](https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html)
- [Joined Eager Loading](https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html#joined-eager-loading)
- [Select IN Loading](https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html#select-in-loading)

**Project Documentation:**
- `docs/MASTER_TASK_LIST.md` - Task #8 (Optimize N+1 Queries)
- `.github/instructions/backend.instructions.md` - Database patterns
- `.github/ARCHITECTURE.md` - Database architecture section

**Related Issues:**
- Issue #6: Extract Magic Numbers (cleanup polling intervals)
- Issue #8: Security Audit (path traversal in queries)

---

## 📋 Implementation Tasks

### 1. Identify N+1 Queries (30 minutes)

**Search patterns:**

```bash
# Find queries without joinedload
grep -rn 'query(Stream)' app/routes/ app/services/ | grep -v 'joinedload'
grep -rn 'query(Streamer)' app/routes/ app/services/ | grep -v 'joinedload'

# Find relationship access without eager loading
grep -rn '\.streamer\.' app/routes/ app/services/
grep -rn '\.streams' app/routes/ app/services/
```

**Confirmed N+1 Issues:**

1. **Stream List** (`app/routes/streams.py`):
   ```python
   streams = session.query(Stream).filter(...).all()
   # Later: stream.streamer.username triggers N queries
   ```

2. **Streamer List** (`app/routes/streamers.py`):
   ```python
   streamers = session.query(Streamer).all()
   # Later: len(streamer.streams) triggers N queries
   ```

3. **WebSocket Status** (`app/routes/websocket.py`):
   ```python
   active_recordings = session.query(Recording).filter(...).all()
   # Later: recording.stream.streamer triggers N queries
   ```

---

### 2. Fix Stream List Endpoint (30 minutes)

**File:** `app/routes/streams.py`

**Before (N+1 query):**
```python
@router.get("/api/streams")
async def get_streams(
    streamer_id: Optional[int] = None,
    limit: int = 50,
    session: Session = Depends(get_db)
):
    query = session.query(Stream)
    
    if streamer_id:
        query = query.filter(Stream.streamer_id == streamer_id)
    
    streams = query.order_by(Stream.created_at.desc()).limit(limit).all()
    
    # N+1: Accessing stream.streamer.username triggers N queries
    return {
        "streams": [
            {
                "id": s.id,
                "title": s.title,
                "streamer_name": s.streamer.username,  # N queries!
                "category_name": s.category_name,
                # ...
            }
            for s in streams
        ]
    }
```

**After (Single query with JOIN):**
```python
from sqlalchemy.orm import joinedload

@router.get("/api/streams")
async def get_streams(
    streamer_id: Optional[int] = None,
    limit: int = 50,
    session: Session = Depends(get_db)
):
    query = session.query(Stream).options(
        joinedload(Stream.streamer)  # ✅ Eager load relationship
    )
    
    if streamer_id:
        query = query.filter(Stream.streamer_id == streamer_id)
    
    streams = query.order_by(Stream.created_at.desc()).limit(limit).all()
    
    # ✅ No additional queries - streamer already loaded
    return {
        "streams": [
            {
                "id": s.id,
                "title": s.title,
                "streamer_name": s.streamer.username,  # Already loaded!
                "category_name": s.category_name,
                # ...
            }
            for s in streams
        ]
    }
```

---

### 3. Fix Streamer List Endpoint (30 minutes)

**File:** `app/routes/streamers.py`

**Before (N+1 query):**
```python
@router.get("/api/streamers")
async def get_streamers(session: Session = Depends(get_db)):
    streamers = session.query(Streamer).all()
    
    # N+1: len(streamer.streams) triggers N queries
    return {
        "streamers": [
            {
                "id": s.id,
                "username": s.username,
                "vods_count": len(s.streams),  # N queries!
                # ...
            }
            for s in streamers
        ]
    }
```

**After (Single query with JOIN):**
```python
from sqlalchemy.orm import joinedload

@router.get("/api/streamers")
async def get_streamers(session: Session = Depends(get_db)):
    streamers = session.query(Streamer).options(
        joinedload(Streamer.streams)  # ✅ Eager load streams
    ).all()
    
    # ✅ No additional queries
    return {
        "streamers": [
            {
                "id": s.id,
                "username": s.username,
                "vods_count": len(s.streams),  # Already loaded!
                # ...
            }
            for s in streamers
        ]
    }
```

---

### 4. Fix WebSocket Status Queries (30 minutes)

**File:** `app/routes/websocket.py`

**Before:**
```python
active_recordings = session.query(Recording).filter(
    Recording.status == "recording"
).all()

for rec in active_recordings:
    # N+1: rec.stream.streamer triggers N queries
    data.append({
        "streamer": rec.stream.streamer.username,
        "title": rec.stream.title
    })
```

**After:**
```python
from sqlalchemy.orm import joinedload

active_recordings = session.query(Recording).options(
    joinedload(Recording.stream).joinedload(Stream.streamer)  # ✅ Nested eager load
).filter(
    Recording.status == "recording"
).all()

for rec in active_recordings:
    # ✅ Already loaded
    data.append({
        "streamer": rec.stream.streamer.username,
        "title": rec.stream.title
    })
```

---

### 5. Fix Streamer Detail Endpoint (30 minutes)

**File:** `app/routes/streamers.py`

**Before:**
```python
@router.get("/api/streamers/{id}")
async def get_streamer(id: int, session: Session = Depends(get_db)):
    streamer = session.query(Streamer).filter(Streamer.id == id).first()
    
    if not streamer:
        raise HTTPException(404)
    
    # N+1: streamer.streams triggers query
    return {
        "streamer": streamer.to_dict(),
        "streams": [s.to_dict() for s in streamer.streams]  # Query!
    }
```

**After:**
```python
from sqlalchemy.orm import joinedload

@router.get("/api/streamers/{id}")
async def get_streamer(id: int, session: Session = Depends(get_db)):
    streamer = session.query(Streamer).options(
        joinedload(Streamer.streams)  # ✅ Eager load
    ).filter(Streamer.id == id).first()
    
    if not streamer:
        raise HTTPException(404)
    
    # ✅ Already loaded
    return {
        "streamer": streamer.to_dict(),
        "streams": [s.to_dict() for s in streamer.streams]
    }
```

---

## 📂 Files to Modify

**Backend:**
- `app/routes/streams.py` (stream list endpoint)
- `app/routes/streamers.py` (streamer list + detail endpoints)
- `app/routes/websocket.py` (WebSocket status queries)
- `app/services/recording/recording_service.py` (if accessing relationships)
- `app/services/cleanup/cleanup_service.py` (if accessing relationships)

---

## ✅ Acceptance Criteria

**Performance:**
- [ ] Stream list endpoint: < 100ms (was 200-500ms)
- [ ] Streamer list endpoint: < 150ms (was 300-700ms)
- [ ] WebSocket status: < 50ms per poll (was 100-200ms)
- [ ] Database query count reduced 50-70%

**Code Quality:**
- [ ] All relationship access uses `joinedload()`
- [ ] Nested relationships use chained `joinedload()`
- [ ] No lazy loading in API endpoints
- [ ] Tests verify eager loading behavior

**Verification:**
```python
# Enable SQLAlchemy query logging
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Check query count in logs:
# Before: 31 queries (1 + 30)
# After: 1 query (with JOIN)
```

**No Regressions:**
- [ ] All tests pass
- [ ] API responses unchanged (same data)
- [ ] No missing data in frontend
- [ ] WebSocket updates work correctly

---

## 🧪 Testing Checklist

**Query Count Verification:**

```python
# tests/test_query_optimization.py
from sqlalchemy import event
from sqlalchemy.engine import Engine

@pytest.fixture
def query_counter():
    """Count queries executed during test"""
    queries = []
    
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
        queries.append(statement)
    
    yield queries
    
def test_stream_list_no_n_plus_one(client, query_counter):
    """Stream list should use single query with JOIN"""
    response = client.get("/api/streams")
    
    assert response.status_code == 200
    assert len(query_counter) == 1  # Single query with JOIN
    assert "JOIN" in query_counter[0].upper()

def test_streamer_list_no_n_plus_one(client, query_counter):
    """Streamer list should use single query"""
    response = client.get("/api/streamers")
    
    assert response.status_code == 200
    assert len(query_counter) == 1
```

**Performance Testing:**

```bash
# Benchmark before optimization
time curl http://localhost:8000/api/streams

# Benchmark after optimization
time curl http://localhost:8000/api/streams

# Should be 50-70% faster
```

**Functional Testing:**
- [ ] Stream list displays correctly
- [ ] Streamer list shows VOD counts
- [ ] WebSocket status updates work
- [ ] Streamer detail page loads
- [ ] No missing data in responses

---

## 📖 Documentation

**Primary:** `docs/MASTER_TASK_LIST.md` (Task #8)  
**Backend Guide:** `.github/instructions/backend.instructions.md`  
**Architecture:** `.github/ARCHITECTURE.md` (Database Patterns section)

**Update Backend Instructions:**

Add to `.github/instructions/backend.instructions.md`:

```markdown
## N+1 Query Prevention

**CRITICAL**: Always use eager loading when accessing relationships.

### Pattern:
```python
from sqlalchemy.orm import joinedload

# ✅ CORRECT: Eager load relationships
streams = session.query(Stream).options(
    joinedload(Stream.streamer)
).all()

# ❌ WRONG: Lazy loading triggers N queries
streams = session.query(Stream).all()
for s in streams:
    print(s.streamer.username)  # N queries!
```

### Nested Relationships:
```python
# Load Recording → Stream → Streamer
recordings = session.query(Recording).options(
    joinedload(Recording.stream).joinedload(Stream.streamer)
).all()
```
```

---

## 🤖 Copilot Instructions

**Context:**
Optimize database queries by eliminating N+1 query pattern. Current code makes 31 queries for 30 streams (1 + 30), causing 200-500ms API response times. Need to use eager loading with `joinedload()`.

**Critical Patterns:**
1. **Simple eager loading:**
   ```python
   from sqlalchemy.orm import joinedload
   
   streams = session.query(Stream).options(
       joinedload(Stream.streamer)
   ).all()
   ```

2. **Nested eager loading:**
   ```python
   recordings = session.query(Recording).options(
       joinedload(Recording.stream).joinedload(Stream.streamer)
   ).all()
   ```

3. **Multiple relationships:**
   ```python
   streamers = session.query(Streamer).options(
       joinedload(Streamer.streams),
       joinedload(Streamer.recordings)
   ).all()
   ```

**Identification:**
- Search for `.query(Model).all()` without `.options(joinedload())`
- Search for `model.relationship.field` access in loops
- Enable SQLAlchemy logging to count queries

**Files to Update:**
1. `app/routes/streams.py` - Stream list endpoint
2. `app/routes/streamers.py` - Streamer list + detail
3. `app/routes/websocket.py` - WebSocket status queries

**Testing Strategy:**
1. Enable SQLAlchemy query logging
2. Count queries before optimization (should be 1 + N)
3. Add `joinedload()` to queries
4. Count queries after (should be 1)
5. Verify response data unchanged
6. Benchmark performance improvement

**Files to Read First:**
- `.github/ARCHITECTURE.md` (Database Patterns)
- `.github/instructions/backend.instructions.md`
- `app/routes/streams.py`, `app/routes/streamers.py` (current implementation)

**Success Criteria:**
All API endpoints use eager loading, query count reduced from 1+N to 1, 50-70% performance improvement, no data changes, tests pass.

**Common Pitfalls:**
- ❌ Forgetting to import `joinedload` from `sqlalchemy.orm`
- ❌ Not testing query count (optimization not verified)
- ❌ Breaking existing functionality
- ❌ Missing nested relationships (Recording → Stream → Streamer)
- ❌ Not chaining `joinedload()` for nested relations
