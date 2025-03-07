FROM python:3.13-slim

# Create non-root user and set up directories
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser && \
    mkdir -p /app/data/profile_images && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy Python requirements first
COPY requirements.txt ./

# Install Node.js and npm
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y \
    nodejs \
    gcc \
    python3-dev \
    libpq-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get remove -y gcc python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Setup frontend
COPY app/frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm install

# Copy and build frontend
COPY app/frontend ./
RUN npm run build

# Back to main directory and copy rest of app
WORKDIR /app
COPY . .

# Set proper permissions again after all copies
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 7000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000"]