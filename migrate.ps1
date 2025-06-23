# Safe migration runner for StreamVault (PowerShell)
# This script runs all database migrations safely and idempotently

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting StreamVault database migrations..." -ForegroundColor Green

# Change to the script directory
Set-Location $PSScriptRoot

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please ensure Python is installed and in PATH." -ForegroundColor Red
    exit 1
}

# Check if we can import required modules
try {
    python -c "import sqlalchemy; from app.config.settings import settings; from app.services.migration_service import MigrationService" 2>$null
    Write-Host "✅ Required modules available" -ForegroundColor Green
} catch {
    Write-Host "❌ Required Python modules not found. Please install dependencies:" -ForegroundColor Red
    Write-Host "   pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Run the migrations using MigrationService
Write-Host "🔄 Executing database migrations..." -ForegroundColor Blue

try {
    python -c "from app.services.migration_service import MigrationService; import sys; sys.exit(0 if MigrationService.run_safe_migrations() else 1)"
    Write-Host "✅ All migrations completed successfully!" -ForegroundColor Green
    Write-Host "🎯 Database is now up to date." -ForegroundColor Green
} catch {
    Write-Host "❌ Migration failed. Check the logs above for details." -ForegroundColor Red
    exit 1
}

Write-Host "🎉 Migration process completed!" -ForegroundColor Green
