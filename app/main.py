from fastapi import FastAPI, WebSocket, WebSocketRoute, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from app.routes import streamers, auth
from app.routes import settings as settings_router
import logging
import hmac
import hashlib
import json
import asyncio

from contextlib import asynccontextmanager

from app.events.handler_registry import EventHandlerRegistry

from app.config.logging_config import setup_logging
from app.database import engine
import app.models as models
from app.dependencies import websocket_manager, get_event_registry, get_twitch, get_auth_service
from app.middleware.error_handler import error_handler
from app.middleware.logging import logging_middleware
from app.config.settings import settings
from app.middleware.auth import AuthMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    print("\n=== Registered Routes ===")
    for route in app.routes:
        if isinstance(route, APIRoute):
            print(f"Route: {route.path}, Methods: {route.methods}")
        elif isinstance(route, WebSocketRoute):
            print(f"WebSocket Route: {route.path}")
    print("=======================\n")
    
    # Original startup event logic
    await get_twitch()
    await get_event_registry()
    logger.info("Application startup complete")
    
    yield
    
    # Original shutdown event logic
    event_registry = await get_event_registry()
    logger.info("Application shutdown complete")

# Initialize application components
logger = setup_logging()
models.Base.metadata.create_all(bind=engine)
app = FastAPI(lifespan=lifespan)
app.middleware("http")(logging_middleware)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)

# Application Lifecycle Events
# @app.on_event("startup")
# async def startup_event():
#     await get_twitch()
#     await get_event_registry()
#     logger.info("Application startup complete")

# @app.on_event("shutdown")
# async def shutdown_event():
#     event_registry = await get_event_registry()
#     logger.info("Application shutdown complete")

# EventSub Routes
@app.get("/eventsub/callback")
@app.head("/eventsub/callback")
async def eventsub_root():
    return Response(content="Twitch EventSub Endpoint", media_type="text/plain")

@app.post("/eventsub/callback")
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
        hmac_message = message_id.encode() + timestamp.encode() + body

        # Calculate HMAC using raw bytes
        calculated_signature = "sha256=" + hmac.new(
            settings.EVENTSUB_SECRET.encode(),
            hmac_message,
            hashlib.sha256
        ).hexdigest()

        # Debug HMAC calculation
        logger.debug(f"HMAC message: {hmac_message}")
        logger.debug(f"Calculated signature: {calculated_signature}")
        logger.debug(f"Secret used: {settings.EVENTSUB_SECRET}")

        if not hmac.compare_digest(received_signature, calculated_signature):
            logger.error(f"Signature mismatch. Got: {received_signature}, Expected: {calculated_signature}")
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

                logger.debug(f"Event type: {event_type}")
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
app.include_router(settings_router.router, prefix="/api/settings")

#Delete all subscriptions
@app.delete("/delete-all-subscriptions")
async def delete_all_subscriptions(event_registry: EventHandlerRegistry = Depends(get_event_registry)):
    try:
        logger.debug("Attempting to delete all subscriptions")
        
        # Holen aller bestehenden Subscriptions
        existing_subs = await event_registry.twitch.get_eventsub_subscriptions()
        logger.debug(f"Found {len(existing_subs.data)} subscriptions to delete")
        
        # Löschen jeder einzelnen Subscription
        results = []
        for sub in existing_subs.data:
            try:
                await event_registry.twitch.delete_eventsub_subscription(sub.id)
                logger.info(f"Deleted subscription {sub.id}")
                results.append({"id": sub.id, "status": "deleted"})
            except Exception as sub_error:
                logger.error(f"Failed to delete subscription {sub.id}: {sub_error}", exc_info=True)
                results.append({"id": sub.id, "status": "failed", "error": str(sub_error)})
        
        # Zusammenfassung der Ergebnisse
        return {
            "success": True,
            "deleted_subscriptions": results,
            "total_deleted": len([res for res in results if res["status"] == "deleted"]),
            "total_failed": len([res for res in results if res["status"] == "failed"]),
        }

    except Exception as e:
        logger.error(f"Error deleting all subscriptions: {e}", exc_info=True)
        return {"success": False, "error": str(e)}



# Static files for assets
app.mount("/assets", StaticFiles(directory="app/frontend/dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return FileResponse("app/frontend/dist/index.html")

# Error handler
app.add_exception_handler(Exception, error_handler)

# Auth Middleware
app.add_middleware(AuthMiddleware)
