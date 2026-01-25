# ADR-001: Circuit Breaker for Twitch API Integration

**Status:** Proposed  
**Date:** 2026-01-06  
**Decision Makers:** StreamVault Core Team

## Context

StreamVault relies heavily on the Twitch API for:
- EventSub webhooks (stream online/offline notifications)
- User authentication (OAuth flow)
- Stream metadata retrieval
- Username validation

Currently, there is no protection against Twitch API outages or rate limiting. When Twitch is unavailable, StreamVault continues making requests, which can:
1. Exhaust rate limits faster
2. Create cascade failures
3. Fill logs with error messages
4. Block recording recovery attempts

### Current Implementation

```python
# app/events/handler_registry.py
async def get_access_token(self) -> str:
    if not self._access_token:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://id.twitch.tv/oauth2/token", ...):
                # No circuit breaker, retries indefinitely
```

## Decision Drivers

- **Reliability**: System should degrade gracefully when Twitch is unavailable
- **Performance**: Avoid unnecessary API calls during outages
- **User Experience**: Provide clear feedback when external services are down
- **Operations**: Reduce noise in logs during API issues

## Considered Options

### Option 1: Custom Circuit Breaker Implementation

**Pros:**
- Full control over behavior
- No additional dependencies
- Tailored to Twitch API specifics

**Cons:**
- More code to maintain
- May miss edge cases

### Option 2: Use `aiobreaker` Library

**Pros:**
- Battle-tested implementation
- Async-native
- Prometheus metrics built-in

**Cons:**
- Additional dependency
- May be overkill for single integration

### Option 3: Use `tenacity` with Custom Circuit Breaker

**Pros:**
- tenacity already used for retries
- Combines retry + circuit breaker logic
- Well-documented

**Cons:**
- Circuit breaker is secondary feature

## Decision

**Chosen Option: Option 1 - Custom Circuit Breaker Implementation**

### Rationale

1. StreamVault already has minimal dependencies - adding a library for one integration is excessive
2. Twitch API has specific behaviors (rate limit headers) we can optimize for
3. Custom implementation allows integration with existing WebSocket notifications

## Implementation Details

### Proposed Implementation

```python
# app/services/api/circuit_breaker.py
import asyncio
import time
from enum import Enum
from typing import Optional, Callable
import logging

logger = logging.getLogger("streamvault")

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    """
    Circuit Breaker for external API calls.
    
    States:
    - CLOSED: Normal operation, all calls pass through
    - OPEN: Service is failing, all calls fail fast
    - HALF_OPEN: Testing recovery, limited calls allowed
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_try_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"Circuit '{self.name}' entering half-open state")
                else:
                    raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(f"Circuit '{self.name}' half-open limit reached")
                self._half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    def _should_try_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        return time.time() - self._last_failure_time >= self.recovery_timeout
    
    async def _on_success(self):
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info(f"Circuit '{self.name}' recovered, now CLOSED")
            self._failure_count = 0
    
    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit '{self.name}' OPEN after {self._failure_count} failures"
                )
            elif self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit '{self.name}' reopened during recovery test")

class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass

# Global instance for Twitch API
twitch_api_circuit = CircuitBreaker(
    name="twitch_api",
    failure_threshold=5,
    recovery_timeout=60,
    half_open_max_calls=3
)
```

### Integration Points

1. **EventSub Handler** (`app/events/handler_registry.py`)
2. **Twitch API Service** (`app/services/api/twitch_api.py`)
3. **OAuth Flow** (`app/routes/twitch_auth.py`)

### Metrics to Expose

```python
# For future Prometheus integration
circuit_breaker_state{name="twitch_api"} 0|1|2  # closed|open|half_open
circuit_breaker_failures_total{name="twitch_api"} counter
circuit_breaker_trips_total{name="twitch_api"} counter
```

## Consequences

### Positive

- System continues working during Twitch outages (recordings still work)
- Faster failure feedback (no waiting for timeouts)
- Reduced log noise during outages
- Better rate limit management

### Negative

- Additional complexity in API layer
- Need to handle CircuitOpenError in all callers
- May delay recovery detection by `recovery_timeout` seconds

### Neutral

- Requires testing with simulated outages
- Dashboard/UI could show circuit state (future enhancement)

## Related ADRs

- (Future) ADR-002: Prometheus Metrics Implementation
- (Future) ADR-003: Dead Letter Queue for Failed Tasks

## References

- [Circuit Breaker Pattern - Martin Fowler](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Twitch API Rate Limits](https://dev.twitch.tv/docs/api/guide#twitch-rate-limits)
