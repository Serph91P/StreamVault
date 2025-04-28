FROM python:3.13-slim

# Create non-root user and set up directories
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser && \
    mkdir -p /app/data/profile_images && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy Python requirements first
COPY requirements.txt ./

# Install Node.js, npm, and required packages including FFmpeg and GPAC (MP4Box)
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    wget \
    build-essential \
    pkg-config \
    zlib1g-dev \
    libssl-dev \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y \
    nodejs \
    gcc \
    python3-dev \
    libpq-dev \
    # Install GPAC from source for MP4Box
    && cd /tmp \
    && wget https://github.com/gpac/gpac/archive/refs/tags/v2.2.1.tar.gz \
    && tar -xzf v2.2.1.tar.gz \
    && cd gpac-2.2.1 \
    && ./configure --static-bin --use-zlib=no --use-ogg=no --use-vorbis=no --use-theora=no --use-openjpeg=no --use-a52=no --use-mad=no --use-faad=no --use-png=no --use-jpeg=no --use-ft=no --use-js=no --use-opengl=no \
    && make -j$(nproc) \
    && make install \
    && cd / \
    && rm -rf /tmp/gpac-2.2.1 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install streamlink==7.2.0 \
    && apt-get remove -y gcc python3-dev build-essential pkg-config \
    && apt-get autoremove -y \
    && apt-get clean \
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

# Create recordings directory with correct permissions
RUN mkdir -p /recordings && \
    chown -R appuser:appuser /recordings && \
    chmod 775 /recordings

# Update library cache to find newly installed libraries
RUN ldconfig

USER appuser

EXPOSE 7000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000"]