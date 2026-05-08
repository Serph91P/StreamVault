# StreamVault - Coding Agent Onboarding

## Project Summary

**StreamVault** is a self-hosted Twitch stream recorder with FastAPI backend (Python 3.12+) and Vue 3 TypeScript frontend (PWA). Records live streams via Streamlink, generates metadata/thumbnails, and serves content through a responsive web UI.

**Repository Size:** ~12K LOC (Backend: 8K Python, Frontend: 4K TypeScript/Vue)  
**Runtime:** Python 3.12+, Node.js 20+, PostgreSQL 15+, Docker  
**Architecture:** REST API + WebSocket + Background Task Queue

## Critical Build & Test Commands

**⚠️ ALWAYS run commands in this exact order to avoid build failures.**

### Backend (Python)

```bash
# Setup (one-time)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Validation (MUST pass before commit)
pytest tests/ -v                 # ~5s - All tests must pass
python -m app.migrations_init    # ~2s - Check migrations run

# Run locally (optional)
uvicorn app.main:app --reload --port 8000
```

### Frontend (Vue 3 + TypeScript)

```bash
cd app/frontend

# Setup (one-time)
npm install

# Build (MUST succeed before commit)
rm -rf dist/ || true                     # Clean first (prevents ENOTEMPTY errors)
npx update-browserslist-db@latest        # Fixes browserslist warning
npm run build                            # ~15-30s - MUST complete without errors

# Development (optional)
npm run dev
```

**🚨 Common Build Failures:**
- **Frontend `ENOTEMPTY` error**: Always `rm -rf dist/` before `npm run build`
- **Browserslist warning**: Run `npx update-browserslist-db@latest` once
- **SCSS errors**: Check variable namespacing (`v.$variable-name`)
- **Python import errors**: Verify ALL imports (e.g., `from starlette.websockets import WebSocketState`)

### Docker Build (Production)

```bash
# CRITICAL: Build frontend FIRST, then Docker image
cd app/frontend && npm run build && cd ../..
docker build -f docker/Dockerfile -t streamvault:test .

# Full stack test
docker compose -f docker/docker-compose.yml up -d
docker compose logs -f app  # Check for startup errors
```

## Repository Structure

**DO NOT search for these - they are always at these paths:**

```
app/
├── main.py                      # FastAPI app entry point
├── models.py                    # SQLAlchemy ORM models (centralized)
├── database.py                  # Database session management
├── routes/                      # API endpoint handlers
│   ├── videos.py               # Video streaming & thumbnail endpoints
│   ├── streamers.py            # Streamer CRUD operations
│   └── background_queue.py     # Task queue API
├── services/                    # Business logic (stateless)
│   ├── recording/              # Recording engine
│   │   ├── recording_service.py      # Main recording orchestration
│   │   ├── process_manager.py        # Streamlink process management
│   │   └── notification_manager.py   # Apprise notifications
│   ├── background_queue_service.py   # AsyncIO task queue
│   └── metadata_service.py           # NFO/chapter generation
├── config/
│   ├── settings.py             # Environment variables (Pydantic)
│   └── constants.py            # Magic numbers → Named constants
├── frontend/
│   ├── package.json            # Dependencies (Vue 3.5, TypeScript 5.6)
│   ├── vite.config.ts          # Build configuration
│   └── src/
│       ├── components/         # Reusable Vue components
│       ├── views/              # Page-level components
│       ├── composables/        # Reusable logic (useAuth, useWebSocket)
│       └── styles/             # SCSS design system (global classes)
migrations/                      # Database migrations (run automatically)
docker/
├── Dockerfile                  # Multi-stage build (Node → Python)
└── docker-compose.yml          # PostgreSQL + App stack
tests/                          # Pytest tests (integration + unit)
```

## Path-Specific Instructions (Code Patterns)

**⚠️ DO NOT add code examples to this file!** All code-specific patterns are in:

| File | Applies To | Contains |
|------|-----------|----------|
| `.github/instructions/frontend.instructions.md` | `app/frontend/**/*.vue`, `*.ts`, `*.scss` | Vue patterns, SCSS utilities, TypeScript conventions |
| `.github/instructions/backend.instructions.md` | `app/**/*.py` | FastAPI patterns, SQLAlchemy queries, error handling |
| `.github/instructions/api.instructions.md` | `app/routes/**/*.py` | Endpoint design, validation, response formats |
| `.github/instructions/migrations.instructions.md` | `migrations/**/*.py` | Migration patterns, rollback safety |
| `.github/instructions/docker.instructions.md` | `docker/**`, `Dockerfile` | Build optimization, CRLF issues |
| `.github/instructions/security.instructions.md` | `**/*` | Path validation, input sanitization, credentials |

**When working on a file**, Copilot automatically loads **both**:
1. This file (project-wide conventions)
2. The matching path-specific file (code patterns for that file type)

## Commit Message Convention

**CRITICAL**: Use [Conventional Commits](https://conventionalcommits.org/) for semantic versioning.

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Purpose | Version Impact |
|------|---------|----------------|
| `feat` | New feature or capability | **Minor** bump (0.X.0) |
| `fix` | Bug fix | **Patch** bump (0.0.X) |
| `docs` | Documentation only | Patch bump |
| `style` | Formatting, whitespace, no code change | Patch bump |
| `refactor` | Code restructuring, no behavior change | Patch bump |
| `perf` | Performance improvement | Patch bump |
| `test` | Adding or updating tests | Patch bump |
| `chore` | Build, tooling, dependencies | Patch bump |
| `ci` | CI/CD pipeline changes | Patch bump |

### Breaking Changes → Major Bump

A breaking change triggers a **Major** version bump (X.0.0). Mark it with either:

- An `!` after the type/scope: `feat!: remove legacy API`
- A `BREAKING CHANGE:` footer in the commit body

### Scopes

- `api` – Backend API routes/endpoints
- `ui` – Frontend components/pages
- `auth` – Authentication/security
- `db` – Database/models/migrations
- `docker` – Docker/deployment
- `recording` – Recording engine/Streamlink
- `notifications` – Notification system
- `scheduler` – Background jobs/task queue
- `ws` – WebSocket connections

### Rules

- Type and description are **required**
- Scope is optional but encouraged
- Description must be lowercase, imperative mood ("add" not "added" or "adds")
- No period at the end of the description
- Body and footer are optional
- Use `!` or `BREAKING CHANGE:` only for genuinely incompatible changes

### Examples

```bash
feat(api): add multi-proxy health checks
fix(recording): handle streamlink timeout gracefully
refactor(ui): eliminate hardcoded colors
chore(deps): update Python dependencies
feat!: redesign recording scheduling API
ci: add ARM64 Docker build
perf(db): add index on recording.created_at
```

## CI/CD Pipeline

**GitHub Actions** (`.github/workflows/docker-build.yml`):
- **Triggers**: Push to `main` or `develop` branches
- **Steps**:
  1. Frontend build (cached if unchanged)
  2. Docker build (multi-stage: Node → Python)
  3. Security scan (Trivy, Safety, Bandit)
  4. Auto-versioning (from commit message)
  5. Push to DockerHub + GHCR

**⚠️ Pipeline Fails If:**
- Frontend build errors (SCSS/TypeScript)
- Python tests fail (`pytest`)
- Security vulnerabilities (CRITICAL/HIGH)
- Docker build fails

## Key Configuration Files

**DO NOT modify these without understanding:**

| File | Purpose | Notes |
|------|---------|-------|
| `requirements.txt` | Python dependencies | Pin versions for security |
| `app/frontend/package.json` | Node dependencies | Lock file committed |
| `app/config/settings.py` | Environment variables | Uses Pydantic validation |
| `docker/docker-compose.yml` | Container orchestration | PostgreSQL + App |
| `.env.example` | Environment template | Copy to `.env` |

## Documentation Locations

**DO NOT duplicate information - reference these:**

| Topic | File | Purpose |
|-------|------|---------|
| Architecture | `docs/ARCHITECTURE.md` | Recording flow, state management |
| Design System | `docs/DESIGN_SYSTEM.md` | SCSS utilities, component patterns |
| Master Tasks | `docs/MASTER_TASK_LIST.md` | All project tasks + status |
| Known Issues | `docs/KNOWN_ISSUES_SESSION_7.md` | Current bugs |
| API Reference | `/docs` endpoint | Interactive OpenAPI docs |

## Development Workflow

```bash
# 1. Create feature branch
git checkout -b feat/your-feature

# 2. Make changes (use path-specific instructions!)

# 3. Validate locally
pytest tests/ -v                 # Backend
cd app/frontend && npm run build # Frontend

# 4. Commit (conventional commits!)
git commit -m "feat(scope): description"

# 5. Push
git push origin feat/your-feature

# 6. Create PR (CI runs automatically)
```

## Trust These Instructions

**⚠️ DO NOT search for build commands** - they are documented above.  
**⚠️ DO NOT add code examples here** - they belong in path-specific instructions.  
**⚠️ DO NOT duplicate documentation** - reference existing files.

If you find errors in these instructions, open an issue to update them.

---

**Architecture Notes:**
- Database migrations run automatically at startup (idempotent)
- Frontend served by FastAPI (built assets in `app/frontend/dist/`)
- WebSocket connections for real-time updates
- Background task queue for post-processing (AsyncIO)
- Session-based authentication (HTTP-only cookies)

**Security Requirements:**
- ALL fetch() calls MUST include `credentials: 'include'`
- ALL file paths MUST be validated (`validate_path_security()`)
- ALL user input MUST be sanitized
- Use parameterized queries (SQLAlchemy ORM)

See `.github/instructions/security.instructions.md` for complete security patterns.

---

## Twitch Authentication & Token Management

**CRITICAL:** Twitch restricts third-party OAuth apps from accessing H.265/AV1 codecs and 1440p quality. Only **browser authentication tokens** grant full access.

### Token Usage Priority

The system uses multiple authentication methods for different purposes:

1. **Browser Token (Environment Variable)** - `TWITCH_OAUTH_TOKEN`
   - **Priority:** HIGHEST (used first if available)
   - **Purpose:** Stream recording with full quality access
   - **Features:** H.265/AV1 codecs, 1440p60, ad-free (with Turbo)
   - **Source:** Manual extraction from browser cookie (`auth-token`)
   - **Validity:** 60-90 days
   - **Configuration:** Set in `.env` or `docker-compose.yml`

2. **App Credentials** - `TWITCH_APP_ID` + `TWITCH_APP_SECRET`
   - **Purpose:** EventSub webhooks (stream online/offline notifications)
   - **Purpose:** Username validation (`/api/streamers/validate/`)
   - **Type:** App-to-App OAuth (not user-specific)
   - **Configuration:** Required for EventSub functionality

3. **Database OAuth Token** - User OAuth Flow
   - **Priority:** FALLBACK (only if browser token unavailable)
   - **Purpose:** Follower import (`/api/twitch/followed-channels`)
   - **Purpose:** User profile information
   - **Limitation:** Cannot access H.265/1440p (Twitch API restriction)
   - **Storage:** Encrypted in `global_settings` table

### Implementation Details

**Token Service Priority** (`app/services/system/twitch_token_service.py`):
```python
async def get_valid_access_token(self) -> Optional[str]:
    # 1. Check environment variable FIRST (browser token)
    if self.settings.TWITCH_OAUTH_TOKEN:
        return self.settings.TWITCH_OAUTH_TOKEN
    
    # 2. Fall back to database OAuth token
    # 3. Return None if neither available
```

**Streamlink Command** (`app/utils/streamlink_utils.py`):
- Token passed as: `--twitch-api-header=Authorization=OAuth TOKEN`
- Format: Single argument with `=` (prevents tuple parsing)
- Per-recording token overrides config file

**UI Guide** (`app/frontend/src/components/settings/TwitchConnectionPanel.vue`):
- Shows browser token extraction steps
- Copy-to-clipboard JavaScript snippet
- Explains quality benefits (H.265, 1440p, ad-free)

### Browser Token Setup

**Extract from browser** (F12 console on twitch.tv):
```javascript
document.cookie.split("; ").find(item=>item.startsWith("auth-token="))?.split("=")[1]
```

**Set in environment**:
```env
TWITCH_OAUTH_TOKEN=<your-browser-token-here>
```

**Verification**:
- Check logs for: `✅ Using browser token from environment variable (TWITCH_OAUTH_TOKEN)`
- Logs show: `→ Full quality access: H.265/AV1 codecs, 1440p, ad-free (Turbo)`

### Quality Verification

**With Browser Token:**
- Available streams: `audio_only, 160p, 360p, 480p, 720p60, 1080p60, 1440p60 (if supported)`
- Codecs: H.264, H.265/HEVC, AV1 (if supported by stream)
- Ad-blocking: `[plugins.twitch][info] Will skip ad segments`

**Without Browser Token (OAuth only):**
- Limited to: `1080p60` maximum
- Codecs: H.264 only
- Ads may appear in recordings

### Related Files

| File | Purpose |
|------|---------|
| `app/services/system/twitch_token_service.py` | Token priority logic, auto-refresh |
| `app/config/settings.py` | `TWITCH_OAUTH_TOKEN` environment variable |
| `app/utils/streamlink_utils.py` | Streamlink command generation, token passing |
| `app/frontend/src/components/settings/TwitchConnectionPanel.vue` | Browser token setup UI |
| `BROWSER_TOKEN_SETUP.md` | Comprehensive setup guide |
| `docker/docker-compose.yml` | Environment variable documentation |

### Troubleshooting

**Issue:** Recording stuck at 1080p H.264  
**Solution:** Set `TWITCH_OAUTH_TOKEN` environment variable with browser token

**Issue:** Token not working  
**Solution:** Check logs for token source, verify 30-character length, restart container

**Issue:** Ads in recordings  
**Solution:** Browser token + Twitch Turbo subscription required for ad-free
