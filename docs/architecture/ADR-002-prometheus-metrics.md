# ADR-002: Prometheus Metrics for Observability

**Status:** Proposed  
**Date:** 2026-01-06  
**Decision Makers:** StreamVault Core Team

## Context

StreamVault currently lacks runtime observability. Operators have no way to:
- Monitor active recording counts
- Track Twitch API health
- Measure background queue performance
- Get alerted on failures

The only monitoring is through logs, which requires log aggregation infrastructure and doesn't provide real-time dashboards.

### Current State

- Logs written to filesystem (`/app/logs/`)
- Health check endpoint (`/health`) only returns basic status
- No metrics endpoint
- No integration with monitoring systems

## Decision Drivers

- **Operational Excellence**: Need visibility into production system health
- **Alerting**: Enable alerts for recording failures, API issues
- **Debugging**: Faster root cause analysis
- **Self-Hosted Friendly**: Must work without external cloud services

## Considered Options

### Option 1: Prometheus + prometheus_client

**Pros:**
- Industry standard
- Self-hosted friendly
- Large ecosystem (Grafana, AlertManager)
- Python library is mature

**Cons:**
- Requires additional infrastructure (Prometheus server)

### Option 2: StatsD + Graphite

**Pros:**
- Simpler protocol
- Lower overhead

**Cons:**
- Less common today
- Fewer pre-built dashboards

### Option 3: OpenTelemetry Metrics

**Pros:**
- Future-proof (CNCF standard)
- Supports multiple backends

**Cons:**
- More complex setup
- Overkill for current scale

## Decision

**Chosen Option: Option 1 - Prometheus + prometheus_client**

### Rationale

1. Most StreamVault users will have Prometheus (via Docker/k8s monitoring)
2. Easy to integrate with existing Grafana dashboards
3. Python library is simple and battle-tested
4. Can be added without changing existing functionality

## Implementation Details

### Proposed Metrics

```python
# app/services/system/metrics_service.py
from prometheus_client import Counter, Gauge, Histogram, Info

# System Information
streamvault_info = Info(
    'streamvault',
    'StreamVault version and build information'
)

# Recording Metrics
active_recordings_gauge = Gauge(
    'streamvault_active_recordings_total',
    'Number of currently active recordings'
)

recording_duration_histogram = Histogram(
    'streamvault_recording_duration_seconds',
    'Duration of completed recordings',
    buckets=[300, 900, 1800, 3600, 7200, 14400, 28800]  # 5m to 8h
)

recording_failures_counter = Counter(
    'streamvault_recording_failures_total',
    'Total number of recording failures',
    ['reason']  # proxy_error, streamlink_crash, disk_full, etc.
)

# Twitch API Metrics
twitch_api_requests_counter = Counter(
    'streamvault_twitch_api_requests_total',
    'Total Twitch API requests',
    ['endpoint', 'status']  # success, error, rate_limited
)

twitch_api_latency_histogram = Histogram(
    'streamvault_twitch_api_latency_seconds',
    'Twitch API request latency',
    ['endpoint']
)

twitch_circuit_breaker_state = Gauge(
    'streamvault_twitch_circuit_breaker_state',
    'Twitch API circuit breaker state (0=closed, 1=open, 2=half_open)'
)

# Background Queue Metrics
queue_size_gauge = Gauge(
    'streamvault_background_queue_size',
    'Number of tasks in background queue',
    ['priority']  # high, normal, low
)

queue_processing_duration_histogram = Histogram(
    'streamvault_queue_task_duration_seconds',
    'Duration of background queue task processing',
    ['task_type']
)

queue_failures_counter = Counter(
    'streamvault_queue_task_failures_total',
    'Total background queue task failures',
    ['task_type', 'reason']
)

# Database Metrics
db_connection_pool_gauge = Gauge(
    'streamvault_db_pool_connections',
    'Database connection pool status',
    ['state']  # active, idle, overflow
)

# Streamer Metrics
monitored_streamers_gauge = Gauge(
    'streamvault_monitored_streamers_total',
    'Total number of monitored streamers'
)

live_streamers_gauge = Gauge(
    'streamvault_live_streamers_total',
    'Number of currently live streamers'
)
```

### API Endpoint

```python
# app/routes/metrics.py
from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

router = APIRouter()

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

### Integration Points

1. **Recording Service**: Update gauges on start/stop
2. **Twitch API**: Instrument all API calls
3. **Background Queue**: Track task metrics
4. **Database**: Export pool statistics
5. **Startup**: Set version info

### Grafana Dashboard

A pre-built Grafana dashboard JSON will be provided at:
`/docs/monitoring/grafana-dashboard.json`

Key panels:
- Active Recordings Over Time
- Recording Failure Rate
- Twitch API Health
- Queue Backlog Size
- P95 Recording Duration

## Consequences

### Positive

- Full visibility into production health
- Can create alerts for critical failures
- Historical data for debugging
- Standard `/metrics` endpoint

### Negative

- Small performance overhead (~1% CPU)
- Additional dependency (prometheus_client)
- Requires Prometheus infrastructure

### Neutral

- Users without Prometheus won't use this feature
- Metrics endpoint is unauthenticated (by convention)

## Security Considerations

The `/metrics` endpoint should be:
1. Listed in public paths (no auth required - Prometheus scraper needs access)
2. Optionally filterable by IP in reverse proxy
3. Not exposing sensitive data (no usernames, tokens, etc.)

## Migration

1. Add `prometheus_client` to requirements.txt
2. Create metrics service
3. Instrument existing services
4. Add `/metrics` route
5. Document Prometheus scrape config

## Example Prometheus Config

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'streamvault'
    static_configs:
      - targets: ['streamvault:7000']
    metrics_path: /metrics
    scrape_interval: 15s
```

## Related ADRs

- ADR-001: Circuit Breaker for Twitch API (provides circuit state metric)
- (Future) ADR-003: Alerting Rules Configuration

## References

- [Prometheus Python Client](https://github.com/prometheus/client_python)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [RED Method](https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/)
