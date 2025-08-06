# Use Alpine Linux for smaller attack surface and fewer vulnerabilities
FROM python:3.13.3-alpine AS base

# Create non-root user and set up directories
RUN addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -s /bin/bash -D appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

WORKDIR /app

# Install system dependencies with security updates
RUN apk update && apk upgrade && \
    apk add --no-cache \
    curl \
    ffmpeg \
    gcc \
    python3-dev \
    postgresql-dev \
    musl-dev \
    libffi-dev \
    openssl-dev \
    wget \
    git \
    cmake \
    zlib-dev \
    nodejs \
    npm \
    bash \
    && rm -rf /var/cache/apk/*

# Stage for Python dependencies (cached separately)
FROM base AS python-deps
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --upgrade -r requirements.txt \
    && pip install --no-cache-dir --upgrade streamlink==7.4.0

# Stage for frontend (only rebuilt when frontend changes)
FROM base AS frontend-builder
WORKDIR /app/frontend
COPY app/frontend/package*.json ./

# Only install npm dependencies if dist doesn't exist (for local builds)
RUN if [ ! -d "../frontend/dist" ]; then \
        echo "No pre-built frontend found, setting up npm..." && \
        npm install -g npm@latest && \
        npm ci --prefer-offline --no-audit && \
        npm audit fix --audit-level=moderate || echo "Some vulnerabilities may remain but build continues"; \
    else \
        echo "Pre-built frontend detected, skipping npm setup"; \
    fi

# Copy frontend sources
COPY app/frontend/ ./

# Build frontend only if not already built and not in development mode
ARG BUILD_ENV=production
RUN if [ "$BUILD_ENV" = "production" ]; then \
        if [ -d "dist" ] && [ "$(ls -A dist 2>/dev/null)" ]; then \
            echo "✅ Using pre-built frontend from CI/CD pipeline"; \
        else \
            echo "Building frontend in production mode..." && \
            rm -rf dist || true && \
            npm run build || { \
                echo "Build failed, cleaning cache and retrying..." && \
                rm -rf node_modules/.cache || true && \
                npm run build; \
            }; \
        fi \
    else \
        echo "Skipping frontend build in development mode..." && \
        mkdir -p dist; \
    fi

# Final stage - combine everything
FROM python-deps AS final

# Copy built frontend from frontend stage
COPY --from=frontend-builder /app/frontend/dist /app/app/frontend/dist

# Back to main directory and copy only necessary app files
WORKDIR /app
COPY app/ ./app/
COPY migrations/ ./migrations/

# Copy debug scripts for troubleshooting (production containers)
COPY debug_task_execution.py ./debug_task_execution.py

# Create directories with correct permissions
RUN mkdir -p /recordings && \
    mkdir -p /app/migrations && \
    mkdir -p /app/logs/streamlink && \
    mkdir -p /app/logs/ffmpeg && \
    mkdir -p /app/logs/app && \
    chown -R appuser:appuser /app /recordings && \
    chmod 775 /recordings && \
    chmod -R 775 /app/migrations && \
    chmod -R 775 /app/logs

# Copy the entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Run final security update
RUN apk update && apk upgrade && rm -rf /var/cache/apk/*

USER appuser

EXPOSE 7000

ENTRYPOINT ["/app/entrypoint.sh"]
