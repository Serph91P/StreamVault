#!/bin/bash

echo "🚀 StreamVault Development Server"
echo "================================"
echo ""
echo "Starting local development server..."
echo "Server will be available at: http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

# Set environment variables for local development
export DATABASE_URL="sqlite:///./streamvault_local.db"
export LOG_LEVEL="DEBUG"
export ENVIRONMENT="development"
export BASE_URL="http://localhost:8000"

# Create local directories
mkdir -p recordings_local data_local logs_local

# Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app
