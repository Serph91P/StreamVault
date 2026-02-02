# =============================================================================
# StreamVault Multi-Stage Dockerfile
# Optimized for security, size, and build performance
# =============================================================================

# Use Alpine Linux for smaller attack surface and fewer vulnerabilities
FROM python:3.14-alpine AS base

# Build arguments for version tracking (passed from docker-build.yml)
ARG VERSION=dev
ARG BRANCH=unknown
ARG BUILD_DATE
ARG COMMIT_SHA=unknown

# Expose build args as environment variables for runtime access
ENV STREAMVAULT_VERSION=${VERSION} \
    STREAMVAULT_BRANCH=${BRANCH} \
    STREAMVAULT_BUILD_DATE=${BUILD_DATE} \
    STREAMVAULT_COMMIT_SHA=${COMMIT_SHA}

# Install system dependencies with security updates in a single layer
# Grouped by purpose for better readability and caching
RUN apk update && apk upgrade && \
    apk add --no-cache \
    # Core utilities
    curl \
    bash \
    # Media processing
    ffmpeg \
    fontconfig \
    ttf-dejavu \
    # Build dependencies for Python packages
    gcc \
    g++ \
    python3-dev \
    postgresql-dev \
    musl-dev \
    libffi-dev \
    openssl-dev \
    zlib-dev \
    cmake \
    # Node.js for frontend build
    nodejs \
    npm \
    # Additional tools
    wget \
    git \
    && rm -rf /var/cache/apk/*

# Create non-root user and set up directories
RUN addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -s /bin/bash -D appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

WORKDIR /app

# =============================================================================
# Stage 1: Python Dependencies (cached separately for optimal layer reuse)
# =============================================================================
FROM base AS python-deps

# Copy only requirements.txt first for maximum cache efficiency
COPY requirements.txt ./

# Install Python dependencies with pip cache mounting for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir streamlink==8.1.2

# =============================================================================
# Stage 2: Frontend Build (only rebuilt when frontend changes)
# =============================================================================
FROM base AS frontend-builder
WORKDIR /app/frontend

# Copy package files first for npm cache optimization
COPY app/frontend/package*.json ./

# Install npm dependencies with cache mounting
RUN --mount=type=cache,target=/root/.npm \
    if [ ! -d "../frontend/dist" ]; then \
        echo "No pre-built frontend found, installing npm dependencies..." && \
        npm ci --prefer-offline --no-audit && \
        npm audit fix --audit-level=moderate || echo "Some vulnerabilities may remain but build continues"; \
    else \
        echo "Pre-built frontend detected, skipping npm setup"; \
    fi

# Copy frontend sources (separate layer for better caching)
COPY app/frontend/ ./

# Build frontend conditionally based on environment
ARG BUILD_ENV=production
RUN if [ "$BUILD_ENV" = "production" ]; then \
        if [ -d "dist" ] && [ "$(ls -A dist 2>/dev/null)" ]; then \
            echo "✅ Using pre-built frontend from CI/CD pipeline"; \
        else \
            echo "📦 Building frontend in production mode..." && \
            rm -rf dist || true && \
            npm run build || { \
                echo "⚠️ Build failed, cleaning cache and retrying..." && \
                rm -rf node_modules/.cache || true && \
                npm run build; \
            }; \
        fi \
    else \
        echo "🔧 Skipping frontend build in development mode..." && \
        mkdir -p dist; \
    fi

# =============================================================================
# Stage 3: Final Production Image
# =============================================================================
FROM python-deps AS final

# Set production environment
ENV NODE_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy built frontend from frontend stage
COPY --from=frontend-builder /app/frontend/dist /app/app/frontend/dist

# Copy application code and migrations
COPY app/ ./app/
COPY migrations/ ./migrations/

# Copy and prepare entrypoint script (fix Windows CRLF line endings)
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Create all necessary directories with correct permissions in a single layer
RUN mkdir -p \
    /app/data \
    /recordings \
    /app/logs/streamlink \
    /app/logs/ffmpeg \
    /app/logs/app \
    /app/config/streamlink && \
    chown -R appuser:appuser /app /recordings && \
    chmod 775 /recordings && \
    chmod -R 775 /app/logs && \
    chmod -R 775 /app/config

# Remove build tools not needed at runtime (reduces attack surface)
# Note: Keeping gcc/g++ because some Python packages need them for runtime extensions
# If you don't need them, uncomment:
# RUN apk del gcc g++ python3-dev musl-dev cmake

# Switch to non-root user for security
USER appuser

# Labels for image metadata (OCI standard)
LABEL org.opencontainers.image.title="StreamVault" \
      org.opencontainers.image.description="Self-hosted Twitch stream recorder" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/your-repo/streamvault" \
      org.opencontainers.image.created="${BUILD_DATE}"

# Health check for container orchestration
# Uses the /api/health/live endpoint for lightweight liveness checks
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7000/api/health/live || exit 1

EXPOSE 7000

ENTRYPOINT ["/app/entrypoint.sh"]

# =============================================================================
# Stage 4: Minimal Runtime (for maximum size reduction)
# This stage removes build tools and creates the smallest possible image
# =============================================================================
FROM python:3.14-alpine AS runtime

# Install only runtime dependencies (no build tools)
RUN apk add --no-cache \
    curl bash ffmpeg fontconfig ttf-dejavu libpq && \
    addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -s /bin/bash -D appuser

# Copy Python packages from python-deps
COPY --from=python-deps /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy application from final stage
COPY --from=final --chown=appuser:appuser /app /app

USER appuser
WORKDIR /app

# Labels for image metadata (OCI standard)
LABEL org.opencontainers.image.title="StreamVault" \
      org.opencontainers.image.description="Self-hosted Twitch stream recorder"

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7000/api/health/live || exit 1

EXPOSE 7000

ENTRYPOINT ["/app/entrypoint.sh"]