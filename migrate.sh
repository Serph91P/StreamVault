#!/bin/bash
# Safe migration runner for StreamVault
# This script runs all database migrations safely and idempotently

set -e  # Exit on any error

echo "🚀 Starting StreamVault database migrations..."

# Change to the script directory
cd "$(dirname "$0")"

# Check if Python environment is set up
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please ensure Python is installed and in PATH."
    exit 1
fi

# Check if we can import required modules
if ! python -c "import sqlalchemy; from app.config.settings import settings; from app.services.migration_service import MigrationService" 2>/dev/null; then
    echo "❌ Required Python modules not found. Please install dependencies:"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Run the migrations using MigrationService
echo "🔄 Executing database migrations..."
if python -c "from app.services.migration_service import MigrationService; import sys; sys.exit(0 if MigrationService.run_safe_migrations() else 1)"; then
    echo "✅ All migrations completed successfully!"
    echo "🎯 Database is now up to date."
else
    echo "❌ Migration failed. Check the logs above for details."
    exit 1
fi

echo "🎉 Migration process completed!"
