---
applyTo: "docker/**/*,Dockerfile,docker-compose*.yml,.dockerignore"
---

# Docker Configuration Guidelines

## Multi-Stage Builds

Use multi-stage builds to minimize image size:

```dockerfile
# Build stage
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY app/frontend/package*.json ./
RUN npm ci
COPY app/frontend/ ./
RUN npm run build

# Production stage
FROM python:3.11-slim
WORKDIR /app
COPY --from=frontend-builder /app/frontend/dist ./app/frontend/dist
# ... rest of image
```

## Layer Caching

Optimize layer caching by copying dependency files first:

```dockerfile
# ✅ CORRECT: Dependencies cached separately
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# ❌ WRONG: Invalidates cache on any code change
COPY . .
RUN pip install -r requirements.txt
```

## Security

- Use non-root user for production
- Scan images for vulnerabilities
- Pin dependency versions
- Use slim/alpine base images where possible

## Docker Compose

- Use `.env` files for configuration
- Define health checks for services
- Use named volumes for persistence
- Set proper restart policies

## Line Endings

**IMPORTANT**: Use LF line endings for shell scripts:
```dockerfile
COPY --chmod=755 entrypoint.sh /entrypoint.sh
RUN dos2unix /entrypoint.sh  # For Windows development
```

## Environment Variables

Define all required environment variables with defaults:
```yaml
environment:
  - DATABASE_URL=${DATABASE_URL:-postgresql://user:pass@db:5432/streamvault}
  - LOG_LEVEL=${LOG_LEVEL:-INFO}
```

## Common Patterns

### Health Checks
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

### Volume Mounts
```yaml
volumes:
  - ./app:/app:ro  # Read-only for code
  - recordings:/recordings  # Named volume for data
```
