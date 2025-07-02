FROM python:3.13.3-slim

# Create non-root user and set up directories
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser && \
    mkdir -p /app/data/profile_images && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy only what's needed for dependencies first
COPY requirements.txt ./

# Install system dependencies and Python packages
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    gcc \
    python3-dev \
    libpq-dev \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install streamlink==7.4.0 \
    && apt-get remove -y gcc python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

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
# Keep all app code in a single directory structure
WORKDIR /app
COPY app/ ./app/
COPY migrations/ ./migrations/

# Create directories with correct permissions
RUN mkdir -p /recordings && \
    mkdir -p /app/migrations && \
    mkdir -p /app/logs/streamlink && \
    mkdir -p /app/logs/ffmpeg && \
    mkdir -p /app/logs/app && \
    mkdir -p /app/data/category_images && \
    mkdir -p /app/frontend/public/images/categories && \
    chown -R appuser:appuser /app /recordings && \
    chmod 775 /recordings && \
    chmod -R 775 /app/migrations && \
    chmod -R 775 /app/logs && \
    chmod -R 775 /app/data/category_images && \
    chmod -R 775 /app/frontend/public/images/categories

# Copy the entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER appuser

EXPOSE 7000

ENTRYPOINT ["/app/entrypoint.sh"]