"""
Health check endpoint for monitoring and load balancers
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger("streamvault")

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint for load balancers and monitoring
    Returns 200 OK if application is running
    """
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        
        # Test database connection
        db_healthy = False
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            db_healthy = True
        except Exception as db_error:
            logger.error(f"Health check - database failed: {db_error}")
        
        # Application is healthy if it responds
        status = "healthy" if db_healthy else "degraded"
        
        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "application": "healthy",
                "database": "healthy" if db_healthy else "unhealthy"
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

@router.get("/health/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check - returns 200 only if all critical systems are ready
    Used by Kubernetes/Docker to know when service is ready to accept traffic
    """
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        import subprocess
        
        checks = {
            "database": False,
            "ffmpeg": False,
            "streamlink": False
        }
        
        # Database check
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            checks["database"] = True
        except:
            pass
        
        # FFmpeg check
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5
            )
            checks["ffmpeg"] = result.returncode == 0
        except:
            pass
        
        # Streamlink check
        try:
            result = subprocess.run(
                ["streamlink", "--version"],
                capture_output=True,
                timeout=5
            )
            checks["streamlink"] = result.returncode == 0
        except:
            pass
        
        # Service is ready if all critical checks pass
        all_ready = all(checks.values())
        
        if all_ready:
            return {
                "status": "ready",
                "timestamp": datetime.now().isoformat(),
                "checks": checks
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_ready",
                    "checks": checks
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/health/live")
async def liveness_check() -> Dict[str, str]:
    """
    Liveness check - returns 200 if application process is alive
    Used by Kubernetes/Docker to restart crashed containers
    """
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    }
