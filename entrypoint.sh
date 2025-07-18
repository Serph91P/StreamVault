#!/bin/bash

# Function to log with timestamp
log_msg() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    echo "$msg" >> /app/entrypoint.log
}

log_msg "Starting StreamVault entrypoint script"
log_msg "ENVIRONMENT: $ENVIRONMENT, LOG_LEVEL: $LOG_LEVEL"

# Check for environment variable to determine if we're in development mode
if [ "$ENVIRONMENT" = "development" ] || [ "$LOG_LEVEL" = "DEBUG" ]; then
    log_msg "Running in development environment..."
    
    # Check if frontend dist directory exists and has content
    if [ ! -d "/app/app/frontend/dist/assets" ]; then
        log_msg "Frontend dist assets directory not found. Building frontend..."
        cd /app/frontend
        log_msg "Installing npm dependencies..."
        npm install
        log_msg "Building frontend with npm..."
        npm run build
        
        # Make sure the dist directory is copied to the right location
        log_msg "Copying built frontend to app directory..."
        mkdir -p /app/app/frontend
        
        # Use detailed cp for better debug output
        log_msg "Contents of /app/frontend/dist before copying:"
        ls -la /app/frontend/dist | tee -a /app/entrypoint.log
        
        log_msg "Checking if assets directory exists in source:"
        ls -la /app/frontend/dist/assets | tee -a /app/entrypoint.log
        
        log_msg "Removing old dist directory if it exists"
        rm -rf /app/app/frontend/dist
        
        log_msg "Copying dist directory"
        cp -rv /app/frontend/dist /app/app/frontend/ | tee -a /app/entrypoint.log
        
        log_msg "Contents of /app/app/frontend/dist after copying:"
        ls -la /app/app/frontend/dist | tee -a /app/entrypoint.log
        
        log_msg "Checking if assets directory exists in destination:"
        ls -la /app/app/frontend/dist/assets 2>&1 | tee -a /app/entrypoint.log
        
        log_msg "Frontend built and copied successfully."
    else
        log_msg "Frontend dist assets directory found. Skipping build."
    fi
else
    log_msg "Running in production environment. Frontend should be pre-built by GitHub Actions."
    
    # Just check if the frontend dist exists
    if [ ! -d "/app/app/frontend/dist/assets" ]; then
        log_msg "WARNING: Frontend dist assets directory not found in production environment!"
        log_msg "This may indicate that the GitHub Action build failed or the image was not built correctly."
    fi
fi

# Ensure migrations directory permissions are set correctly
log_msg "Setting proper permissions for migrations directory..."
if [ -d "/app/migrations" ]; then
    chown -R appuser:appuser /app/migrations
    chmod -R 755 /app/migrations
    log_msg "Migrations directory permissions set."
else
    log_msg "WARNING: Migrations directory not found!"
fi

# Category images are now handled by unified_image_service
log_msg "Category images are now managed by unified_image_service"

# Database migrations are now handled by the application startup in main.py
log_msg "Database migrations will be handled by application startup..."

log_msg "Starting FastAPI application..."
# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 7000
