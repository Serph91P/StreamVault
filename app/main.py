from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from app.routes import streamers, auth
import logging
import hmac
import hashlib
import json
import asyncio

from app.config.logging_config import setup_logging
from app.database import engine
import app.models as models
from app.dependencies import websocket_manager, get_event_registry, get_twitch, get_auth_service
from app.middleware.error_handler import error_handler
from app.middleware.logging import logging_middleware
from app.config.settings import settings
from app.middleware.auth import AuthMiddleware

# Initialize application components
logger = setup_logging()
models.Base.metadata.create_all(bind=engine)
app = FastAPI()
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
@app.on_event("startup")
async def startup_event():
    await get_twitch()
    await get_event_registry()
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    event_registry = await get_event_registry()
    logger.info("Application shutdown complete")

# EventSub Routes
@app.get("/eventsub/callback")
@app.head("/eventsub/callback")
async def eventsub_root():
    return Response(content="Twitch EventSub Endpoint", media_type="text/plain")

@app.post("/eventsub/callback")
async def eventsub_callback(request: Request):
    try:
        # Read the headers and body
        headers = request.headers
        body = await request.body()

        # Extract the Twitch Message Type
        message_type = headers.get("Twitch-Eventsub-Message-Type")
        logger.debug(f"Received EventSub request: type={message_type}, headers={headers}, body={body}")

        # Handle challenge requests
        if message_type == "webhook_callback_verification":
            body_json = json.loads(body)
            challenge = body_json.get("challenge")
            if challenge:
                logger.info("Challenge request received and processed successfully.")
                # Respond with the challenge and set Content-Type to exactly 'text/plain' without charset
                return Response(content=challenge, media_type=None, headers={"Content-Type": "text/plain"})
            else:
                logger.error("Challenge request missing 'challenge' field.")
                return Response(status_code=400)

        # Validate signature for notifications and revocations
        message_id = headers.get("Twitch-Eventsub-Message-Id", "")
        timestamp = headers.get("Twitch-Eventsub-Message-Timestamp", "")
        signature = headers.get("Twitch-Eventsub-Message-Signature", "")

        if not all([message_id, timestamp, signature]):
            logger.error("Missing required headers for signature verification")
            return Response(status_code=403)

        # Compute and verify the HMAC signature
        hmac_message = message_id + timestamp + body.decode()
        expected_signature = "sha256=" + hmac.new(
            settings.WEBHOOK_SECRET.encode("utf-8"),
            hmac_message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if signature != expected_signature:
            logger.error("Invalid webhook signature")
            return Response(status_code=403)

        # Process the notification
        if message_type == "notification":
            event_registry = await get_event_registry()
            body_json = json.loads(body)
            event_type = body_json.get("subscription", {}).get("type")
            event_data = body_json.get("event")

            if event_type and event_data:
                handler = event_registry.handlers.get(event_type)
                if handler:
                    # Process event asynchronously
                    asyncio.create_task(handler(event_data))
                    return Response(status_code=204)

        # Initialize the event registry
        # event_registry = await get_event_registry()

        # if message_type == "notification":
        #     event_type = body_json.get("subscription", {}).get("type")
        #     event_data = body_json.get("event")

        #     if not event_type or not event_data:
        #         logger.error("Missing event type or data in notification")
        #         return Response(status_code=400)

        #     handler = event_registry.handlers.get(event_type)
        #     if handler:
        #         logger.info(f"Handling event type: {event_type}")
        #         try:
                    # Start event processing asynchronously
                    # asyncio.create_task(handler(event_data))
                    # Return immediately with 204 No Content
            #         return Response(status_code=204)
            #     except Exception as e:
            #         logger.error(f"Error processing event: {e}", exc_info=True)
            #         return Response(status_code=500)
            # else:
            #     logger.warning(f"No handler found for event type: {event_type}")
            #     return Response(status_code=400)

        # Handle revocation messages
        if message_type == "revocation":
            logger.warning("Subscription revoked by Twitch")
            return Response(status_code=204)

        # Unsupported message type
        logger.warning(f"Unsupported message type: {message_type}")
        return Response(status_code=400)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return Response(status_code=500)
    
# API routes first
app.include_router(streamers.router)
app.include_router(auth.router, prefix="/auth")


#Subscription test
@app.post("/api/admin/test-subscription/{twitch_id}")
async def test_subscription(
    twitch_id: str, 
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    try:
        response = await event_registry.twitch.create_eventsub_subscription(
            'stream.online',
            '1',
            {'broadcaster_user_id': twitch_id},
            {
                'method': 'webhook', 
                'callback': f"{event_registry.settings.WEBHOOK_URL}/callback", 
                'secret': event_registry.settings.EVENTSUB_SECRET
            }
        )
        return {"success": True, "response": response}
    except Exception as e:
        return {"success": False, "error": str(e)}

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
