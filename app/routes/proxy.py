"""
Proxy Management API Routes

Provides endpoints for managing multiple proxy configurations with health monitoring.

CRITICAL: This prevents recording failures when proxies go down by providing
automatic health checks and failover to the best available proxy.
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, validator
from sqlalchemy import select

from app.database import SessionLocal
from app.models import ProxySettings, RecordingSettings
from app.dependencies import get_current_user
from app.services.proxy.proxy_health_service import proxy_health_service

logger = logging.getLogger('streamvault')

router = APIRouter(prefix="/api/proxy", tags=["proxy"])


# ===== Request/Response Models =====

class ProxyAddRequest(BaseModel):
    """Request model for adding a new proxy"""
    proxy_url: str
    priority: int = 0
    
    @validator('proxy_url')
    def validate_proxy_url(cls, v):
        """Validate proxy URL format"""
        if not v or not v.strip():
            raise ValueError("Proxy URL cannot be empty")
        
        v = v.strip()
        
        # Must start with http:// or https://
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Proxy URL must start with http:// or https://")
        
        return v


class ProxyUpdatePriorityRequest(BaseModel):
    """Request model for updating proxy priority"""
    priority: int


class ProxyListResponse(BaseModel):
    """Response model for proxy list"""
    proxies: List[dict]
    total: int
    enabled_count: int
    healthy_count: int


# ===== API Endpoints =====

@router.get("/list", response_model=ProxyListResponse)
async def list_proxies(
    user = Depends(get_current_user)
):
    """
    List all configured proxies with health status.
    
    Returns:
        List of all proxies with masked passwords for security
    """
    with SessionLocal() as db:
        proxies = db.query(ProxySettings).order_by(
            ProxySettings.priority,
            ProxySettings.health_status
        ).all()
        
        # Count statistics
        enabled_count = sum(1 for p in proxies if p.enabled)
        healthy_count = sum(1 for p in proxies if p.enabled and p.health_status == 'healthy')
        
        return {
            'proxies': [p.to_dict(mask_password=True) for p in proxies],
            'total': len(proxies),
            'enabled_count': enabled_count,
            'healthy_count': healthy_count
        }


@router.post("/add")
async def add_proxy(
    request: ProxyAddRequest,
    user = Depends(get_current_user)
):
    """
    Add a new proxy configuration.
    
    Args:
        request: ProxyAddRequest with proxy_url and priority
    
    Returns:
        Success message with proxy_id
    """
    with SessionLocal() as db:
        # Check for duplicate proxy URL
        existing = db.query(ProxySettings).filter(
            ProxySettings.proxy_url == request.proxy_url
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Proxy URL already exists with ID {existing.id}"
            )
        
        # Create new proxy
        new_proxy = ProxySettings(
            proxy_url=request.proxy_url,
            priority=request.priority,
            enabled=True,
            health_status='unknown',
            consecutive_failures=0,
            total_recordings=0,
            failed_recordings=0
        )
        
        db.add(new_proxy)
        db.commit()
        db.refresh(new_proxy)
        
        logger.info(f"✅ Added new proxy: {new_proxy.masked_url} (priority {new_proxy.priority})")
        
        # Trigger immediate health check (don't wait for response)
        import asyncio
        asyncio.create_task(proxy_health_service.check_proxy_health_manual(new_proxy.id))
        
        return {
            'success': True,
            'proxy_id': new_proxy.id,
            'message': 'Proxy added successfully. Health check in progress.'
        }


@router.delete("/{proxy_id}")
async def delete_proxy(
    proxy_id: int,
    user = Depends(get_current_user)
):
    """
    Delete a proxy configuration.
    
    Args:
        proxy_id: Database ID of proxy to delete
    
    Returns:
        Success message
    """
    with SessionLocal() as db:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        
        if not proxy:
            raise HTTPException(status_code=404, detail="Proxy not found")
        
        masked_url = proxy.masked_url
        
        db.delete(proxy)
        db.commit()
        
        logger.info(f"🗑️ Deleted proxy: {masked_url} (ID: {proxy_id})")
        
        return {
            'success': True,
            'message': f'Proxy {proxy_id} deleted successfully'
        }


@router.post("/{proxy_id}/toggle")
async def toggle_proxy(
    proxy_id: int,
    user = Depends(get_current_user)
):
    """
    Toggle proxy enabled/disabled status.
    
    Args:
        proxy_id: Database ID of proxy to toggle
    
    Returns:
        Success message with new enabled status
    """
    with SessionLocal() as db:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        
        if not proxy:
            raise HTTPException(status_code=404, detail="Proxy not found")
        
        # Toggle enabled status
        proxy.enabled = not proxy.enabled
        
        # Reset consecutive failures when re-enabling
        if proxy.enabled:
            proxy.consecutive_failures = 0
            logger.info(f"✅ Re-enabled proxy: {proxy.masked_url}")
        else:
            logger.info(f"⏸️ Disabled proxy: {proxy.masked_url}")
        
        db.commit()
        
        # Broadcast status update
        import asyncio
        asyncio.create_task(proxy_health_service._broadcast_proxy_status(proxy, auto_disabled=False))
        
        return {
            'success': True,
            'enabled': proxy.enabled,
            'message': f'Proxy {"enabled" if proxy.enabled else "disabled"} successfully'
        }


@router.post("/{proxy_id}/test")
async def test_proxy(
    proxy_id: int,
    user = Depends(get_current_user)
):
    """
    Manually trigger health check for a specific proxy.
    
    Args:
        proxy_id: Database ID of proxy to test
    
    Returns:
        Health check result
    """
    result = await proxy_health_service.check_proxy_health_manual(proxy_id)
    
    if 'error' in result and result['error'] == 'Proxy not found':
        raise HTTPException(status_code=404, detail="Proxy not found")
    
    return {
        'success': True,
        'result': result
    }


@router.post("/{proxy_id}/update-priority")
async def update_proxy_priority(
    proxy_id: int,
    request: ProxyUpdatePriorityRequest,
    user = Depends(get_current_user)
):
    """
    Update proxy priority for selection ordering.
    
    Args:
        proxy_id: Database ID of proxy to update
        request: ProxyUpdatePriorityRequest with new priority value
    
    Returns:
        Success message
    """
    with SessionLocal() as db:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        
        if not proxy:
            raise HTTPException(status_code=404, detail="Proxy not found")
        
        old_priority = proxy.priority
        proxy.priority = request.priority
        
        db.commit()
        
        logger.info(f"🔄 Updated proxy priority: {proxy.masked_url} - {old_priority} → {request.priority}")
        
        return {
            'success': True,
            'message': f'Proxy priority updated to {request.priority}'
        }


@router.get("/best")
async def get_best_proxy(
    user = Depends(get_current_user)
):
    """
    Get the currently selected best available proxy.
    
    This is the proxy that would be used for the next recording.
    
    Returns:
        Best proxy information (masked) or None if no healthy proxies
    """
    best_proxy_url = await proxy_health_service.get_best_proxy()
    
    if not best_proxy_url:
        return {
            'proxy': None,
            'message': 'No healthy proxies available'
        }
    
    # Get proxy details from database
    with SessionLocal() as db:
        proxy = db.query(ProxySettings).filter(
            ProxySettings.proxy_url == best_proxy_url
        ).first()
        
        if proxy:
            return {
                'proxy': proxy.to_dict(mask_password=True),
                'message': 'Best available proxy'
            }
    
    return {
        'proxy': None,
        'message': 'Proxy not found in database'
    }


@router.get("/config")
async def get_proxy_config(
    user = Depends(get_current_user)
):
    """
    Get proxy system configuration settings.
    
    Returns:
        Proxy configuration from recording_settings
    """
    with SessionLocal() as db:
        settings = db.query(RecordingSettings).first()
        
        if not settings:
            raise HTTPException(status_code=404, detail="Recording settings not found")
        
        return {
            'enable_proxy': settings.enable_proxy if hasattr(settings, 'enable_proxy') else True,
            'proxy_health_check_enabled': settings.proxy_health_check_enabled if hasattr(settings, 'proxy_health_check_enabled') else True,
            'proxy_health_check_interval_seconds': settings.proxy_health_check_interval_seconds if hasattr(settings, 'proxy_health_check_interval_seconds') else 300,
            'proxy_max_consecutive_failures': settings.proxy_max_consecutive_failures if hasattr(settings, 'proxy_max_consecutive_failures') else 3,
            'fallback_to_direct_connection': settings.fallback_to_direct_connection if hasattr(settings, 'fallback_to_direct_connection') else True,
        }


@router.post("/config/update")
async def update_proxy_config(
    enable_proxy: Optional[bool] = None,
    proxy_health_check_enabled: Optional[bool] = None,
    proxy_health_check_interval_seconds: Optional[int] = None,
    proxy_max_consecutive_failures: Optional[int] = None,
    fallback_to_direct_connection: Optional[bool] = None,
    user = Depends(get_current_user)
):
    """
    Update proxy system configuration settings.
    
    Args:
        enable_proxy: Master switch for proxy system
        proxy_health_check_enabled: Enable automatic health checks
        proxy_health_check_interval_seconds: Check interval in seconds
        proxy_max_consecutive_failures: Auto-disable threshold
        fallback_to_direct_connection: Use direct connection when all proxies fail
    
    Returns:
        Success message with updated configuration
    """
    with SessionLocal() as db:
        settings = db.query(RecordingSettings).first()
        
        if not settings:
            raise HTTPException(status_code=404, detail="Recording settings not found")
        
        # Update only provided fields
        if enable_proxy is not None:
            settings.enable_proxy = enable_proxy
        
        if proxy_health_check_enabled is not None:
            settings.proxy_health_check_enabled = proxy_health_check_enabled
        
        if proxy_health_check_interval_seconds is not None:
            if proxy_health_check_interval_seconds < 60:
                raise HTTPException(
                    status_code=400,
                    detail="Health check interval must be at least 60 seconds"
                )
            settings.proxy_health_check_interval_seconds = proxy_health_check_interval_seconds
        
        if proxy_max_consecutive_failures is not None:
            if proxy_max_consecutive_failures < 1 or proxy_max_consecutive_failures > 10:
                raise HTTPException(
                    status_code=400,
                    detail="Max consecutive failures must be between 1 and 10"
                )
            settings.proxy_max_consecutive_failures = proxy_max_consecutive_failures
        
        if fallback_to_direct_connection is not None:
            settings.fallback_to_direct_connection = fallback_to_direct_connection
        
        db.commit()
        
        logger.info("✅ Proxy configuration updated")
        
        return {
            'success': True,
            'message': 'Proxy configuration updated successfully',
            'config': {
                'enable_proxy': settings.enable_proxy,
                'proxy_health_check_enabled': settings.proxy_health_check_enabled,
                'proxy_health_check_interval_seconds': settings.proxy_health_check_interval_seconds,
                'proxy_max_consecutive_failures': settings.proxy_max_consecutive_failures,
                'fallback_to_direct_connection': settings.fallback_to_direct_connection,
            }
        }
