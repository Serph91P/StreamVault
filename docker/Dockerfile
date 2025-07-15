# Use Alpine Linux for smaller attack surface and fewer vulnerabilities
FROM python:3.13.3-alpine

# Create non-root user and set up directories
RUN addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -s /bin/bash -D appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy only what's needed for dependencies first
COPY requirements.txt ./

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

# Install Python packages with latest versions
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --upgrade -r requirements.txt \
    && pip install --no-cache-dir --upgrade streamlink==7.4.0

# Setup frontend dependencies
WORKDIR /app/frontend
COPY app/frontend/package*.json ./

# Update npm to latest version and install dependencies with security fixes
RUN npm install -g npm@latest && \
    npm ci --prefer-offline --no-audit && \
    npm audit fix --audit-level=moderate || echo "Some vulnerabilities may remain but build continues"

# Copy frontend sources
COPY app/frontend/ ./

# Build frontend only if not in development mode
ARG BUILD_ENV=production
RUN if [ "$BUILD_ENV" = "production" ]; then \
        echo "Building frontend in production mode..." && \
        npm run build && \
        mkdir -p /app/app/frontend && \
        cp -r dist /app/app/frontend/; \
    else \
        echo "Skipping frontend build in development mode..."; \
    fi

# Back to main directory and copy only necessary app files
WORKDIR /app
COPY app/ ./app/
COPY migrations/ ./migrations/

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
