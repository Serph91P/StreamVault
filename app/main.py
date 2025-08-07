from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.routing import APIRoute
from app.routes import streamers, auth
from app.routes import settings as settings_router
from app.routes import twitch_auth
from app.routes import recording as recording_router
from app.routes import recordings
from app.routes import logging as logging_router
from app.routes import videos
from app.routes import images
from app.routes import api_images
from app.routes import background_queue
from app.routes import streams
from app.routes import status
from app.services.system.development_test_runner import run_development_tests
import logging
import hmac
import hashlib
import json
import asyncio
import os
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from typing import Optional

from app.events.handler_registry import EventHandlerRegistry
from app.config.logging_config import setup_logging
from app.database import engine
import app.models as models
from app.dependencies import websocket_manager, get_event_registry, get_auth_service
from app.services.images.image_sync_service import image_sync_service
from app.middleware.error_handler import error_handler
from app.middleware.logging import logging_middleware
from app.config.settings import settings
from app.middleware.auth import AuthMiddleware
from app.routes import categories
from app.utils.security_enhanced import safe_file_access, safe_error_message
from app.tasks.websocket_broadcast_task import websocket_broadcast_task

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application initialization...")
    
    # Initialize services
    event_registry = None
    cleanup_task = None
    log_cleanup_task = None
    recording_service = None
    
    try:
        # Run database migrations always (development and production)
        logger.info("🔄 Running database migrations...")
        from app.services.system.migration_service import MigrationService
        try:
            migration_success = MigrationService.run_safe_migrations()
            if migration_success:
                logger.info("✅ All database migrations completed successfully")
            else:
                logger.warning("⚠️ Some migrations failed, application may have limited functionality")
        except Exception as e:
            logger.error(f"❌ Database migration failed: {e}")
            logger.warning("⚠️ Application will continue but may have limited functionality")
        
        # Image migration check and execution
        logger.info("🖼️ Checking image migration status...")
        from app.services.migration.image_migration_service import image_migration_service
        
        try:
            # Check if migration is needed
            old_dirs_exist = (
                image_migration_service.old_images_dir.exists() or 
                image_migration_service.old_artwork_dir.exists()
            )
            
            if old_dirs_exist:
                logger.info("🔄 Running image migration from old directory structure...")
                migration_stats = await image_migration_service.migrate_all_images()
                logger.info(f"✅ Image migration completed: {migration_stats}")
            else:
                logger.info("✅ No image migration needed - directory structure is up to date")
        except Exception as e:
            logger.error(f"❌ Image migration failed: {e}")
            logger.warning("⚠️ Continuing startup without image migration")
        
        # Image refresh check for missing images
        logger.info("🔄 Checking for missing images...")
        from app.services.images.image_refresh_service import image_refresh_service
        
        try:
            # Run image refresh in background (non-blocking) with error handling
            async def safe_image_refresh():
                try:
                    await image_refresh_service.check_and_refresh_missing_images()
                    logger.info("✅ Image refresh task completed successfully")
                except Exception as e:
                    logger.error(f"❌ Image refresh task failed: {e}")
            
            asyncio.create_task(safe_image_refresh())
            logger.info("✅ Image refresh task started in background")
        except Exception as e:
            logger.error(f"❌ Image refresh failed to start: {e}")
            logger.warning("⚠️ Images may not be available until manually refreshed")
        
        # Create any remaining tables from models (after migrations)
        logger.info("🔄 Creating remaining tables from models...")
        try:
            models.Base.metadata.create_all(bind=engine)
            logger.info("✅ All model tables ensured")
        except Exception as e:
            logger.error(f"❌ Error creating model tables: {e}")
            logger.warning("⚠️ Application will continue but may have limited functionality")
        
        # Initialize EventSub
        event_registry = await get_event_registry()
        await event_registry.initialize_eventsub()
        logger.info("EventSub initialized successfully")
        
        # Get recording service reference for graceful shutdown
        try:
            recording_service = getattr(event_registry, 'recording_service', None)
            if recording_service:
                logger.info("Recording service reference obtained for graceful shutdown")
        except Exception as e:
            logger.warning(f"Could not get recording service reference: {e}")
        
        # Start log cleanup service
        try:
            from app.services.system.logging_service import logging_service
            # Use the global logging service instance instead of creating a new one
            log_cleanup_task = asyncio.create_task(logging_service._schedule_cleanup(interval_hours=24))
            logger.info("Log cleanup service started")
            logger.info(f"Logging service base directory: {logging_service.logs_base_dir}")
        except Exception as e:
            logger.error(f"Failed to start log cleanup service: {e}")
        
        # Initialize background queue service (will be done later in initialize_background_services)
        try:
            logger.info("Background queue initialization deferred to initialize_background_services()")
            
            # Background queue cleanup will be handled by initialize_background_services()
            logger.info("✅ Background queue auto-cleanup will be initialized later")
            
        except Exception as e:
            logger.error(f"Failed to initialize background queue service: {e}")
            logger.exception("Full error details:")
        
        # Automated recovery service will be handled by initialize_background_services()
        try:
            logger.info("✅ Startup recovery check scheduled (runs once after 2 minutes)")
            
        except Exception as e:
            logger.error(f"❌ Failed to start startup recovery check: {e}")
            logger.warning("⚠️ Failed recordings will not be automatically recovered")
        
        # Start recording cleanup service
        try:
            from app.services.system.cleanup_service import CleanupService
            
            async def scheduled_recording_cleanup():
                while True:
                    try:
                        await CleanupService.run_scheduled_cleanup()
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Error in scheduled recording cleanup: {e}", exc_info=True)
                    
                    # Run every 12 hours
                    await asyncio.sleep(12 * 3600)
            
            cleanup_task = asyncio.create_task(scheduled_recording_cleanup())
            logger.info("Recording cleanup service started")
        except Exception as e:
            logger.error(f"Failed to start recording cleanup service: {e}")
        
        # Wait a moment for migrations to fully complete before starting services
        await asyncio.sleep(1)
        
        # Start background services AFTER migrations are guaranteed to be complete
        try:
            from app.services.init.startup_init import initialize_background_services
            await initialize_background_services()
            logger.info("✅ Background services initialized successfully")
        except Exception as e:
            logger.error(f"❌ Error starting background services: {e}", exc_info=True)
            logger.warning("⚠️ Application will continue but background processing may be limited")
            
        # Start image sync service
        try:
            await image_sync_service.start_sync_worker()
            logger.info("✅ Image sync service started")
        except Exception as e:
            logger.error(f"❌ Error starting image sync service: {e}", exc_info=True)
        
        # Start WebSocket broadcast task for real-time updates
        try:
            await websocket_broadcast_task.start()
            logger.info("WebSocket broadcast task started")
        except Exception as e:
            logger.error(f"Error starting WebSocket broadcast task: {e}", exc_info=True)
        
        # Run development tests if in debug mode
        try:
            test_success = await run_development_tests()
            if test_success:
                logger.info("✅ All development tests passed")
            else:
                logger.warning("⚠️ Some development tests failed - check logs above")
        except Exception as e:
            logger.error(f"Error running development tests: {e}", exc_info=True)
        
        logger.info("Application startup complete")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
    
    yield
    
    # Shutdown
    logger.info("🛑 Starting application shutdown...")
    
    # Gracefully shutdown recording service first (most critical)
    if recording_service:
        try:
            logger.info("🔄 Gracefully shutting down recording service...")
            await recording_service.graceful_shutdown(timeout=30)
            logger.info("✅ Recording service shutdown completed")
        except Exception as e:
            logger.error(f"❌ Error during recording service shutdown: {e}")
    
    # Shutdown active recordings broadcaster
    try:
        logger.info("🔄 Stopping active recordings broadcaster...")

        logger.info("✅ Active recordings broadcaster stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error during active recordings broadcaster shutdown: {e}")
    
    # Stop WebSocket broadcast task
    try:
        logger.info("🔄 Stopping WebSocket broadcast task...")
        await websocket_broadcast_task.stop()
        logger.info("✅ WebSocket broadcast task stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error stopping WebSocket broadcast task: {e}")
    
    # Shutdown background queue service
    try:
        logger.info("🔄 Stopping background queue service...")
        from app.services.background_queue_service import background_queue_service
        await background_queue_service.stop()
        logger.info("✅ Background queue service stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error during background queue service shutdown: {e}")
    
    # Cancel cleanup tasks
    for task_name, task in [("cleanup", cleanup_task), ("log_cleanup", log_cleanup_task)]:
        if task and not task.done():
            logger.info(f"🔄 Cancelling {task_name} task...")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info(f"✅ {task_name} task cancelled successfully")
            except Exception as e:
                logger.error(f"❌ Error cancelling {task_name} task: {e}")
    
    # Stop EventSub properly
    if event_registry:
        try:
            # Try to access eventsub attribute safely
            eventsub = getattr(event_registry, 'eventsub', None)
            if eventsub and hasattr(eventsub, 'stop'):
                logger.info("🔄 Stopping EventSub...")
                await eventsub.stop()
                logger.info("✅ EventSub stopped successfully")
            elif hasattr(event_registry, 'cleanup'):
                logger.info("🔄 Cleaning up event registry...")
                await event_registry.cleanup()
                logger.info("✅ Event registry cleaned up")
        except Exception as e:
            logger.error(f"❌ Error during EventSub shutdown: {e}")
    
    # Stop image sync service
    try:
        await image_sync_service.stop_sync_worker()
        logger.info("✅ Image sync service stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping image sync service: {e}")
    
    # Stop recording auto-fix service
    try:
        from app.services.recording.recording_auto_fix_service import recording_auto_fix_service
        await recording_auto_fix_service.stop()
        logger.info("✅ Recording auto-fix service stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping recording auto-fix service: {e}")
    
    # Close database connections
    try:
        from sqlalchemy.ext.asyncio import AsyncEngine
        if isinstance(engine, AsyncEngine):
            await engine.dispose()
        else:
            engine.dispose()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.error(f"❌ Error disposing database engine: {e}")
    
    logger.info("🎯 Application shutdown complete")

# Initialize application components
logger = setup_logging()

# Initialize FastAPI app
app = FastAPI(
    title="StreamVault API",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add Trusted Host middleware (security best practice)
if settings.is_secure:
    # Only allow requests to our configured domain in production
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            settings.domain,
            f"www.{settings.domain}",
            "localhost",  # For health checks
        ]
    )

# Add CORS middleware with secure configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # Use computed origins from settings
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
    max_age=settings.CORS_MAX_AGE,
)

# Add custom middleware
app.middleware("http")(logging_middleware)

# Enhanced security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Set proper content types for specific files
    path = request.url.path
    
    # Special handling for service worker
    if path == "/registerSW.js" or path.endswith("registerSW.js"):
        response.headers["Content-Type"] = "application/javascript"
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        # Don't set X-Content-Type-Options for service worker
        return response
    
    # Set content types based on file extension
    content_type_map = {
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.css': 'text/css',
        '.ico': 'image/x-icon',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.webmanifest': 'application/manifest+json',
        '.xml': 'application/xml',
        '.html': 'text/html',
        '.webp': 'image/webp'
    }
    
    for ext, content_type in content_type_map.items():
        if path.endswith(ext):
            response.headers["Content-Type"] = content_type
            break
    
    # Security headers (only if enabled in settings)
    if settings.SECURE_HEADERS_ENABLED:
        # Basic security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # HSTS (only for HTTPS)
        if settings.is_secure:
            response.headers["Strict-Transport-Security"] = f"max-age={settings.HSTS_MAX_AGE}; includeSubDomains"
        
        # Content Security Policy (if configured)
        if settings.CONTENT_SECURITY_POLICY:
            response.headers["Content-Security-Policy"] = settings.CONTENT_SECURITY_POLICY
        else:
            # Default CSP
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Required for Vue.js
                "style-src 'self' 'unsafe-inline'",  # Required for inline styles
                "img-src 'self' data: https: blob:",  # Allow images from various sources
                "font-src 'self' data:",
                "connect-src 'self' wss: ws: https:",  # WebSocket and API connections
                "media-src 'self' blob:",  # For video playback
                "worker-src 'self' blob:",  # For service workers
                "manifest-src 'self'",
                "frame-ancestors 'none'"
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # Permissions Policy (modern replacement for Feature Policy)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    return response

# Add request ID middleware for tracking
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    
    # Skip logging for frequent background queue polling endpoints to reduce log spam
    skip_logging_paths = [
        "/api/background-queue/stats",
        "/api/background-queue/active-tasks"
    ]
    
    # Add request ID to logger context (skip frequent polling endpoints)
    if request.url.path not in skip_logging_paths:
        logger.info(f"Request {request_id}: {request.method} {request.url.path}")
    else:
        # Log at debug level for background queue endpoints
        logger.debug(f"Request {request_id}: {request.method} {request.url.path}")
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response

# Rate limiting middleware (basic implementation)
from collections import defaultdict
from datetime import datetime, timedelta
import time

request_counts = defaultdict(list)
RATE_LIMIT_REQUESTS = 100  # requests
RATE_LIMIT_WINDOW = 60  # seconds

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for health checks, static files, and internal API calls
    if (request.url.path in ["/health", "/favicon.ico"] or 
        request.url.path.startswith("/assets/") or
        request.url.path.startswith("/api/images/") or  # Skip rate limiting for image API calls
        request.url.path.startswith("/api/sync/") or    # Skip rate limiting for sync API calls
        request.url.path.startswith("/data/")):         # Skip rate limiting for data files
        return await call_next(request)
    
    # Get client IP
    client_ip = request.client.host
    if request.headers.get("X-Forwarded-For"):
        client_ip = request.headers["X-Forwarded-For"].split(",")[0].strip()
    
    # Skip rate limiting for localhost (internal services)
    if client_ip in ["127.0.0.1", "localhost", "::1"]:
        return await call_next(request)
    
    current_time = time.time()
    
    # Clean old requests
    request_counts[client_ip] = [
        req_time for req_time in request_counts[client_ip]
        if req_time > current_time - RATE_LIMIT_WINDOW
    ]
    
    # Check rate limit
    if len(request_counts[client_ip]) >= RATE_LIMIT_REQUESTS:
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return Response(
            content="Rate limit exceeded",
            status_code=429,
            headers={
                "Retry-After": str(RATE_LIMIT_WINDOW),
                "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(current_time + RATE_LIMIT_WINDOW))
            }
        )
    
    # Add current request
    request_counts[client_ip].append(current_time)
    
    # Process request
    response = await call_next(request)
    
    # Add rate limit headers
    response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
    response.headers["X-RateLimit-Remaining"] = str(RATE_LIMIT_REQUESTS - len(request_counts[client_ip]))
    response.headers["X-RateLimit-Reset"] = str(int(current_time + RATE_LIMIT_WINDOW))
    
    return response

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from app.utils.client_ip import get_real_client_ip
    
    real_ip = get_real_client_ip(websocket)
    logger.info(f"📞 New WebSocket connection attempt from {real_ip}")
    
    await websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"📞 WebSocket disconnected: {real_ip}")
        await websocket_manager.disconnect(websocket)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "StreamVault"}

@app.get("/admin/websocket-connections")
async def get_websocket_connections():
    """Admin endpoint to monitor WebSocket connections"""
    connections = []
    async with websocket_manager._lock:
        for connection_id, ws in websocket_manager.active_connections.items():
            real_ip = getattr(ws, '_real_ip', 'unknown')
            client_identifier = getattr(ws, '_client_identifier', 'unknown')
            
            connections.append({
                "connection_id": connection_id,
                "real_ip": real_ip,
                "client_identifier": client_identifier,
                "state": ws.application_state.value if hasattr(ws.application_state, 'value') else str(ws.application_state)
            })
    
    # Group by real IP to show multiple connections per client
    clients = {}
    for conn in connections:
        ip = conn["real_ip"]
        if ip not in clients:
            clients[ip] = {"ip": ip, "connections": [], "count": 0}
        clients[ip]["connections"].append(conn)
        clients[ip]["count"] += 1
    
    return {
        "total_connections": len(connections),
        "unique_clients": len(clients),
        "clients": list(clients.values()),
        "connections": connections
    }

# EventSub Routes
@app.get("/eventsub")
@app.head("/eventsub")
async def eventsub_root():
    return Response(content="Twitch EventSub Endpoint", media_type="text/plain")

@app.post("/eventsub")
async def eventsub_callback(request: Request):
    try:
        # Read headers and body
        headers = request.headers
        body = await request.body()

        # Extract required headers
        message_id = headers.get("Twitch-Eventsub-Message-Id", "")
        timestamp = headers.get("Twitch-Eventsub-Message-Timestamp", "")
        received_signature = headers.get("Twitch-Eventsub-Message-Signature", "")
        message_type = headers.get("Twitch-Eventsub-Message-Type", "")

        # Debug logging
        logger.debug(f"Message ID: {message_id}")
        logger.debug(f"Timestamp: {timestamp}")
        logger.debug(f"Received signature: {received_signature}")
        logger.debug(f"Raw body: {body.decode()}")

        # Validate required headers
        if not all([message_id, timestamp, received_signature, message_type]):
            logger.error("Missing required headers for signature verification.")
            return Response(status_code=403)

        # Create message exactly as Twitch does
        hmac_message = message_id.encode() + timestamp.encode() + body        # Calculate HMAC using raw bytes
        calculated_signature = "sha256=" + hmac.new(
            settings.EVENTSUB_SECRET.encode(),
            hmac_message,
            hashlib.sha256
        ).hexdigest()

        # Debug HMAC calculation (without exposing sensitive data)
        logger.debug(f"HMAC message length: {len(hmac_message)}")
        logger.debug(f"Calculated signature: {calculated_signature}")
        logger.debug(f"Secret length: {len(settings.EVENTSUB_SECRET)}")

        if not hmac.compare_digest(received_signature, calculated_signature):
            logger.error(f"Signature mismatch. Got: {received_signature[:16]}..., Expected: {calculated_signature[:16]}...")
            return Response(status_code=403)

        # Process webhook message based on message_type
        if message_type == "webhook_callback_verification":
            try:
                body_json = json.loads(body)
                challenge = body_json.get("challenge")
                if challenge:
                    logger.info("Challenge request received and processed successfully.")
                    return Response(content=challenge, media_type=None, headers={"Content-Type": "text/plain"})
                else:
                    logger.error("Challenge request missing 'challenge' field.")
                    return Response(status_code=400)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON body: {e}")
                return Response(status_code=400)

        elif message_type == "notification":
            # Handle event notifications
            try:
                body_json = json.loads(body)
                event_registry = await get_event_registry()
                event_type = body_json.get("subscription", {}).get("type")
                event_data = body_json.get("event")

                logger.debug(f"Processing EventSub notification: {event_type}")
                logger.debug(f"Event data: {event_data}")

                handler = event_registry.handlers.get(event_type)
                if handler:
                    try:
                        await asyncio.wait_for(handler(event_data), timeout=5.0)
                        logger.info(f"Event {event_type} handled successfully.")
                        return Response(status_code=204)
                    except asyncio.TimeoutError:
                        logger.error(f"Handler for {event_type} timed out.")
                        return Response(status_code=500)
                    except Exception as e:
                        logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)
                        return Response(status_code=500)
                else:
                    logger.warning(f"No handler found for event type: {event_type}.")
                    return Response(status_code=400)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON body: {e}")
                return Response(status_code=400)

        elif message_type == "revocation":
            # Handle subscription revocation
            body_json = json.loads(body)
            subscription_id = body_json.get("subscription", {}).get("id", "unknown")
            reason = body_json.get("subscription", {}).get("status", "unknown reason")
            logger.warning(f"Subscription {subscription_id} revoked by Twitch. Reason: {reason}")
            return Response(status_code=204)

        else:
            logger.warning(f"Unsupported message type: {message_type}")
            return Response(status_code=400)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return Response(status_code=500)

# API routes first
app.include_router(streamers.router)
app.include_router(auth.router, prefix="/auth")
app.include_router(settings_router.router)
app.include_router(twitch_auth.router)
app.include_router(recording_router.router)
app.include_router(recordings.router, prefix="/api")  # Performance-optimized recordings API
app.include_router(logging_router.router)
app.include_router(categories.router)
app.include_router(videos.router)  # Router already has /api prefix
app.include_router(images.router)  # Images serving routes
app.include_router(api_images.router)  # Images API routes
app.include_router(background_queue.router, prefix="/api")  # Background queue routes
app.include_router(streams.router)  # Stream management routes
app.include_router(status.router, prefix="/api")  # Status API routes - independent of WebSocket

# Unified recovery routes (replaces old orphaned + failed recovery)
from app.api import unified_recovery_endpoints
app.include_router(unified_recovery_endpoints.router)

# Automated recovery routes
from app.api import automated_recovery_endpoints
app.include_router(automated_recovery_endpoints.router)

# Push notification routes
from app.routes import push as push_router
app.include_router(push_router.router)

# Admin routes
from app.routes import admin as admin_router
app.include_router(admin_router.router)

# Migration routes
from app.routes import migration as migration_router
app.include_router(migration_router.router)

# Explicit SPA routes - these must come after API routes but before static files
@app.get("/streamers")
@app.get("/videos") 
@app.get("/subscriptions")
@app.get("/add-streamer")
@app.get("/settings")
@app.get("/welcome")
@app.get("/admin")
@app.get("/auth/setup")
@app.get("/auth/login")
@app.get("/streamer/{streamer_id}")
@app.get("/streamer/{streamer_id}/stream/{stream_id}/watch")
async def serve_spa_routes():
    """Serve SPA for known frontend routes"""
    for path in ["app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"]:
        try:
            import os
            if os.path.exists(path):
                return FileResponse(path, media_type="text/html")
        except Exception as e:
            continue
    
    return Response(content="SPA index.html not found", status_code=500)

# Static files for assets
try:
    # Try the standard production path
    app.mount("/assets", StaticFiles(directory="app/frontend/dist/assets"), name="assets")
except Exception as e:
    logger.warning(f"Could not mount static files from app/frontend/dist/assets: {e}")
    # Fallback to a secondary path for development
    try:
        app.mount("/assets", StaticFiles(directory="/app/app/frontend/dist/assets"), name="assets")
        logger.info("Successfully mounted static files from /app/app/frontend/dist/assets")
    except Exception as e:
        logger.error(f"Failed to mount static assets: {e}")

# Static files for PWA assets (icons, registerSW.js, etc.)
try:
    # Try the standard production path for PWA files
    app.mount("/pwa", StaticFiles(directory="app/frontend/dist"), name="pwa-primary")
except Exception as e:
    logger.warning(f"Could not mount PWA files from app/frontend/dist: {e}")
    # Fallback to a secondary path for development
    try:
        app.mount("/pwa", StaticFiles(directory="/app/app/frontend/dist"), name="pwa-fallback")
        logger.info("Successfully mounted PWA files from /app/app/frontend/dist")
    except Exception as e:
        logger.error(f"Failed to mount PWA assets: {e}")

app.mount("/data", StaticFiles(directory="/app/data"), name="data")

# Mount images directory for unified image service
import os
from pathlib import Path
# Hardcoded Docker path - always /recordings in container
recordings_dir = "/recordings"
images_dir = Path(recordings_dir) / ".media"
# Create the directory if it doesn't exist
images_dir.mkdir(parents=True, exist_ok=True)
# Create subdirectories
(images_dir / "profiles").mkdir(parents=True, exist_ok=True)
(images_dir / "categories").mkdir(parents=True, exist_ok=True)
(images_dir / "artwork").mkdir(parents=True, exist_ok=True)
# Mount the images directory under both /data/images and /api/media for compatibility
app.mount("/data/images", StaticFiles(directory=str(images_dir)), name="images")
app.mount("/api/media", StaticFiles(directory=str(images_dir)), name="media")

# PWA Files serving - these must be at root level
@app.get("/manifest.json")
async def serve_manifest():
    for path in ["app/frontend/public/manifest.json", "/app/app/frontend/public/manifest.json"]:
        try:
            return FileResponse(
                path,
                media_type="application/manifest+json",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/manifest.webmanifest")
async def serve_manifest_webmanifest():
    for path in ["app/frontend/public/manifest.webmanifest", "/app/app/frontend/public/manifest.webmanifest"]:
        try:
            return FileResponse(
                path,
                media_type="application/manifest+json",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/sw.js")
async def service_worker():
    for path in ["app/frontend/dist/sw.js", "/app/app/frontend/dist/sw.js"]:
        try:
            return FileResponse(
                path,
                media_type="application/javascript",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Service-Worker-Allowed": "/",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/browserconfig.xml")
async def serve_browserconfig():
    for path in ["app/frontend/public/browserconfig.xml", "/app/app/frontend/public/browserconfig.xml"]:
        try:
            return FileResponse(
                path,
                media_type="application/xml",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/pwa-test.html")
async def serve_pwa_test():
    for path in ["app/frontend/public/pwa-test.html", "/app/app/frontend/public/pwa-test.html"]:
        try:
            return FileResponse(path, media_type="text/html")
        except:
            continue
    return Response(status_code=404)

@app.get("/pwa-helper.js")
async def serve_pwa_helper():
    for path in ["app/frontend/public/pwa-helper.js", "/app/app/frontend/public/pwa-helper.js"]:
        try:
            return FileResponse(path, media_type="application/javascript")
        except:
            continue
    return Response(status_code=404)

@app.get("/registerSW.js")
async def serve_register_sw():
    from app.utils.file_paths import get_pwa_file_paths
    for path in get_pwa_file_paths("registerSW.js"):
        try:
            return FileResponse(
                path, 
                media_type="application/javascript",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/workbox-{filename:path}")
async def serve_workbox_files(filename: str):
    """Serve Workbox-related files from the dist directory"""
    import os
    import re
    from pathlib import Path
    
    # SECURITY: Complete isolation - user input never reaches file operations
    # Step 1: Create whitelist of allowed workbox files (hardcoded, no user input)
    ALLOWED_WORKBOX_FILES = {
        # Common workbox filenames - add more as needed
        "74f2ef77.js": "workbox-74f2ef77.js",
        "core.js": "workbox-core.js", 
        "sw.js": "workbox-sw.js",
        "runtime.js": "workbox-runtime.js",
        "strategies.js": "workbox-strategies.js",
        "precaching.js": "workbox-precaching.js",
        "routing.js": "workbox-routing.js",
        "window.js": "workbox-window.js"
    }
    
    # Step 2: Validate user input against whitelist only
    if not isinstance(filename, str) or len(filename) > 50:
        logger.warning(f"Invalid workbox filename format: {filename}")
        return Response(status_code=404)
    
    # Step 3: Check if requested file is in whitelist
    if filename not in ALLOWED_WORKBOX_FILES:
        logger.warning(f"Workbox file not in whitelist: {filename}")
        return Response(status_code=404)
    
    # Step 4: Get hardcoded filename from whitelist (no user input involved)
    safe_filename = ALLOWED_WORKBOX_FILES[filename]
    
    # Step 5: Define hardcoded safe paths (completely isolated from user input)
    SAFE_FILE_PATHS = [
        f"app/frontend/dist/{safe_filename}",
        f"/app/app/frontend/dist/{safe_filename}"
    ]
    
    # Step 6: Try each hardcoded path (user input never touches file operations)
    for hardcoded_path in SAFE_FILE_PATHS:
        try:
            # All file operations use hardcoded paths only
            real_path = os.path.realpath(hardcoded_path)
            
            # Verify path is within expected directories
            expected_dirs = [
                os.path.realpath("app/frontend/dist"),
                os.path.realpath("/app/app/frontend/dist")
            ]
            
            path_is_safe = False
            for expected_dir in expected_dirs:
                try:
                    if os.path.commonpath([real_path, expected_dir]) == expected_dir:
                        path_is_safe = True
                        break
                except (ValueError, OSError):
                    continue
            
            # File operations on hardcoded paths only
            if path_is_safe and os.path.exists(real_path) and os.path.isfile(real_path):
                return FileResponse(
                    real_path,  # This comes from hardcoded paths, not user input
                    media_type="application/javascript",
                    headers={
                        "Cache-Control": "public, max-age=31536000",
                        "Access-Control-Allow-Origin": "*"
                    }
                )
        except Exception as e:
            logger.warning(f"Error checking hardcoded workbox path {hardcoded_path}: {e}")
            continue
    
    # No valid hardcoded path found
    logger.warning(f"Workbox file not found in any safe location: {filename}")
    return Response(status_code=404)

@app.get("/favicon.ico")
async def serve_favicon():
    from app.utils.file_paths import get_file_paths
    for path in get_file_paths("favicon.ico"):
        try:
            return FileResponse(
                path,
                media_type="image/x-icon",
                headers={"Cache-Control": "public, max-age=86400"}
            )
        except:
            continue
    return Response(status_code=404)

@app.get("/favicon.png")
async def serve_favicon_png():
    from app.utils.file_paths import get_file_paths
    # Try specific favicon.png files, then fall back to ico
    for filename in ["favicon.png", "favicon-32x32.png", "favicon.ico"]:
        for path in get_file_paths(filename):
            try:
                media_type = "image/png" if filename.endswith(".png") else "image/x-icon"
                return FileResponse(
                    path,
                    media_type=media_type,
                    headers={"Cache-Control": "public, max-age=86400"}
                )
            except:
                continue
    return Response(status_code=404)

# PWA Icons - serve from public directory
@app.get("/{icon_file}")
async def serve_pwa_icons(icon_file: str):
    # SECURITY: Complete isolation of user input from file operations
    # Step 1: Strict allowlist validation - no user data flows to file operations
    pwa_files = {
        'android-icon-36x36.png', 'android-icon-48x48.png', 'android-icon-72x72.png',
        'android-icon-96x96.png', 'android-icon-144x144.png', 'android-icon-192x192.png',
        'apple-icon-57x57.png', 'apple-icon-60x60.png', 'apple-icon-72x72.png',
        'apple-icon-76x76.png', 'apple-icon-114x114.png', 'apple-icon-120x120.png',
        'apple-icon-144x144.png', 'apple-icon-152x152.png', 'apple-icon-180x180.png',
        'apple-icon-precomposed.png', 'apple-icon.png',
        'favicon-16x16.png', 'favicon-32x32.png', 'favicon-96x96.png', 'favicon.ico',
        'icon-512x512.png', 'maskable-icon-192x192.png', 'maskable-icon-512x512.png',
        'ms-icon-70x70.png', 'ms-icon-144x144.png', 'ms-icon-150x150.png', 'ms-icon-310x310.png'
    }
    
    # Step 2: Early validation - reject if not in allowlist
    if icon_file not in pwa_files:
        return Response(status_code=404)
    
    # Step 3: Additional security checks
    if ".." in icon_file or "/" in icon_file or "\\" in icon_file:
        return Response(status_code=404)
    
    # Step 4: Create safe file mapping - completely disconnect user input from file paths
    # This mapping ensures no user data ever flows to file operations
    safe_file_mappings = {}
    base_directories = ["app/frontend/public", "/app/app/frontend/public"]
    
    for base_dir in base_directories:
        try:
            base_path = Path(base_dir)
            if not base_path.exists():
                continue
                
            # Pre-validate each allowed file independently
            for allowed_file in pwa_files:
                safe_path = base_path / allowed_file
                if safe_path.exists() and safe_path.is_file():
                    safe_file_mappings[allowed_file] = safe_path
        except Exception as e:
            logger.warning(f"Error scanning directory {base_dir}: {e}")
            continue
    
    # Step 5: Serve file using safe mapping (no user input in file operations)
    if icon_file in safe_file_mappings:
        safe_path = safe_file_mappings[icon_file]
        
        # Determine media type based on file extension
        media_type = "image/png"
        if icon_file.endswith('.ico'):
            media_type = "image/x-icon"
        elif icon_file.endswith('.svg'):
            media_type = "image/svg+xml"
        
        try:
            return FileResponse(
                str(safe_path),
                media_type=media_type,
                headers={"Cache-Control": "public, max-age=31536000"}  # 1 year
            )
        except Exception as e:
            logger.warning(f"Error serving icon file: {e}")
    
    return Response(status_code=404)

# Root route to serve index.html
@app.get("/")
async def serve_root():
    """Serve the main SPA index.html for the root route"""
    for path in ["app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"]:
        try:
            import os
            if os.path.exists(path):
                logger.info(f"Serving root index.html from: {path}")
                return FileResponse(path, media_type="text/html")
        except Exception as e:
            logger.warning(f"Could not serve root from {path}: {e}")
            continue
    
    logger.error("Could not find index.html for root route")
    return Response(content="Welcome to StreamVault - Frontend not available", status_code=500)

# Error handler
app.add_exception_handler(Exception, error_handler)

# Auth Middleware
app.add_middleware(AuthMiddleware)

# Service Worker registration script with enhanced security
@app.get("/registerSW.js")
async def serve_register_sw():
    """Serve the service worker registration script"""
    for base_path in ["/app/app/frontend/dist", "app/frontend/dist"]:
        sw_path = Path(base_path) / "registerSW.js"
        if sw_path.exists():
            # Validate file content (basic check)
            try:
                with open(sw_path, 'r') as f:
                    content = f.read()
                    # Basic validation - should contain service worker registration code
                    if 'serviceWorker' not in content:
                        logger.warning("Service worker file doesn't contain expected content")
                        continue
            except Exception as e:
                logger.error(f"Error reading service worker file: {e}")
                continue
                
            return FileResponse(
                sw_path,
                media_type="application/javascript",
                headers={
                    "Service-Worker-Allowed": "/",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "X-Content-Type-Options": "nosniff"  # Override for service worker
                }
            )
    
    # If not found in dist, serve a minimal registration script
    minimal_sw = """
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js', { scope: '/' })
            .then(reg => console.log('Service Worker registered', reg))
            .catch(err => console.error('Service Worker registration failed', err));
    }
    """
    return Response(
        content=minimal_sw,
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache"
        }
    )

# SPA catch-all route must be last - only serve for non-API paths
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # Don't serve SPA for API paths, static files, or PWA files
    if (full_path.startswith("api/") or 
        full_path.startswith("assets/") or 
        full_path.startswith("data/") or
        full_path.startswith("video/") or
        full_path.startswith("ws") or  # WebSocket
        full_path.startswith("eventsub") or  # EventSub
        full_path.startswith("health") or  # Health check
        full_path.startswith("debug/") or  # Debug endpoints
        full_path in {"manifest.json", "manifest.webmanifest", "sw.js", "browserconfig.xml", "pwa-test.html", "pwa-helper.js"} or
        full_path.endswith((".png", ".ico", ".svg", ".jpg", ".jpeg", ".gif", ".webp", ".js", ".css", ".map", ".xml"))):
        raise HTTPException(status_code=404)
    
    # For SPA routes like /streamers, /subscriptions, etc., serve index.html
    logger.info(f"SPA Fallback: Serving index.html for route '{full_path}'")
    
    # Try production path first, then fallback
    for path in ["app/frontend/dist/index.html", "/app/app/frontend/dist/index.html"]:
        try:
            import os
            if os.path.exists(path):
                logger.debug(f"Successfully serving index.html from: {path}")
                return FileResponse(path, media_type="text/html")
        except Exception as e:
            logger.warning(f"Could not serve from {path}: {e}")
            continue
    
    logger.error(f"Could not find index.html for SPA route '{full_path}' in any expected location")
    return Response(content=f"SPA index.html not found for route: {full_path}", status_code=500)
