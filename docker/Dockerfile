# Use Alpine Linux for smaller attack surface and fewer vulnerabilities
FROM python:3.14-alpine AS base

# Install system dependencies with security updates in a single layer
# Grouped by purpose for better readability and caching
RUN apk update && apk upgrade && \
    apk add --no-cache \
    # Core utilities
    curl \
    bash \
    # Media processing
    ffmpeg \
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

# Stage for Python dependencies (cached separately for optimal layer reuse)
FROM base AS python-deps

# Copy only requirements.txt first for maximum cache efficiency
COPY requirements.txt ./

# Install Python dependencies with pip cache mounting for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir streamlink==8.0.0

# Stage for frontend (only rebuilt when frontend changes)
FROM base AS frontend-builder
WORKDIR /app/frontend

# Copy package files first for npm cache optimization
COPY app/frontend/package*.json ./

# Install npm dependencies with cache mounting (no global npm update needed)
# Use npm ci for faster, reproducible installs
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

# Final stage - combine everything into production image
FROM python-deps AS final

WORKDIR /app

# Copy built frontend from frontend stage
COPY --from=frontend-builder /app/frontend/dist /app/app/frontend/dist

# Copy application code and migrations
COPY app/ ./app/
COPY migrations/ ./migrations/

# Copy and prepare entrypoint script (fix Windows CRLF line endings)
COPY entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Create all necessary directories with correct permissions
RUN mkdir -p \
    /recordings \
    /app/logs/streamlink \
    /app/logs/ffmpeg \
    /app/logs/app && \
    chown -R appuser:appuser /app /recordings && \
    chmod 775 /recordings && \
    chmod -R 775 /app/logs

# Switch to non-root user for security
USER appuser

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:7000/health || exit 1

EXPOSE 7000

ENTRYPOINT ["/app/entrypoint.sh"]
