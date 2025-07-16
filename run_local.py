#!/usr/bin/env python3
"""
StreamVault Local Development Server

This script allows you to run StreamVault locally without Docker for quick testing.
Uses SQLite database by default for simplicity.
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_local_env():
    """Setup local environment variables"""
    # Set basic environment variables
    os.environ['DATABASE_URL'] = 'sqlite:///./streamvault_local.db'
    os.environ['LOG_LEVEL'] = 'DEBUG'
    os.environ['ENVIRONMENT'] = 'development'
    os.environ['BASE_URL'] = 'http://localhost:8000'
    
    # Optional: Set Twitch credentials if available
    if not os.environ.get('TWITCH_APP_ID'):
        os.environ['TWITCH_APP_ID'] = 'your_twitch_app_id_here'
    if not os.environ.get('TWITCH_APP_SECRET'):
        os.environ['TWITCH_APP_SECRET'] = 'your_twitch_app_secret_here'
    if not os.environ.get('EVENTSUB_SECRET'):
        os.environ['EVENTSUB_SECRET'] = 'your_eventsub_secret_here'
    
    # Create local directories
    local_dirs = ['recordings_local', 'data_local', 'logs_local']
    for dir_name in local_dirs:
        Path(dir_name).mkdir(exist_ok=True)
    
    print("✅ Local environment setup complete")

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        print("✅ Dependencies available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Install dependencies with: pip install -r requirements.txt")
        return False

def run_migrations():
    """Run database migrations"""
    try:
        print("🔧 Running database migrations...")
        from app.migrations_init import init_database
        init_database()
        print("✅ Database migrations complete")
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False
    return True

def start_server():
    """Start the FastAPI development server"""
    print("🚀 Starting StreamVault development server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📍 API docs will be available at: http://localhost:8000/docs")
    print("🔄 Hot reload enabled - changes will auto-restart the server")
    print("\n📋 Press Ctrl+C to stop the server\n")
    
    try:
        # Start uvicorn with hot reload
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload",
            "--reload-dir", "app"
        ])
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")

def main():
    """Main entry point"""
    print("🔧 StreamVault Local Development Setup")
    print("=====================================")
    
    # Check if we're in the right directory
    if not Path("app").exists() or not Path("requirements.txt").exists():
        print("❌ Please run this script from the StreamVault root directory")
        sys.exit(1)
    
    # Setup environment
    setup_local_env()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Run migrations
    if not run_migrations():
        print("⚠️  Migration failed, but continuing...")
    
    # Start server
    start_server()

if __name__ == "__main__":
    main()
