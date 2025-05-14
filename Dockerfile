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
    && pip install streamlink==7.2.0 \
    && apt-get remove -y gcc python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Setup and build frontend
WORKDIR /app/frontend
COPY app/frontend/package*.json ./
RUN npm install

# Copy and build frontend sources
COPY app/frontend/ ./
RUN npm run build

# Back to main directory and copy only necessary app files
# Keep all app code in a single directory structure
WORKDIR /app
COPY app/ ./app/

# Create recordings directory with correct permissions
RUN mkdir -p /recordings && \
    chown -R appuser:appuser /app /recordings && \
    chmod 775 /recordings

USER appuser

EXPOSE 7000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000"]