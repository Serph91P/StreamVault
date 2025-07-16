@echo off
echo 🚀 StreamVault Development Server
echo ================================
echo.
echo Starting local development server...
echo Server will be available at: http://localhost:8000
echo Press Ctrl+C to stop
echo.

REM Set environment variables for local development
set DATABASE_URL=sqlite:///./streamvault_local.db
set LOG_LEVEL=DEBUG
set ENVIRONMENT=development
set BASE_URL=http://localhost:8000

REM Create local directories
if not exist "recordings_local" mkdir recordings_local
if not exist "data_local" mkdir data_local  
if not exist "logs_local" mkdir logs_local

REM Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app

pause
