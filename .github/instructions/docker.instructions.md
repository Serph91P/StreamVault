---
applyTo: "docker/**/*,Dockerfile,docker-compose*.yml,.dockerignore"
---

# Docker Configuration Guidelines - StreamVault

## Architecture Overview

StreamVault uses a **four-stage multi-stage build** optimized for:
- ⚡ **Fast rebuilds** via aggressive layer caching
- 🔒 **Security** with Alpine Linux + non-root user
- 📦 **Small images** (Alpine base + smart dependency management)
- 🔄 **CI/CD integration** with conditional builds

### Build Stages
1. **base**: Alpine system dependencies (FFmpeg, PostgreSQL, Node.js)
2. **python-deps**: Python packages (cached separately)
3. **frontend-builder**: Vue 3 TypeScript build (conditional)
4. **final**: Combined production image

## Multi-Stage Builds - StreamVault Pattern

### ✅ Optimal Stage Structure

```dockerfile
# Stage 1: Base system dependencies
FROM python:3.14-alpine AS base
RUN apk update && apk upgrade && \
    apk add --no-cache \
    curl ffmpeg gcc g++ postgresql-dev \
    nodejs npm bash && \
    rm -rf /var/cache/apk/*

# Stage 2: Python dependencies (cached independently)
FROM base AS python-deps
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 3: Frontend build (conditional via CI/CD)
FROM base AS frontend-builder
WORKDIR /app/frontend
COPY app/frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit
COPY app/frontend/ ./
RUN npm run build

# Stage 4: Final production image
FROM python-deps AS final
COPY --from=frontend-builder /app/frontend/dist /app/app/frontend/dist
COPY app/ ./app/
USER appuser
```

### ❌ Anti-Patterns to Avoid

```dockerfile
# DON'T: Update npm at runtime (adds 50MB+ to every build)
RUN npm install -g npm@latest

# DON'T: Multiple security updates (invalidates cache)
RUN apk update && apk upgrade
# ... later ...
RUN apk update && apk upgrade  # Duplicate!

# DON'T: Install dependencies after code copy
COPY . .
RUN pip install -r requirements.txt  # Cache invalidated on ANY code change

# DON'T: Build frontend without caching package installs
COPY app/frontend/ ./
RUN npm install && npm run build  # No package.json caching!
```

## Layer Caching Optimization

### 🎯 Cache-Friendly Dockerfile Order

**Golden Rule**: Copy files from **least frequently changed** to **most frequently changed**

```dockerfile
# 1. System dependencies (rarely change)
RUN apk add --no-cache ffmpeg postgresql-dev

# 2. Package manifests (change occasionally)
COPY requirements.txt package.json ./

# 3. Install dependencies (cached until manifests change)
RUN pip install -r requirements.txt
RUN npm ci

# 4. Application code (changes frequently)
COPY app/ ./app/

# 5. Build steps (only run when code changes)
RUN npm run build
```

### 🚀 CI/CD Caching Strategy (GitHub Actions)

```yaml
- name: Build and push Docker image
  uses: docker/build-push-action@v5
  with:
    context: .
    file: docker/Dockerfile
    # ✅ Use GitHub Actions cache with branch-specific scope
    cache-from: |
      type=gha,scope=build-${{ github.ref_name }}
      type=gha,scope=build-main
    cache-to: type=gha,mode=max,scope=build-${{ github.ref_name }}
```

**Benefits**:
- Base layer cached: ~2 min → 30 sec builds
- Python deps cached: Only rebuild when requirements.txt changes
- Frontend cached: Skip npm install if package.json unchanged

## Security Best Practices

### 🔒 Non-Root User (MANDATORY)

```dockerfile
# Create user BEFORE installing app files
RUN addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -s /bin/bash -D appuser

# Set ownership AFTER copying files
COPY --chown=appuser:appuser app/ ./app/

# Drop privileges at the end
USER appuser
```

### 🛡️ Alpine Security Updates

```dockerfile
# ✅ CORRECT: Single update at start of each stage
FROM python:3.14-alpine AS base
RUN apk update && apk upgrade && \
    apk add --no-cache curl && \
    rm -rf /var/cache/apk/*

# ❌ WRONG: Multiple updates throughout Dockerfile
RUN apk update && apk upgrade
# ... 50 lines later ...
RUN apk update && apk upgrade  # Wastes cache!
```

### 🔍 Vulnerability Scanning (Required in CI/CD)

```yaml
- name: Run Trivy vulnerability scanner
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: frequency2098/streamvault:latest
    format: 'sarif'
    severity: 'CRITICAL,HIGH'

- name: Python dependency security check
  run: |
    pip install safety bandit
    safety check --json
    bandit -r app/ -f json
```

## Docker Compose Configuration

### ✅ Production-Ready Compose

```yaml
services:
  app:
    image: frequency2098/streamvault:latest
    container_name: streamvault
    user: "1000:1000"  # Non-root user
    
    # Resource limits (prevent memory leaks)
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
        reservations:
          memory: 512M
          cpus: '0.5'
    
    # Health checks (critical for orchestration)
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7000/health"]
      interval: 30s
      timeout: 10s
      start_period: 40s
      retries: 3
    
    # Logging configuration
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    
    volumes:
      - app_data:/app/data
      - ./recordings:/recordings
      - ./logs:/app/logs
    
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - TZ=Europe/Berlin
    
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    container_name: streamvault_db
    
    # Database resource limits
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
    
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 5
    
    volumes:
      - db_data:/var/lib/postgresql/data
    
    restart: unless-stopped

volumes:
  db_data:
  app_data:

networks:
  streamvault_network:
    driver: bridge
```

### 🔧 Development vs Production

```yaml
# docker-compose.dev.yml - Development overrides
services:
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile
      args:
        BUILD_ENV: development
    
    volumes:
      # Live code reloading
      - ../app:/app/app
      - app_data:/app/data
    
    environment:
      - LOG_LEVEL=DEBUG
      - ENVIRONMENT=development
```

## Line Endings & Cross-Platform

**CRITICAL**: Shell scripts MUST use LF line endings (not CRLF)

```dockerfile
# Fix Windows CRLF → LF conversion
COPY entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Alternative: Use --chmod flag (Docker 20.10+)
COPY --chmod=755 entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh
```

**Git Configuration** (.gitattributes):
```gitattributes
*.sh text eol=lf
entrypoint.sh text eol=lf
```

## Environment Variables & Secrets

### ✅ Secure Configuration

```yaml
# Use .env file (NEVER commit to git)
environment:
  - DATABASE_URL=${DATABASE_URL}
  - TWITCH_APP_SECRET=${TWITCH_APP_SECRET}
  - EVENTSUB_SECRET=${EVENTSUB_SECRET}

# Provide defaults for non-sensitive values
environment:
  - LOG_LEVEL=${LOG_LEVEL:-INFO}
  - TZ=${TZ:-UTC}
  - ENVIRONMENT=${ENVIRONMENT:-production}
```

### 🚫 Never Do This

```yaml
# ❌ Hardcoded secrets
environment:
  - DATABASE_PASSWORD=supersecret123

# ❌ Secrets in Dockerfile
ENV TWITCH_SECRET="abc123"

# ❌ Secrets in git-tracked .env
# Commit .env.example instead, users copy to .env
```

## .dockerignore Optimization

**Purpose**: Reduce Docker build context size (faster uploads to Docker daemon)

```dockerignore
# Git & CI/CD
.git
.github/
.gitignore

# Documentation (not needed in image)
*.md
docs/
CONTRIBUTING.md

# Development files
.vscode/
.idea/
*.log
temp_logs/

# Python cache
__pycache__/
*.py[cod]
.pytest_cache/
.coverage

# Node.js
node_modules/
npm-debug.log*

# Docker files (don't need themselves in context)
Dockerfile*
docker-compose*.yml
.dockerignore

# Tests
tests/
test_*.py
*_test.py

# Build artifacts
dist/
build/
*.egg-info/

# Recordings (mount as volumes)
recordings/

# Local config
.env.local
.env.*.local
```

**Impact**: Reduces build context from ~500MB → ~50MB

## BuildKit Features (Advanced)

### Secret Mounting (for private dependencies)

```dockerfile
# RUN --mount=type=secret for temporary secrets
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf \
    pip install -r requirements.txt
```

### Cache Mounts (faster pip/npm installs)

```dockerfile
# Cache pip packages between builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Cache npm packages
RUN --mount=type=cache,target=/root/.npm \
    npm ci
```

## Performance Optimization Checklist

Before pushing Docker changes, verify:

- [ ] **Layer caching**: Dependencies copied before code
- [ ] **Stage isolation**: Each stage serves one purpose
- [ ] **Security updates**: Only at stage start (not repeated)
- [ ] **Non-root user**: Applied at final stage
- [ ] **.dockerignore**: Excludes dev files, tests, docs
- [ ] **Resource limits**: Defined in docker-compose.yml
- [ ] **Health checks**: Implemented for all services
- [ ] **Logging config**: Max size/file limits set
- [ ] **Secrets**: Never hardcoded, use .env
- [ ] **CI/CD caching**: GitHub Actions cache configured

## Common Issues & Solutions

### Issue: Slow Frontend Builds
**Solution**: Pre-build frontend in CI/CD, copy dist to image
```yaml
- name: Build Frontend
  run: |
    cd app/frontend
    npm ci --prefer-offline
    npm run build
```

### Issue: Large Image Size
**Solutions**:
- ✅ Use Alpine (not debian/ubuntu)
- ✅ `--no-cache-dir` for pip installs
- ✅ `apk add --no-cache` + `rm -rf /var/cache/apk/*`
- ✅ Multi-stage builds (don't copy build tools to final stage)

### Issue: Permission Errors
**Solution**: Set ownership AFTER copying files
```dockerfile
COPY app/ ./app/
RUN chown -R appuser:appuser /app
USER appuser
```

### Issue: Cache Not Used in CI/CD
**Solution**: Use branch-specific cache scopes
```yaml
cache-from: |
  type=gha,scope=build-${{ github.ref_name }}
  type=gha,scope=build-main  # Fallback to main
```

## Monitoring & Metrics

Track these metrics in CI/CD:

```yaml
- name: Image size comparison
  run: |
    docker images frequency2098/streamvault:latest --format "{{.Size}}"
    
- name: Build time
  run: |
    echo "Build completed in ${{ job.duration }} seconds"

- name: Layer count
  run: |
    docker history frequency2098/streamvault:latest --no-trunc
```

**Targets for StreamVault**:
- 🎯 Image size: < 800MB (Alpine + FFmpeg)
- 🎯 Build time (cached): < 1 min
- 🎯 Build time (uncached): < 5 min
- 🎯 Layer count: < 20 layers

---

**Remember**: Docker optimization is about **balancing** build speed, image size, security, and maintainability. Don't over-optimize at the cost of readability!
