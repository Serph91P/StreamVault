# StreamVault - Copilot Instructions

## Project Overview

StreamVault is a self-hosted Twitch stream recording application built with Python FastAPI (backend) and Vue 3 TypeScript (frontend). It automatically records live streams, manages metadata, and provides a Progressive Web App (PWA) interface for stream management.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL, Streamlink
- Frontend: Vue 3, TypeScript, Composition API, SCSS
- Architecture: REST API + WebSocket, Background task queues

## Repository Structure

```
app/
├── api/              # API endpoints and routes
├── services/         # Business logic (recording, cleanup, metadata)
├── models.py         # SQLAlchemy database models
├── frontend/
│   ├── src/
│   │   ├── components/  # Vue components
│   │   ├── views/       # Page views
│   │   ├── styles/      # SCSS design system
│   │   ├── composables/ # Reusable Vue logic
│   │   └── services/    # API clients
migrations/           # Database migration scripts
docker/              # Docker configuration
docs/                # Project documentation
```

## Commit Message Convention

**IMPORTANT**: This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic semantic versioning.

### Commit Message Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Commit Types and Version Impact

When generating commit messages, **ALWAYS** use these prefixes:

#### Minor Version Bump (1.0.x → 1.1.0) - Use for:
- `feat:` - New features
- `feature:` - New features (alternative)
- `add:` - Adding new functionality
- `refactor:` - Code refactoring/restructuring
- `perf:` - Performance improvements

#### Patch Version Bump (1.0.0 → 1.0.1) - Use for:
- `fix:` - Bug fixes
- `bugfix:` - Bug fixes (alternative)
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks, dependency updates
- `style:` - Code formatting, no logic changes
- `test:` - Adding or updating tests
- `ci:` - CI/CD pipeline changes

#### Major Version Bump (1.x.x → 2.0.0) - Use for:
- `BREAKING CHANGE:` in commit body
- `<type>!:` - Any type with ! suffix (e.g., `feat!:`)

### Examples for Common Scenarios

#### Adding a new feature:
```
feat: add automatic YouTube recording support

- Implemented YouTube API integration
- Added quality selection for YouTube streams
- Updated UI with YouTube platform option
```

#### Improving code quality:
```
refactor: optimize database queries and fix memory leaks

- Fixed 31 bare except blocks with specific exception handling
- Optimized 18 N+1 queries using joinedload()
- Replaced unbounded dicts with TTLCache to prevent memory leaks
- Centralized 30+ magic numbers in configuration

New Dependencies: cachetools==5.5.0
```

#### Fixing a bug:
```
fix: resolve memory leak in notification manager

The notification debounce dictionary was growing unboundedly.
Replaced with TTLCache with 5-minute expiration.
```

#### Updating dependencies:
```
chore: update Python dependencies

- Updated FastAPI to 0.110.0
- Updated SQLAlchemy to 2.0.27
- Updated all security patches
```

#### Breaking changes:
```
feat!: migrate to PostgreSQL 16

BREAKING CHANGE: Minimum PostgreSQL version is now 16.0
Users must upgrade their database before updating StreamVault.

Migration guide: docs/upgrade-pg16.md
```

### Scopes (Optional but Recommended)

Use scopes to indicate which part of the codebase is affected:

```
feat(api): add new recording endpoints
fix(ui): resolve dashboard loading issue
perf(db): add database indexes for streams table
docs(docker): update compose examples
chore(deps): update Python dependencies
```

### Rules for Copilot

1. **ALWAYS** analyze the changes first to determine the correct type
2. **PREFER** `refactor:` over `fix:` for code quality improvements
3. **USE** `feat:` for any new functionality, not just user-facing features
4. **USE** multiline commits for complex changes (body + footer)
5. **MENTION** breaking changes explicitly with `BREAKING CHANGE:`
6. **LIST** new dependencies in the commit body
7. **REFERENCE** issue numbers with `Fixes #123` or `Closes #456`

### Common Patterns in StreamVault

#### Code Quality Improvements → `refactor:`
```
refactor: improve exception handling in recording service

- Replaced bare except with specific exception types
- Added proper error logging with context
- Improved error recovery logic
```

#### Database Optimizations → `perf:`
```
perf: optimize stream queries with eager loading

- Added joinedload() for Stream.streamer relationships
- Reduced N+1 queries from 30 to 1
- 50-70% faster API response times
```

#### Docker/Infrastructure → `chore:` or `ci:`
```
chore(docker): optimize image build process

- Multi-stage build reduces image size by 40%
- Fixed Windows CRLF line ending issues
- Improved layer caching
```

#### Bug Fixes → `fix:`
```
fix: resolve recording status persistence issue

Recording states were not properly restored after restart.
Added state persistence service with graceful recovery.

Fixes #234
```

### What NOT to do

❌ **Bad:**
```
update stuff
changes
wip
fixed things
```

✅ **Good:**
```
feat: add thumbnail generation service
fix: resolve memory leak in event handler
refactor: extract configuration constants
chore: update Docker base image
```

## Path-Specific Instructions

This repository uses path-specific instructions for detailed guidelines:

- **Frontend**: See `.github/instructions/frontend.instructions.md` for Vue/TypeScript/SCSS guidelines
- **Backend**: See `.github/instructions/backend.instructions.md` for Python/FastAPI patterns
- **API**: See `.github/instructions/api.instructions.md` for endpoint design
- **Migrations**: See `.github/instructions/migrations.instructions.md` for database changes
- **Docker**: See `.github/instructions/docker.instructions.md` for containerization

## Key Principles

### Backend
- Use type hints and specific exception types
- Eager load relationships with `joinedload()` to avoid N+1 queries
- Services should be stateless; use dependency injection

### Frontend (PWA - Mobile-First)
- Use Composition API with `<script setup lang="ts">`
- **NEVER** override global `.btn` or `.status-border-*` classes
- All tables must transform to cards on mobile
- Use SCSS variables from `_variables.scss`
- Touch targets: minimum 44x44px

### Testing
- Unit tests for business logic
- Integration tests for API endpoints
- Mock external APIs (Twitch, Streamlink)

## Libraries and Frameworks

- **Backend**: FastAPI, SQLAlchemy, Pydantic, Streamlink, psycopg2
- **Frontend**: Vue 3, TypeScript, Vite, SCSS, Axios
- **Database**: PostgreSQL
- **Testing**: pytest (backend), Vitest (frontend)

## Coding Standards

- **Python**: PEP 8, type hints required, Google-style docstrings
- **TypeScript**: Strict mode, Composition API with `<script setup>`
- **SCSS**: Use design tokens from `_variables.scss`, never hard-code colors
- **Commits**: Conventional Commits for semantic versioning

---

**Remember**: The commit type determines the version bump! Choose wisely:
- New functionality? → `feat:` → Minor bump (1.0 → 1.1)
- Code improvement? → `refactor:` → Minor bump (1.0 → 1.1)
- Bug fix? → `fix:` → Patch bump (1.0.0 → 1.0.1)
