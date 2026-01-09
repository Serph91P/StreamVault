<!-- Based on: https://github.com/github/awesome-copilot/blob/main/instructions/performance-optimization.instructions.md -->
---
applyTo: '**/*.py,**/*.ts,**/*.vue,**/*.scss'
description: 'Performance optimization guidelines for StreamVault'
---

# StreamVault Performance Optimization Guidelines

Performance is critical for StreamVault's real-time recording and streaming capabilities. These guidelines ensure optimal performance across all components.

## Core Performance Principles

### Backend Performance (Python/FastAPI)
- **Async by default**: Use async/await for all I/O operations
- **Database efficiency**: Prevent N+1 queries, use proper indexing
- **Memory management**: Avoid memory leaks in long-running processes
- **Resource pooling**: Reuse database connections and HTTP clients
- **Caching strategies**: Implement smart caching for frequently accessed data

### Frontend Performance (Vue/TypeScript)
- **Bundle optimization**: Lazy load components and routes
- **Reactive efficiency**: Minimize unnecessary re-renders
- **API optimization**: Batch requests, implement proper caching
- **Image optimization**: Compress and lazy load media content
- **Memory management**: Clean up event listeners and subscriptions

### Database Performance (PostgreSQL)
- **Query optimization**: Use EXPLAIN ANALYZE for slow queries
- **Index strategy**: Create indexes for frequently queried columns
- **Connection management**: Use connection pooling effectively
- **Transaction efficiency**: Keep transactions short and focused

## Backend Performance Guidelines

### Database Query Optimization
```python
# ❌ AVOID: N+1 Query Problem
async def get_streams_with_recordings():
    streams = await db.query(Stream).all()
    for stream in streams:
        recordings = await db.query(Recording).filter(
            Recording.stream_id == stream.id
        ).all()
        stream.recordings = recordings
    return streams

# ✅ OPTIMAL: Eager Loading
async def get_streams_with_recordings():
    return await db.query(Stream).options(
        selectinload(Stream.recordings)
    ).all()

# ✅ OPTIMAL: Custom Join Query for Complex Cases
async def get_active_streams_with_recent_recordings():
    return await db.execute(
        select(Stream, Recording)
        .join(Recording, Stream.id == Recording.stream_id)
        .where(Stream.is_active == True)
        .where(Recording.created_at > datetime.now() - timedelta(hours=24))
        .options(selectinload(Stream.recordings))
    ).all()
```

### Async Operation Best Practices
```python
# ✅ CONCURRENT API CALLS
async def update_multiple_streams(stream_ids: List[str]):
    tasks = []
    for stream_id in stream_ids:
        task = asyncio.create_task(update_single_stream(stream_id))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]

# ✅ EFFICIENT FILE OPERATIONS
async def process_large_file(file_path: Path):
    chunk_size = 64 * 1024  # 64KB chunks
    async with aiofiles.open(file_path, 'rb') as f:
        while chunk := await f.read(chunk_size):
            await process_chunk(chunk)
            # Allow other coroutines to run
            await asyncio.sleep(0)
```

### Caching Strategies
```python
# ✅ IN-MEMORY CACHING FOR FREQUENT QUERIES
from functools import lru_cache
from typing import Dict, Any

@lru_cache(maxsize=128)
async def get_cached_streamer_config(streamer_id: str) -> Dict[str, Any]:
    """Cache streamer configurations to avoid repeated DB queries."""
    return await db.query(StreamerConfig).filter(
        StreamerConfig.streamer_id == streamer_id
    ).first()

# ✅ REDIS CACHING FOR CROSS-PROCESS DATA
async def get_stream_status(stream_id: str) -> str:
    cache_key = f"stream_status:{stream_id}"
    
    # Try cache first
    if cached_status := await redis.get(cache_key):
        return cached_status.decode()
    
    # Fetch from database if not cached
    stream = await db.query(Stream).filter(Stream.id == stream_id).first()
    status = stream.status if stream else "unknown"
    
    # Cache for 30 seconds
    await redis.setex(cache_key, 30, status)
    return status
```

### Memory Management
```python
# ✅ PROPER RESOURCE CLEANUP
class RecordingProcessor:
    def __init__(self):
        self._active_processes = set()
        self._file_handles = []
    
    async def process_recording(self, recording_id: str):
        process = None
        file_handle = None
        try:
            # Track resources for cleanup
            process = await asyncio.create_subprocess_exec(...)
            self._active_processes.add(process)
            
            file_handle = await aiofiles.open(file_path, 'wb')
            self._file_handles.append(file_handle)
            
            # Process recording...
            
        finally:
            # Always cleanup resources
            if process:
                process.terminate()
                self._active_processes.discard(process)
            
            if file_handle:
                await file_handle.close()
                self._file_handles.remove(file_handle)
```

## Frontend Performance Guidelines

### Component Optimization
```typescript
// ✅ LAZY LOADING FOR ROUTES
const routes = [
  {
    path: '/recordings',
    component: () => import('@/views/RecordingsView.vue')
  },
  {
    path: '/streamers',
    component: () => import('@/views/StreamersView.vue')
  }
];

// ✅ EFFICIENT COMPONENT COMPOSITION
<template>
  <div class="recording-list">
    <!-- Use v-memo for expensive renders -->
    <RecordingItem
      v-for="recording in recordings"
      :key="recording.id"
      v-memo="[recording.id, recording.status, recording.thumbnail_url]"
      :recording="recording"
    />
  </div>
</template>

<script setup lang="ts">
// ✅ OPTIMIZE COMPUTED PROPERTIES
const filteredRecordings = computed(() => {
  // Use shallowRef for large arrays to avoid deep reactivity
  return recordings.value.filter(r => 
    r.status === 'completed' && 
    r.title.toLowerCase().includes(searchTerm.value.toLowerCase())
  );
});

// ✅ DEBOUNCE EXPENSIVE OPERATIONS
const debouncedSearch = useDebounceFn((term: string) => {
  searchTerm.value = term;
}, 300);
</script>
```

### API Call Optimization
```typescript
// ✅ BATCH API CALLS
const useBatchedRecordings = () => {
  const recordings = ref<Recording[]>([]);
  const isLoading = ref(false);
  
  const fetchRecordings = async (recordingIds: string[]) => {
    isLoading.value = true;
    try {
      // Single request for multiple recordings
      const response = await fetch('/api/recordings/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ ids: recordingIds })
      });
      
      recordings.value = await response.json();
    } finally {
      isLoading.value = false;
    }
  };
  
  return { recordings, isLoading, fetchRecordings };
};

// ✅ INTELLIGENT CACHING
const apiCache = new Map<string, { data: any; timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

const cachedFetch = async (url: string) => {
  const cached = apiCache.get(url);
  const now = Date.now();
  
  if (cached && (now - cached.timestamp) < CACHE_TTL) {
    return cached.data;
  }
  
  const response = await fetch(url, { credentials: 'include' });
  const data = await response.json();
  
  apiCache.set(url, { data, timestamp: now });
  return data;
};
```

### Bundle Size Optimization
```typescript
// ✅ TREE-SHAKE UNUSED IMPORTS
// Instead of importing entire libraries
import _ from 'lodash'; // ❌ Imports entire library

// Import only what you need
import { debounce, throttle } from 'lodash-es'; // ✅ Tree-shakeable

// ✅ DYNAMIC IMPORTS FOR LARGE DEPENDENCIES
const loadChartingLibrary = async () => {
  const { Chart } = await import('chart.js');
  return Chart;
};

// ✅ CODE SPLITTING FOR ROUTES
const router = createRouter({
  routes: [
    {
      path: '/analytics',
      component: () => import(/* webpackChunkName: "analytics" */ '@/views/Analytics.vue')
    }
  ]
});
```

## Database Performance Guidelines

### Index Strategy
```sql
-- ✅ COMPOSITE INDEXES FOR COMMON QUERIES
CREATE INDEX CONCURRENTLY idx_recordings_stream_status_date 
ON recordings (stream_id, status, created_at DESC);

-- ✅ PARTIAL INDEXES FOR FILTERED QUERIES
CREATE INDEX CONCURRENTLY idx_active_streams 
ON streams (created_at) WHERE is_active = true;

-- ✅ COVERING INDEXES FOR SELECT-ONLY QUERIES
CREATE INDEX CONCURRENTLY idx_stream_summary 
ON streams (id, name, status, created_at) WHERE is_active = true;
```

### Query Optimization
```sql
-- ✅ EFFICIENT PAGINATION
SELECT id, name, status, created_at 
FROM recordings 
WHERE created_at < $1  -- cursor-based pagination
ORDER BY created_at DESC 
LIMIT 20;

-- ✅ AGGREGATION WITH PROPER GROUPING
SELECT 
    s.name,
    COUNT(r.id) as recording_count,
    MAX(r.created_at) as last_recording
FROM streams s
LEFT JOIN recordings r ON s.id = r.stream_id
WHERE s.is_active = true
GROUP BY s.id, s.name
ORDER BY recording_count DESC;
```

### Connection Pool Optimization
```python
# ✅ OPTIMAL CONNECTION POOL SETTINGS
DATABASE_CONFIG = {
    "pool_size": 20,          # Base connections
    "max_overflow": 30,       # Additional connections under load
    "pool_timeout": 30,       # Seconds to wait for connection
    "pool_recycle": 3600,     # Recycle connections every hour
    "pool_pre_ping": True,    # Validate connections before use
}
```

## Performance Monitoring

### Backend Monitoring
```python
# ✅ PERFORMANCE METRICS
import time
import psutil
from functools import wraps

def monitor_performance(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        start_memory = psutil.virtual_memory().used
        
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            end_time = time.time()
            end_memory = psutil.virtual_memory().used
            
            duration = end_time - start_time
            memory_delta = end_memory - start_memory
            
            logger.info(
                f"Function {func.__name__} took {duration:.2f}s, "
                f"memory delta: {memory_delta / 1024 / 1024:.1f}MB"
            )
    
    return wrapper

# ✅ DATABASE QUERY MONITORING
async def log_slow_queries():
    """Log queries taking longer than 100ms"""
    slow_queries = await db.execute(
        text("""
        SELECT query, calls, total_time, mean_time
        FROM pg_stat_statements 
        WHERE mean_time > 100
        ORDER BY total_time DESC
        LIMIT 10
        """)
    )
    
    for query in slow_queries:
        logger.warning(f"Slow query: {query.mean_time:.2f}ms - {query.query[:100]}...")
```

### Frontend Performance Monitoring
```typescript
// ✅ PERFORMANCE API USAGE
const measurePageLoad = () => {
  const observer = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (entry.entryType === 'navigation') {
        const nav = entry as PerformanceNavigationTiming;
        console.log(`Page load time: ${nav.loadEventEnd - nav.fetchStart}ms`);
      }
    }
  });
  
  observer.observe({ entryTypes: ['navigation'] });
};

// ✅ API RESPONSE TIME TRACKING
const trackApiPerformance = async (url: string, options: RequestInit) => {
  const start = performance.now();
  
  try {
    const response = await fetch(url, options);
    const end = performance.now();
    
    // Log slow API calls
    if (end - start > 1000) {
      console.warn(`Slow API call: ${url} took ${end - start}ms`);
    }
    
    return response;
  } catch (error) {
    const end = performance.now();
    console.error(`Failed API call: ${url} failed after ${end - start}ms`);
    throw error;
  }
};
```

## Performance Testing

### Load Testing
```python
# ✅ CONCURRENT USER SIMULATION
import asyncio
import aiohttp
import time

async def simulate_user_session(session: aiohttp.ClientSession):
    """Simulate a typical user session"""
    # Login
    await session.post('/api/auth/login', json={...})
    
    # Browse recordings
    await session.get('/api/recordings')
    
    # Start recording
    await session.post('/api/recordings', json={...})
    
    # Check status
    for _ in range(10):
        await session.get('/api/recordings/status')
        await asyncio.sleep(1)

async def load_test(concurrent_users: int = 50):
    async with aiohttp.ClientSession() as session:
        tasks = [
            simulate_user_session(session) 
            for _ in range(concurrent_users)
        ]
        
        start_time = time.time()
        await asyncio.gather(*tasks)
        end_time = time.time()
        
        print(f"Load test completed: {concurrent_users} users in {end_time - start_time:.2f}s")
```

## Performance Budget

### Response Time Targets
- **API endpoints**: < 200ms for 95th percentile
- **Database queries**: < 100ms for complex queries
- **Page load time**: < 2 seconds for initial load
- **WebSocket messages**: < 50ms for real-time updates

### Resource Limits
- **Memory usage**: < 512MB for typical workload
- **CPU usage**: < 70% under normal load
- **Database connections**: < 80% of pool size
- **Bundle size**: < 2MB for initial JavaScript bundle

### Performance Regression Prevention
- Monitor key metrics in CI/CD pipeline
- Set up alerts for performance degradation
- Regular performance reviews and optimizations
- Load testing before major releases

Remember: Performance optimization is an ongoing process. Measure first, optimize second, and always validate that optimizations provide real benefits.