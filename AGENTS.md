# AGENTS.md

## Project Overview

StreamVault is a self-hosted Twitch stream recorder with a FastAPI backend (Python 3.12+) and Vue 3 TypeScript frontend (PWA). It records live streams via Streamlink, generates metadata/thumbnails, and serves content through a responsive web UI.

**Stack:**
- Backend: FastAPI, SQLAlchemy, PostgreSQL, AsyncIO
- Frontend: Vue 3.5, TypeScript 5.6, Vite, SCSS, Pinia
- Infrastructure: Docker, GitHub Actions CI/CD
- Recording: Streamlink, FFmpeg

**Architecture:** REST API + WebSocket + Background Task Queue

## Setup Commands

### Backend (Python)

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Check migrations run correctly
python -m app.migrations_init

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Vue 3 + TypeScript)

```bash
cd app/frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production (MUST clean first to avoid ENOTEMPTY errors)
rm -rf dist/
npm run build
```

### Quick Start (Local Development)

```bash
# One-command local dev server (SQLite, auto-creates directories)
./dev.sh  # Linux/Mac
dev.bat   # Windows
```

### Docker (Production)

```bash
# Build frontend first, then Docker image
cd app/frontend && rm -rf dist/ && npm run build && cd ../..
docker build -f docker/Dockerfile -t streamvault:test .

# Run full stack
docker compose -f docker/docker-compose.yml up -d
docker compose logs -f app  # Check for startup errors
```

## Development Workflow

**Server URLs:**
- Backend API: `http://localhost:8000`
- Frontend Dev: `http://localhost:5173` (Vite proxy to backend)
- API Docs: `http://localhost:8000/docs`

**Hot Reload:**
- Backend: `--reload` flag watches `app/` directory
- Frontend: Vite HMR enabled by default

**Environment Variables:**
- Copy `.env.example` to `.env`
- Required: `DATABASE_URL`, `TWITCH_APP_ID`, `TWITCH_APP_SECRET`
- See `app/config/settings.py` for all options

## Testing Instructions

### Run All Tests

```bash
# Backend tests (~5s)
pytest tests/ -v

# All tests must pass before commit
pytest tests/ -v --tb=short
```

### Run Specific Test Files

```bash
# Security tests
pytest tests/test_security.py -v

# API route tests
pytest tests/test_api_routes.py -v

# N+1 query optimization tests
pytest tests/test_n_plus_one_optimization.py -v

# Application startup tests
pytest tests/test_application_startup.py -v
```

### Run Specific Test Pattern

```bash
# Run tests matching a name pattern
pytest tests/ -k "test_path_traversal" -v

# Run single test method
pytest tests/test_security.py::TestPathTraversalPrevention::test_path_traversal_with_relative_paths_blocked -v
```

### Frontend Validation

```bash
cd app/frontend

# Type checking
npm run type-check

# Linting
npm run lint

# Build (validates everything)
rm -rf dist/ && npm run build
```

## Code Style

### Python (Backend)

- **Type hints required** for all function parameters and return types
- **PEP 8** style guide compliance
- **Google-style docstrings** for public APIs
- **No bare `except:`** - use specific exception types
- **No magic numbers** - extract to `app/config/constants.py`
- **SQLAlchemy ORM only** - no raw SQL with string formatting
- **Parameterized queries** for any raw SQL: `text("... WHERE id = :id"), {"id": value}`

### TypeScript/Vue (Frontend)

- **Vue 3 Composition API** with `<script setup lang="ts">`
- **`credentials: 'include'`** on ALL fetch() calls (session cookies)
- **Global SCSS first** - check `docs/DESIGN_SYSTEM.md` before writing component styles
- **SCSS variables** - no hardcoded colors (`v.$primary` not `#3b82f6`)
- **Breakpoint mixins** - use `@include m.respond-below('md')` not raw `@media`

### Commit Messages

Use [Conventional Commits](https://conventionalcommits.org/) format:

```
<type>[scope]: <description>
```

**Types:**
- `feat:` / `feature:` - New features (minor bump)
- `fix:` - Bug fixes (patch bump)
- `refactor:` - Code restructuring (minor bump)
- `docs:` - Documentation only (patch bump)
- `chore:` - Dependencies, tooling (patch bump)
- `test:` - Test updates (patch bump)
- `perf:` - Performance improvements (minor bump)

**Examples:**
```bash
feat(api): add multi-proxy health checks
fix(videos): thumbnail endpoint graceful degradation (404 not 500)
refactor(frontend): eliminate hardcoded colors
chore(deps): update Python dependencies
```

## Build and Deployment

### CI Pipeline (GitHub Actions)

**Triggers:** Push to `main` or `develop` branches

**Pipeline Steps:**
1. Frontend build (cached if unchanged)
2. Docker build (multi-stage: Node → Python)
3. Security scan (Trivy, Safety, Bandit)
4. Auto-versioning (from commit message)
5. Push to DockerHub + GHCR

### Build Failures to Watch

| Issue | Solution |
|-------|----------|
| Frontend `ENOTEMPTY` error | Always `rm -rf dist/` before `npm run build` |
| Browserslist warning | Run `npx update-browserslist-db@latest` once |
| SCSS errors | Check variable namespacing (`v.$variable-name`) |
| Python import errors | Verify ALL imports exist |

### Production Build

```bash
# 1. Build frontend
cd app/frontend
rm -rf dist/
npm run build
cd ../..

# 2. Build Docker image
docker build -f docker/Dockerfile -t streamvault:latest .

# 3. Tag and push
docker tag streamvault:latest ghcr.io/username/streamvault:latest
docker push ghcr.io/username/streamvault:latest
```

## Pull Request Guidelines

**Title Format:** `<type>(scope): Brief description`

**Required Checks Before Submission:**
```bash
# Backend
pytest tests/ -v

# Frontend
cd app/frontend && rm -rf dist/ && npm run build
```

**PR Requirements:**
- All tests pass
- Frontend builds without errors
- Security checks pass (no new vulnerabilities)
- Conventional commit message format
- Update documentation if adding new features

## Security Requirements

**CRITICAL - These are mandatory for all code:**

### Path Traversal Prevention
```python
# ✅ ALWAYS validate user paths
from app.utils.security import validate_path_security
safe_path = validate_path_security(user_path, "read")

# ❌ NEVER use raw user input
open(user_path, 'r')  # Path traversal vulnerability
```

### SQL Injection Prevention
```python
# ✅ ALWAYS use SQLAlchemy ORM
db.query(Stream).filter(Stream.name == user_input).all()

# ✅ Parameterized queries for raw SQL
db.execute(text("SELECT * FROM streams WHERE name = :name"), {"name": user_input})

# ❌ NEVER string format user input
f"SELECT * FROM streams WHERE name = '{user_input}'"  # SQL injection
```

### Frontend Session Auth
```typescript
// ✅ ALWAYS include credentials for session cookies
await fetch('/api/endpoint', { credentials: 'include' })

// ❌ Missing credentials = 401 errors
await fetch('/api/endpoint')  // Session cookie not sent!
```

## Repository Structure

```
app/
├── main.py                      # FastAPI app entry point
├── models.py                    # SQLAlchemy ORM models
├── database.py                  # Database session management
├── routes/                      # API endpoint handlers
├── services/                    # Business logic (stateless)
│   └── recording/              # Recording engine
├── config/
│   ├── settings.py             # Environment variables (Pydantic)
│   └── constants.py            # Magic numbers → Named constants
└── frontend/
    ├── src/
    │   ├── components/         # Reusable Vue components
    │   ├── views/              # Page-level components
    │   ├── composables/        # Reusable logic (useAuth, useWebSocket)
    │   └── styles/             # SCSS design system
    └── package.json            # Dependencies (Vue 3.5, TypeScript 5.6)

migrations/                      # Database migrations (auto-run at startup)
docker/
├── Dockerfile                  # Multi-stage build
└── docker-compose.yml          # PostgreSQL + App stack
tests/                          # Pytest tests
```

## Path-Specific Instructions

Detailed code patterns are in `.github/instructions/`:

| File | Applies To |
|------|-----------|
| `frontend.instructions.md` | `app/frontend/**/*.vue`, `*.ts`, `*.scss` |
| `backend.instructions.md` | `app/**/*.py` |
| `api.instructions.md` | `app/routes/**/*.py` |
| `migrations.instructions.md` | `migrations/**/*.py` |
| `docker.instructions.md` | `docker/**`, `Dockerfile` |
| `security.instructions.md` | All files |

## Troubleshooting

### Common Issues

**Frontend won't build:**
```bash
rm -rf app/frontend/dist app/frontend/node_modules
cd app/frontend && npm install && npm run build
```

**Database migration errors:**
```bash
# Check migration status
python -m app.migrations_init

# Reset local SQLite (dev only)
rm streamvault_local.db
```

**Docker container won't start:**
```bash
# Check logs
docker compose logs -f app

# Rebuild from scratch
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

**401 Unauthorized errors in frontend:**
- Ensure ALL fetch() calls include `credentials: 'include'`
- Check browser dev console for missing cookies

### Debug Mode

```bash
# Backend with debug logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload

# Check application logs
tail -f logs/*.txt
```

## Additional Documentation

| Topic | Location |
|-------|----------|
| Architecture | `docs/ARCHITECTURE.md` |
| Design System | `docs/DESIGN_SYSTEM.md` |
| User Guide | `docs/USER_GUIDE.md` |
| API Reference | `/docs` endpoint (OpenAPI) |
| Browser Token Setup | `docs/BROWSER_TOKEN_SETUP.md` |
