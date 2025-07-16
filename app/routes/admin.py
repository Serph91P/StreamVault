"""
API routes for system testing and administration
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

# Import test service locally to avoid initialization issues
# from app.services.test_service import test_service  # REMOVED

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"]
)

logger = logging.getLogger("streamvault")

class TestRequest(BaseModel):
    test_names: Optional[List[str]] = None  # If None, run all tests

class TestResponse(BaseModel):
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    success_rate: float
    results: List[Dict[str, Any]]

@router.post("/tests/run", response_model=TestResponse)
async def run_tests(
    request: TestRequest = TestRequest()
) -> TestResponse:
    """
    Run comprehensive system tests
    """
    try:
        logger.info(f"Running admin tests: {request.test_names or 'all'}")
        
        # Create test service instance here
        from app.services.core.test_service import StreamVaultTestService
        test_service = StreamVaultTestService()
        
        if request.test_names:
            # TODO: Implement selective test running
            # For now, run all tests
            results = await test_service.run_all_tests()
        else:
            results = await test_service.run_all_tests()
        
        return TestResponse(**results)
        
    except Exception as e:
        logger.error(f"Error running tests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test execution failed: {str(e)}")

@router.get("/tests/available")
async def get_available_tests() -> Dict[str, List[str]]:
    """
    Get list of available tests
    """
    tests = {
        "system": [
            "dependency_streamlink",
            "dependency_ffmpeg", 
            "dependency_ffprobe",
            "dependency_python"
        ],
        "infrastructure": [
            "database_connection",
            "file_permissions",
            "disk_space",
            "proxy_connection"
        ],
        "core_functionality": [
            "streamlink_functionality",
            "ffmpeg_functionality",
            "recording_workflow",
            "metadata_generation",
            "media_server_structure"
        ],
        "communication": [
            "push_notifications",
            "websocket_functionality"
        ]
    }
    
    return tests

@router.get("/system/info")
async def get_system_info() -> Dict[str, Any]:
    """
    Get comprehensive system information
    """
    import platform
    import os
    from pathlib import Path
    from app.config.settings import settings
    
    try:
        # Try to import psutil - handle gracefully if not available
        try:
            import psutil
            has_psutil = True
        except ImportError:
            has_psutil = False
            logger.error("psutil module not installed - some system info will be unavailable")
        
        # System info
        info = {
            "system": {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "architecture": platform.architecture()[0]
            },
            "resources": {} if not has_psutil else {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory": {
                    "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                    "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                    "percent_used": psutil.virtual_memory().percent
                }
            },
            "storage": {},
            "settings": {
                "recording_directory": "/recordings",  # Hard-coded path based on Docker mount
                "vapid_configured": hasattr(settings, 'VAPID_PUBLIC_KEY') and bool(settings.VAPID_PUBLIC_KEY),
                "proxy_configured": hasattr(settings, 'HTTP_PROXY') and bool(settings.HTTP_PROXY)
            },
            "services": {
                "test_service_available": True  # Service is available when created
            }
        }
        
        # Storage info for recording directory
        try:
            recording_path = Path("/recordings")  # Hard-coded path based on Docker mount
            if recording_path.exists():
                stat = os.statvfs(recording_path)
                free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
                total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
                used_gb = total_gb - free_gb
                
                info["storage"]["recording_drive"] = {
                    "total_gb": round(total_gb, 2),
                    "used_gb": round(used_gb, 2),
                    "free_gb": round(free_gb, 2),
                    "percent_used": round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0
                }
        except Exception as e:
            info["storage"]["error"] = str(e)
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get system info: {str(e)}")

@router.post("/tests/quick-health")
async def quick_health_check() -> Dict[str, Any]:
    """
    Run a quick health check of critical systems
    """
    try:
        import subprocess
        from app.database import SessionLocal
        
        health = {
            "timestamp": "",
            "overall_status": "healthy",
            "checks": {}
        }
        
        # Database check
        try:
            from sqlalchemy import text
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            health["checks"]["database"] = {"status": "healthy", "message": "Connection successful"}
        except Exception as e:
            health["checks"]["database"] = {"status": "error", "message": str(e)}
            health["overall_status"] = "unhealthy"
        
        # FFmpeg check
        try:
            result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                health["checks"]["ffmpeg"] = {"status": "healthy", "message": "Available"}
            else:
                health["checks"]["ffmpeg"] = {"status": "error", "message": "Command failed"}
                health["overall_status"] = "warning"
        except Exception as e:
            health["checks"]["ffmpeg"] = {"status": "error", "message": str(e)}
            health["overall_status"] = "unhealthy"
        
        # Streamlink check  
        try:
            result = subprocess.run(["streamlink", "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                health["checks"]["streamlink"] = {"status": "healthy", "message": "Available"}
            else:
                health["checks"]["streamlink"] = {"status": "error", "message": "Command failed"}
                health["overall_status"] = "warning"
        except Exception as e:
            health["checks"]["streamlink"] = {"status": "error", "message": str(e)}
            health["overall_status"] = "unhealthy"
        
        # Disk space check
        try:
            import os
            from pathlib import Path
            
            recording_dir = Path("/recordings")  # Hard-coded path based on Docker mount
            stat = os.statvfs(recording_dir)
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            
            if free_gb >= 10:
                health["checks"]["disk_space"] = {"status": "healthy", "message": f"{free_gb:.1f}GB free"}
            elif free_gb >= 5:
                health["checks"]["disk_space"] = {"status": "warning", "message": f"Low space: {free_gb:.1f}GB free"}
                if health["overall_status"] == "healthy":
                    health["overall_status"] = "warning"
            else:
                health["checks"]["disk_space"] = {"status": "error", "message": f"Critical: {free_gb:.1f}GB free"}
                health["overall_status"] = "unhealthy"
        except Exception as e:
            health["checks"]["disk_space"] = {"status": "error", "message": str(e)}
            health["overall_status"] = "unhealthy"
        
        from datetime import datetime
        health["timestamp"] = datetime.now().isoformat()
        
        return health
        
    except Exception as e:
        logger.error(f"Error in quick health check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.post("/maintenance/cleanup-temp")
async def cleanup_temp_files() -> Dict[str, Any]:
    """
    Clean up temporary files from recording directory
    """
    try:
        from pathlib import Path
        import glob
        
        recording_dir = Path("/recordings")  # Hard-coded path based on Docker mount
        cleanup_stats = {
            "files_removed": 0,
            "space_freed_mb": 0,
            "errors": []
        }
        
        # Patterns for temporary files
        temp_patterns = [
            "**/*.ts",  # Temporary TS files
            "**/*.h264",  # FFmpeg temp files
            "**/*.aac",   # FFmpeg temp files
            "**/*.tmp",   # General temp files
            "**/streamlink_*.log.*",  # Old log files
            "**/ffmpeg_*.log.*"       # Old FFmpeg logs
        ]
        
        for pattern in temp_patterns:
            try:
                for file_path in recording_dir.glob(pattern):
                    if file_path.is_file():
                        try:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            cleanup_stats["files_removed"] += 1
                            cleanup_stats["space_freed_mb"] += file_size / (1024 * 1024)
                        except Exception as e:
                            cleanup_stats["errors"].append(f"Failed to remove {file_path}: {str(e)}")
            except Exception as e:
                cleanup_stats["errors"].append(f"Error with pattern {pattern}: {str(e)}")
        
        cleanup_stats["space_freed_mb"] = round(cleanup_stats["space_freed_mb"], 2)
        
        logger.info(f"Cleanup completed: {cleanup_stats['files_removed']} files removed, {cleanup_stats['space_freed_mb']}MB freed")
        
        return cleanup_stats
        
    except Exception as e:
        logger.error(f"Error in cleanup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

@router.get("/logs/recent")
async def get_recent_logs(
    lines: int = 100,
    level: str = "INFO"
) -> Dict[str, Any]:
    """
    Get recent log entries
    """
    try:
        import subprocess
        from pathlib import Path
        
        # Try to get logs from the application log file
        log_files = [
            "/app/logs/app.log",
            "/home/maxe/Dokumente/private_projects/StreamVault/app.log",
            "app.log"
        ]
        
        log_content = []
        log_file_used = None
        
        for log_file in log_files:
            log_path = Path(log_file)
            if log_path.exists():
                try:
                    # Get last N lines
                    result = subprocess.run(
                        ["tail", "-n", str(lines), str(log_path)],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        log_content = result.stdout.strip().split('\n')
                        log_file_used = str(log_path)
                        break
                except Exception as e:
                    continue
        
        # Filter by log level if specified
        if level and level.upper() != "ALL":
            log_content = [line for line in log_content if level.upper() in line]
        
        return {
            "log_file": log_file_used,
            "lines_requested": lines,
            "lines_returned": len(log_content),
            "level_filter": level,
            "logs": log_content
        }
        
    except Exception as e:
        logger.error(f"Error getting logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")

# If you need test functionality, create it as a dependency or initialize it properly in the route
@router.post("/test/{test_name}")
async def run_test(test_name: str, db: Session = Depends(get_db)):
    """Run a specific system test"""
    try:
        # Initialize test service here if needed, with proper dependencies
        # For now, let's just return a message
        return {
            "status": "error",
            "message": "Test service is currently disabled due to initialization issues"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
