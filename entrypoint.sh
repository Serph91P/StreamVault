#!/bin/bash

# Check if frontend dist directory exists
if [ ! -d "/app/app/frontend/dist" ]; then
    echo "Frontend dist directory not found. Building frontend..."
    cd /app/frontend
    npm install
    npm run build
    
    # Make sure the dist directory is copied to the right location
    mkdir -p /app/app/frontend
    cp -r dist /app/app/frontend/
    echo "Frontend built successfully."
else
    echo "Frontend dist directory found. Skipping build."
fi

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 7000
