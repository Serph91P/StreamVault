"""
API routes for system testing and administration
"""
import logging
import platform
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


# Orphaned Recording Recovery endpoints
@router.get("/orphaned/statistics")
async def get_orphaned_statistics(max_age_hours: int = 168) -> Dict[str, Any]:
    """Get statistics about orphaned recordings"""
    try:
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        
        recovery_service = await get_orphaned_recovery_service()
        stats = await recovery_service.get_orphaned_statistics(max_age_hours)
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get orphaned statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.post("/orphaned/scan")
async def scan_orphaned_recordings(
    max_age_hours: int = 48,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Scan for orphaned recordings and optionally trigger recovery"""
    try:
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        
        recovery_service = await get_orphaned_recovery_service()
        result = await recovery_service.scan_and_recover_orphaned_recordings(
            max_age_hours=max_age_hours,
            dry_run=dry_run
        )
        
        return {
            "success": True,
            "message": f"Scan completed: {result['recovery_triggered']} recoveries triggered",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Failed to scan orphaned recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to scan: {str(e)}")


@router.post("/orphaned/recover/{recording_id}")
async def recover_specific_recording(recording_id: int) -> Dict[str, Any]:
    """Trigger recovery for a specific recording"""
    try:
        from app.services.recording.orphaned_recovery_service import get_orphaned_recovery_service
        from app.database import SessionLocal
        from app.models import Recording
        
        recovery_service = await get_orphaned_recovery_service()
        
        with SessionLocal() as db:
            recording = db.query(Recording).filter(Recording.id == recording_id).first()
            if not recording:
                raise HTTPException(status_code=404, detail=f"Recording {recording_id} not found")
            
            # Validate it's actually orphaned
            validation = await recovery_service.validate_orphaned_recording(recording)
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": f"Recording {recording_id} is not suitable for recovery: {validation['reason']}"
                }
            
            # Trigger recovery
            success = await recovery_service.trigger_orphaned_recovery(recording, db)
            
            if success:
                return {
                    "success": True,
                    "message": f"Recovery triggered for recording {recording_id}",
                    "data": {
                        "recording_id": recording_id,
                        "file_path": recording.path,
                        "file_size": validation.get("file_size")
                    }
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to trigger recovery for recording {recording_id}"
                }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to recover recording {recording_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to recover recording: {str(e)}")


# Video Debug Endpoints
@router.get("/debug/videos-database")
async def debug_videos_database(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Debug endpoint to see what's in the database vs filesystem"""
    
    try:
        from pathlib import Path
        from app.models import Stream, Streamer, Recording
        
        result = {
            "streams": [],
            "recordings": [],
            "filesystem_check": {},
            "summary": {}
        }
        
        # Check streams table
        streams = db.query(Stream, Streamer).join(
            Streamer, Stream.streamer_id == Streamer.id
        ).order_by(Stream.started_at.desc()).limit(50).all()  # Limit for performance
        
        for stream, streamer in streams:
            stream_info = {
                "id": stream.id,
                "title": stream.title,
                "streamer_name": streamer.username,
                "started_at": stream.started_at.isoformat() if stream.started_at else None,
                "ended_at": stream.ended_at.isoformat() if stream.ended_at else None,
                "recording_path": stream.recording_path,
                "category_name": stream.category_name,
                "is_live": stream.is_live
            }
            
            # Check if recording_path file exists
            if stream.recording_path:
                try:
                    path = Path(stream.recording_path)
                    stream_info["recording_path_exists"] = path.exists()
                    if path.exists():
                        stream_info["recording_path_size"] = path.stat().st_size
                except Exception as e:
                    stream_info["recording_path_error"] = str(e)
            
            result["streams"].append(stream_info)
        
        # Check recordings table
        recordings = db.query(Recording, Stream, Streamer).join(
            Stream, Recording.stream_id == Stream.id
        ).join(
            Streamer, Stream.streamer_id == Streamer.id
        ).order_by(Recording.start_time.desc()).limit(50).all()  # Limit for performance
        
        for recording, stream, streamer in recordings:
            recording_info = {
                "id": recording.id,
                "stream_id": recording.stream_id,
                "status": recording.status,
                "path": recording.path,
                "start_time": recording.start_time.isoformat() if recording.start_time else None,
                "end_time": recording.end_time.isoformat() if recording.end_time else None,
                "stream_title": stream.title,
                "streamer_name": streamer.username
            }
            
            # Check if recording path file exists
            if recording.path:
                try:
                    ts_path = Path(recording.path)
                    mp4_path = ts_path.with_suffix('.mp4')
                    
                    recording_info["ts_path_exists"] = ts_path.exists()
                    recording_info["mp4_path_exists"] = mp4_path.exists()
                    
                    if ts_path.exists():
                        recording_info["ts_path_size"] = ts_path.stat().st_size
                    if mp4_path.exists():
                        recording_info["mp4_path_size"] = mp4_path.stat().st_size
                        recording_info["mp4_path"] = str(mp4_path)
                        
                except Exception as e:
                    recording_info["path_check_error"] = str(e)
            
            result["recordings"].append(recording_info)
        
        # Check filesystem directly
        recordings_dir = Path("/recordings")
        if recordings_dir.exists():
            result["filesystem_check"]["recordings_dir_exists"] = True
            
            # List streamer directories and their subdirectories
            subdirs = []
            try:
                for streamer_dir in recordings_dir.iterdir():
                    if streamer_dir.is_dir():
                        streamer_info = {
                            "name": streamer_dir.name,
                            "path": str(streamer_dir),
                            "subdirectories": []
                        }
                        
                        # List season directories
                        for season_dir in streamer_dir.iterdir():
                            if season_dir.is_dir():
                                season_info = {
                                    "name": season_dir.name,
                                    "path": str(season_dir),
                                    "files": []
                                }
                                
                                # List files in season directory
                                for file in season_dir.iterdir():
                                    if file.suffix in ['.mp4', '.ts']:
                                        season_info["files"].append({
                                            "name": file.name,
                                            "size": file.stat().st_size,
                                            "path": str(file),
                                            "extension": file.suffix
                                        })
                                
                                streamer_info["subdirectories"].append(season_info)
                        
                        subdirs.append(streamer_info)
                
                result["filesystem_check"]["subdirectories"] = subdirs
            except Exception as e:
                result["filesystem_check"]["error"] = str(e)
        else:
            result["filesystem_check"]["recordings_dir_exists"] = False
        
        # Summary
        result["summary"] = {
            "total_streams": len(result["streams"]),
            "total_recordings": len(result["recordings"]),
            "streams_with_recording_path": len([s for s in result["streams"] if s.get("recording_path")]),
            "recordings_with_path": len([r for r in result["recordings"] if r.get("path")]),
            "mp4_files_found": len([r for r in result["recordings"] if r.get("mp4_path_exists")]),
            "filesystem_streamers": len(result["filesystem_check"].get("subdirectories", []))
        }
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error in videos database debug: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Videos debug failed: {str(e)}")


@router.get("/debug/recordings-directory")
async def debug_recordings_directory() -> Dict[str, Any]:
    """Debug endpoint to list contents of recordings directory"""
    
    try:
        from pathlib import Path
        
        result = {
            "base_recordings_dir": "/recordings",
            "directories": []
        }
        
        base_dir = Path("/recordings")
        if base_dir.exists():
            result["base_recordings_dir_exists"] = True
            
            # List all streamer directories
            for streamer_dir in base_dir.iterdir():
                if streamer_dir.is_dir():
                    streamer_info = {
                        "name": streamer_dir.name,
                        "path": str(streamer_dir),
                        "subdirectories": [],
                        "total_files": 0,
                        "total_size_mb": 0
                    }
                    
                    # List season directories
                    for season_dir in streamer_dir.iterdir():
                        if season_dir.is_dir():
                            season_info = {
                                "name": season_dir.name,
                                "path": str(season_dir),
                                "files": [],
                                "file_count": 0,
                                "total_size_mb": 0
                            }
                            
                            # List files in season directory
                            for file in season_dir.iterdir():
                                if file.is_file():
                                    file_size = file.stat().st_size
                                    season_info["files"].append({
                                        "name": file.name,
                                        "size": file_size,
                                        "size_mb": round(file_size / (1024 * 1024), 2),
                                        "path": str(file),
                                        "extension": file.suffix
                                    })
                                    season_info["file_count"] += 1
                                    season_info["total_size_mb"] += file_size / (1024 * 1024)
                            
                            season_info["total_size_mb"] = round(season_info["total_size_mb"], 2)
                            streamer_info["subdirectories"].append(season_info)
                            streamer_info["total_files"] += season_info["file_count"]
                            streamer_info["total_size_mb"] += season_info["total_size_mb"]
                    
                    streamer_info["total_size_mb"] = round(streamer_info["total_size_mb"], 2)
                    result["directories"].append(streamer_info)
        else:
            result["base_recordings_dir_exists"] = False
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error in recordings directory debug: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Directory debug failed: {str(e)}")


@router.post("/debug/check-stream-recordings")
async def debug_check_stream_recordings(stream_ids: List[int], db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Check recording availability for multiple streams"""
    
    try:
        from pathlib import Path
        from app.models import Stream, Recording
        
        results = {}
        
        # Get all streams at once
        streams = db.query(Stream).filter(Stream.id.in_(stream_ids)).all()
        stream_dict = {stream.id: stream for stream in streams}
        
        # Get all recordings for these streams at once
        recordings = db.query(Recording).filter(
            Recording.stream_id.in_(stream_ids),
            Recording.status.in_(['completed', 'post_processing'])
        ).all()
        recording_dict = {recording.stream_id: recording for recording in recordings}
        
        for stream_id in stream_ids:
            stream = stream_dict.get(stream_id)
            if not stream:
                results[stream_id] = {"has_recording": False, "method": "stream_not_found"}
                continue
            
            # Strategy 1: Check stream.recording_path
            if stream.recording_path and stream.recording_path.strip():
                try:
                    recording_path = Path(stream.recording_path)
                    if recording_path.exists() and recording_path.is_file():
                        results[stream_id] = {
                            "has_recording": True,
                            "file_path": str(recording_path),
                            "file_size": recording_path.stat().st_size,
                            "method": "stream_recording_path"
                        }
                        continue
                except Exception:
                    pass  # Continue to next strategy
            
            # Strategy 2: Check recording in database
            recording = recording_dict.get(stream_id)
            if recording and recording.path:
                try:
                    ts_path = Path(recording.path)
                    mp4_path = ts_path.with_suffix('.mp4')
                    
                    # Prefer .mp4 if it exists
                    if mp4_path.exists():
                        results[stream_id] = {
                            "has_recording": True,
                            "file_path": str(mp4_path),
                            "file_size": mp4_path.stat().st_size,
                            "method": "recording_mp4_file"
                        }
                        continue
                    elif ts_path.exists():
                        results[stream_id] = {
                            "has_recording": True,
                            "file_path": str(ts_path),
                            "file_size": ts_path.stat().st_size,
                            "method": "recording_ts_file"
                        }
                        continue
                except Exception:
                    pass  # Continue to no recording found
            
            # No recording found
            results[stream_id] = {"has_recording": False, "method": "none"}
        
        return {
            "success": True,
            "data": results
        }
        
    except Exception as e:
        logger.error(f"Error checking stream recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stream recording check failed: {str(e)}")
