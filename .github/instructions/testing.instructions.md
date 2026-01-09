---
applyTo: 'tests/**/*.py,**/*.test.ts,**/*.spec.ts'
description: 'Comprehensive testing guidelines for StreamVault'
---

# StreamVault Testing Guidelines

Testing is critical for StreamVault's reliability and security. These guidelines ensure comprehensive test coverage across all components.

## Testing Philosophy

### Quality Assurance Principles
- **Security first**: All security-critical functions must have 100% test coverage
- **Behavior-driven**: Test what the code does, not how it's implemented
- **Reliability**: Tests must be deterministic and fast
- **Maintainability**: Tests should be easy to understand and update
- **Real-world scenarios**: Test actual user workflows and edge cases

### Testing Pyramid
```
    E2E Tests (Few)
       /\
      /  \
  Integration Tests (Some)
     /\
    /  \
Unit Tests (Many)
```

## Backend Testing (Python/pytest)

### Test Structure and Organization
```python
# ✅ PROPER TEST ORGANIZATION
tests/
├── conftest.py              # Shared fixtures
├── test_api/
│   ├── test_auth.py        # Authentication endpoints
│   ├── test_recordings.py  # Recording endpoints
│   └── test_streamers.py   # Streamer endpoints
├── test_services/
│   ├── test_recording_service.py
│   └── test_notification_service.py
├── test_security/
│   ├── test_path_validation.py
│   ├── test_sql_injection.py
│   └── test_xss_prevention.py
└── test_performance/
    ├── test_n_plus_one.py
    └── test_memory_usage.py
```

### Test Fixtures and Setup
```python
# conftest.py - Shared test fixtures
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def test_db():
    """Create test database for the session"""
    engine = create_engine("sqlite:///test.db")
    TestingSessionLocal = sessionmaker(bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield TestingSessionLocal
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(test_db):
    """Create a fresh database session for each test"""
    session = test_db()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture
def authenticated_client(client, db_session):
    """Client with authenticated session"""
    # Create test user and authenticate
    user = create_test_user(db_session)
    client.post("/api/auth/login", json={
        "username": user.username,
        "password": "testpass123"
    })
    return client
```

### Security Testing Patterns
```python
# ✅ PATH TRAVERSAL TESTING
def test_path_traversal_prevention():
    """Test that path traversal attempts are blocked"""
    malicious_paths = [
        "../../../etc/passwd",
        "..\\..\\windows\\system32\\config",
        "/etc/passwd",
        "C:\\Windows\\System32\\config"
    ]
    
    for malicious_path in malicious_paths:
        with pytest.raises(SecurityError):
            validate_path_security(malicious_path, "read")

# ✅ SQL INJECTION TESTING
def test_sql_injection_prevention(client, db_session):
    """Test that SQL injection attempts fail safely"""
    injection_attempts = [
        "'; DROP TABLE users; --",
        "1' OR '1'='1",
        "admin'--",
        "1' UNION SELECT * FROM users--"
    ]
    
    for injection in injection_attempts:
        response = client.get(f"/api/streamers/{injection}")
        # Should return 400/404, not 500 (which indicates successful injection)
        assert response.status_code in [400, 404]
        # Should not contain database error messages
        assert "sql" not in response.text.lower()
        assert "database" not in response.text.lower()

# ✅ AUTHENTICATION BYPASS TESTING
def test_authentication_required(client):
    """Test that protected endpoints require authentication"""
    protected_endpoints = [
        ("/api/recordings", "POST"),
        ("/api/streamers", "POST"),
        ("/api/settings", "GET"),
        ("/api/users/profile", "GET")
    ]
    
    for endpoint, method in protected_endpoints:
        response = getattr(client, method.lower())(endpoint)
        assert response.status_code == 401
```

### API Endpoint Testing
```python
# ✅ COMPREHENSIVE API TESTING
class TestRecordingsAPI:
    
    def test_create_recording_success(self, authenticated_client, db_session):
        """Test successful recording creation"""
        streamer = create_test_streamer(db_session)
        
        payload = {
            "streamer_id": streamer.id,
            "quality": "720p60",
            "duration_limit": 3600
        }
        
        response = authenticated_client.post("/api/recordings", json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data["streamer_id"] == streamer.id
        assert data["status"] == "pending"
        assert "id" in data
    
    def test_create_recording_validation_errors(self, authenticated_client):
        """Test validation error handling"""
        invalid_payloads = [
            {},  # Missing required fields
            {"streamer_id": "invalid"},  # Invalid streamer ID
            {"streamer_id": "123", "quality": "invalid"},  # Invalid quality
            {"streamer_id": "123", "duration_limit": -1}  # Invalid duration
        ]
        
        for payload in invalid_payloads:
            response = authenticated_client.post("/api/recordings", json=payload)
            assert response.status_code == 400
            assert "error" in response.json()
    
    def test_get_recordings_pagination(self, authenticated_client, db_session):
        """Test recording list pagination"""
        # Create test recordings
        recordings = [create_test_recording(db_session) for _ in range(25)]
        
        # Test first page
        response = authenticated_client.get("/api/recordings?page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["page"] == 1
        
        # Test last page
        response = authenticated_client.get("/api/recordings?page=3&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5  # Remaining items
```

### Service Layer Testing
```python
# ✅ SERVICE TESTING WITH MOCKS
class TestRecordingService:
    
    @pytest.fixture
    def recording_service(self, db_session):
        return RecordingService(db_session)
    
    @pytest.mark.asyncio
    async def test_start_recording_success(self, recording_service, mocker):
        """Test successful recording start"""
        # Mock external dependencies
        mock_streamlink = mocker.patch('app.utils.streamlink_utils.start_recording')
        mock_notify = mocker.patch('app.services.notification_service.send_notification')
        
        mock_streamlink.return_value = {
            "process_id": "test_123",
            "output_path": "/recordings/test.mp4"
        }
        
        streamer = create_test_streamer()
        result = await recording_service.start_recording(
            streamer_id=streamer.id,
            quality="720p60"
        )
        
        # Verify service behavior
        assert result.status == "recording"
        assert result.process_id == "test_123"
        
        # Verify external calls
        mock_streamlink.assert_called_once()
        mock_notify.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_recording_streamlink_failure(self, recording_service, mocker):
        """Test handling of Streamlink failures"""
        mock_streamlink = mocker.patch('app.utils.streamlink_utils.start_recording')
        mock_streamlink.side_effect = StreamlinkError("Stream not found")
        
        streamer = create_test_streamer()
        
        with pytest.raises(RecordingError, match="Stream not found"):
            await recording_service.start_recording(
                streamer_id=streamer.id,
                quality="720p60"
            )
```

## Frontend Testing (Vue/TypeScript)

### Component Testing Setup
```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import path from 'path';

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts']
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  }
});

// src/test-setup.ts
import { config } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';

// Global test configuration
config.global.plugins = [createTestingPinia()];

// Mock fetch globally
global.fetch = vi.fn();

// Mock WebSocket
global.WebSocket = vi.fn();
```

### Vue Component Testing
```typescript
// ✅ COMPONENT BEHAVIOR TESTING
import { mount } from '@vue/test-utils';
import { describe, it, expect, vi } from 'vitest';
import RecordingCard from '@/components/RecordingCard.vue';

describe('RecordingCard', () => {
  const mockRecording = {
    id: '123',
    title: 'Test Stream',
    status: 'completed',
    thumbnail_url: '/thumbnails/test.jpg',
    duration: 3600,
    created_at: '2025-01-01T00:00:00Z'
  };
  
  it('renders recording information correctly', () => {
    const wrapper = mount(RecordingCard, {
      props: { recording: mockRecording }
    });
    
    expect(wrapper.find('[data-testid="recording-title"]').text())
      .toBe('Test Stream');
    expect(wrapper.find('[data-testid="recording-duration"]').text())
      .toBe('1h 0m');
    expect(wrapper.find('img').attributes('src'))
      .toBe('/thumbnails/test.jpg');
  });
  
  it('emits delete event when delete button clicked', async () => {
    const wrapper = mount(RecordingCard, {
      props: { recording: mockRecording }
    });
    
    await wrapper.find('[data-testid="delete-button"]').trigger('click');
    
    expect(wrapper.emitted('delete')).toBeTruthy();
    expect(wrapper.emitted('delete')?.[0]).toEqual([mockRecording.id]);
  });
  
  it('shows loading state during API operations', async () => {
    const wrapper = mount(RecordingCard, {
      props: { recording: { ...mockRecording, status: 'processing' } }
    });
    
    expect(wrapper.find('[data-testid="loading-spinner"]').exists())
      .toBe(true);
    expect(wrapper.find('[data-testid="delete-button"]').attributes('disabled'))
      .toBeDefined();
  });
});
```

### Composables Testing
```typescript
// ✅ COMPOSABLES TESTING
import { renderHook } from '@testing-library/vue';
import { useRecordings } from '@/composables/useRecordings';

describe('useRecordings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  
  it('fetches recordings on mount', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        items: [mockRecording],
        total: 1
      })
    } as Response);
    
    const { result } = renderHook(() => useRecordings());
    
    await vi.waitFor(() => {
      expect(result.current.recordings.value).toHaveLength(1);
    });
    
    expect(mockFetch).toHaveBeenCalledWith('/api/recordings', {
      credentials: 'include'
    });
  });
  
  it('handles API errors gracefully', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockRejectedValueOnce(new Error('Network error'));
    
    const { result } = renderHook(() => useRecordings());
    
    await vi.waitFor(() => {
      expect(result.current.error.value).toBe('Failed to load recordings');
    });
    
    expect(result.current.recordings.value).toHaveLength(0);
    expect(result.current.isLoading.value).toBe(false);
  });
});
```

### API Integration Testing
```typescript
// ✅ API INTEGRATION TESTING
import { setupServer } from 'msw/node';
import { rest } from 'msw';

const server = setupServer(
  rest.get('/api/recordings', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [mockRecording],
        total: 1
      })
    );
  }),
  
  rest.post('/api/recordings', (req, res, ctx) => {
    const { streamer_id } = req.body as any;
    if (!streamer_id) {
      return res(
        ctx.status(400),
        ctx.json({ error: 'streamer_id is required' })
      );
    }
    
    return res(
      ctx.status(201),
      ctx.json({ id: '123', streamer_id, status: 'pending' })
    );
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Recording API Integration', () => {
  it('creates recording with valid data', async () => {
    const response = await fetch('/api/recordings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        streamer_id: 'streamer123',
        quality: '720p60'
      })
    });
    
    expect(response.status).toBe(201);
    const data = await response.json();
    expect(data.id).toBeDefined();
    expect(data.status).toBe('pending');
  });
});
```

## Integration Testing

### Database Integration Tests
```python
# ✅ DATABASE INTEGRATION TESTING
class TestDatabaseIntegration:
    
    def test_recording_lifecycle(self, db_session):
        """Test complete recording lifecycle in database"""
        # Create streamer
        streamer = Streamer(
            name="TestStreamer",
            platform="twitch",
            username="test_user"
        )
        db_session.add(streamer)
        db_session.commit()
        
        # Create recording
        recording = Recording(
            streamer_id=streamer.id,
            title="Test Recording",
            status="pending"
        )
        db_session.add(recording)
        db_session.commit()
        
        # Update to recording
        recording.status = "recording"
        recording.process_id = "proc_123"
        db_session.commit()
        
        # Complete recording
        recording.status = "completed"
        recording.file_path = "/recordings/test.mp4"
        recording.duration = 3600
        db_session.commit()
        
        # Verify final state
        saved_recording = db_session.query(Recording).filter(
            Recording.id == recording.id
        ).first()
        
        assert saved_recording.status == "completed"
        assert saved_recording.duration == 3600
        assert saved_recording.streamer.name == "TestStreamer"
    
    def test_cascade_deletion(self, db_session):
        """Test that cascade deletion works correctly"""
        streamer = create_test_streamer(db_session)
        recording = create_test_recording(db_session, streamer_id=streamer.id)
        
        # Delete streamer should cascade to recordings
        db_session.delete(streamer)
        db_session.commit()
        
        # Recording should be deleted
        assert db_session.query(Recording).filter(
            Recording.id == recording.id
        ).first() is None
```

### End-to-End Testing
```python
# ✅ E2E TESTING WITH PLAYWRIGHT
from playwright.async_api import async_playwright

@pytest.mark.asyncio
async def test_recording_workflow():
    """Test complete user workflow for creating a recording"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        # Login
        await page.goto("http://localhost:5173/login")
        await page.fill("input[name='username']", "testuser")
        await page.fill("input[name='password']", "testpass")
        await page.click("button[type='submit']")
        
        # Navigate to recordings
        await page.wait_for_url("**/recordings")
        
        # Create new recording
        await page.click("button:text('New Recording')")
        await page.select_option("select[name='streamer']", "test_streamer")
        await page.select_option("select[name='quality']", "720p60")
        await page.click("button:text('Start Recording')")
        
        # Verify recording created
        await page.wait_for_selector(".recording-card:has-text('test_streamer')")
        recording_status = await page.text_content(".recording-status")
        assert recording_status == "Recording"
        
        await browser.close()
```

## Performance Testing

### Load Testing
```python
# ✅ PERFORMANCE BENCHMARKING
import pytest
import time

def test_api_response_time(client):
    """Test API response times are within acceptable limits"""
    endpoints = [
        "/api/recordings",
        "/api/streamers", 
        "/api/health"
    ]
    
    for endpoint in endpoints:
        start_time = time.time()
        response = client.get(endpoint)
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to ms
        
        assert response.status_code == 200
        assert response_time < 200, f"{endpoint} took {response_time}ms"

def test_concurrent_requests(client):
    """Test system handles concurrent requests properly"""
    import concurrent.futures
    import threading
    
    def make_request():
        return client.get("/api/recordings")
    
    # Simulate 20 concurrent users
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(make_request) for _ in range(100)]
        
        results = [future.result() for future in futures]
    
    # All requests should succeed
    assert all(r.status_code == 200 for r in results)
```

## Test Data Management

### Test Fixtures
```python
# ✅ REUSABLE TEST DATA
def create_test_streamer(db_session, **kwargs):
    """Create a test streamer with sensible defaults"""
    defaults = {
        "name": "TestStreamer",
        "platform": "twitch",
        "username": "test_user",
        "is_active": True
    }
    defaults.update(kwargs)
    
    streamer = Streamer(**defaults)
    db_session.add(streamer)
    db_session.commit()
    db_session.refresh(streamer)
    return streamer

def create_test_recording(db_session, **kwargs):
    """Create a test recording with sensible defaults"""
    if 'streamer_id' not in kwargs:
        streamer = create_test_streamer(db_session)
        kwargs['streamer_id'] = streamer.id
    
    defaults = {
        "title": "Test Recording",
        "status": "completed",
        "duration": 3600,
        "file_path": "/recordings/test.mp4"
    }
    defaults.update(kwargs)
    
    recording = Recording(**defaults)
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)
    return recording
```

## Test Coverage Requirements

### Minimum Coverage Targets
- **Security functions**: 100% coverage
- **API endpoints**: 95% coverage
- **Service layer**: 90% coverage
- **Utility functions**: 85% coverage
- **Frontend components**: 80% coverage

### Coverage Monitoring
```bash
# Generate coverage reports
pytest --cov=app --cov-report=html tests/
npm run test:coverage

# Enforce coverage in CI
pytest --cov=app --cov-fail-under=85 tests/
```

## Continuous Integration Testing

### CI Test Pipeline
```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: streamvault_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Run Backend Tests
        run: |
          pytest tests/ -v --cov=app --cov-report=xml
      
      - name: Run Frontend Tests  
        run: |
          cd app/frontend
          npm ci
          npm run test:coverage
      
      - name: Upload Coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml,./app/frontend/coverage/lcov.info
```

Remember: Good tests are an investment in code quality, reliability, and developer confidence. Write tests that document behavior, catch regressions, and enable safe refactoring.