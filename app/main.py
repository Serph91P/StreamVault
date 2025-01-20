from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from app.routes import streamers, auth
import logging
import hmac
import hashlib
import json
import asyncio

from app.events.handler_registry import EventHandlerRegistry

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
        # Read headers and body
        headers = request.headers
        body = await request.body()

        # Debug logging for request details
        logger.debug(f"Raw headers: {dict(headers)}")
        logger.debug(f"Raw body length: {len(body)}")
        logger.debug(f"Raw body content: {body.decode()}")

        # Extract required headers
        message_id = headers.get("Twitch-Eventsub-Message-Id", "")
        timestamp = headers.get("Twitch-Eventsub-Message-Timestamp", "")
        signature = headers.get("Twitch-Eventsub-Message-Signature", "")
        message_type = headers.get("Twitch-Eventsub-Message-Type", "")

        logger.debug(f"Message ID: {message_id}")
        logger.debug(f"Timestamp: {timestamp}")
        logger.debug(f"Received signature: {signature}")
        logger.debug(f"Message Type: {message_type}")

        # Validate required headers
        if not all([message_id, timestamp, signature, message_type]):
            logger.error("Missing required headers for signature verification.")
            return Response(status_code=403)

        # Create HMAC signature
        hmac_message = message_id + timestamp + body.decode()
        expected_signature = "sha256=" + hmac.new(
            settings.EVENTSUB_SECRET.encode("utf-8"),
            hmac_message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        logger.debug(f"Computed signature: {expected_signature}")
        logger.debug(f"HMAC message content: {hmac_message}")

        # Use a timing-safe comparison for signature validation
        if not hmac.compare_digest(signature, expected_signature):
            logger.error(
                f"Invalid webhook signature. "
                f"Expected: {expected_signature}, Received: {signature}"
            )
            return Response(status_code=403)

        # Process webhook message
        if message_type == "webhook_callback_verification":
            # Handle challenge verification
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


# @app.post("/eventsub/callback")
# async def eventsub_callback(request: Request):
#     try:
#         # Read the headers and body
#         headers = request.headers
#         body = await request.body()

#         # Debug logging for request details
#         logger.debug(f"Raw headers: {dict(headers)}")
#         logger.debug(f"Raw body length: {len(body)}")
#         logger.debug(f"Raw body content: {body.decode()}")

#         # Extract the Twitch Message Type
#         message_type = headers.get("Twitch-Eventsub-Message-Type")
#         logger.debug(f"Received EventSub request: type={message_type}")

#         valid_message_types = {"webhook_callback_verification", "notification", "revocation"}
#         if message_type not in valid_message_types:
#             logger.warning(f"Unsupported message type: {message_type}")
#             return Response(status_code=400)

#         # Handle challenge requests
#         if message_type == "webhook_callback_verification":
#             try:
#                 body_json = json.loads(body)
#             except json.JSONDecodeError as e:
#                 logger.error(f"Failed to parse JSON body: {e}")
#                 return Response(status_code=400)

#             challenge = body_json.get("challenge")
#             if challenge:
#                 logger.info("Challenge request received and processed successfully.")
#                 return Response(content=challenge, media_type=None, headers={"Content-Type": "text/plain"})
#             else:
#                 logger.error("Challenge request missing 'challenge' field.")
#                 return Response(status_code=400)

#         # Validate signature
#         message_id = headers.get("Twitch-Eventsub-Message-Id", "")
#         timestamp = headers.get("Twitch-Eventsub-Message-Timestamp", "")
#         signature = headers.get("Twitch-Eventsub-Message-Signature", "")

#         logger.debug(f"Message ID: {message_id}")
#         logger.debug(f"Timestamp: {timestamp}")
#         logger.debug(f"Received signature: {signature}")

#         if not all([message_id, timestamp, signature]):
#             logger.error("Missing required headers for signature verification")
#             return Response(status_code=403)

#         hmac_message = message_id + timestamp + body.decode()
#         expected_signature = "sha256=" + hmac.new(
#             settings.WEBHOOK_SECRET.encode("utf-8"),
#             hmac_message.encode("utf-8"),
#             hashlib.sha256
#         ).hexdigest()

#         logger.debug(f"Computed signature: {expected_signature}")
#         logger.debug(f"HMAC message content: {hmac_message}")

#         if signature != expected_signature:
#             logger.error(
#                 "Invalid webhook signature. "
#                 f"Expected: {expected_signature}, Received: {signature}, HMAC Message: {hmac_message}"
#             )
#             return Response(status_code=403)

#         # Process notifications
#         if message_type == "notification":
#             try:
#                 body_json = json.loads(body)
#             except json.JSONDecodeError as e:
#                 logger.error(f"Failed to parse JSON body: {e}")
#                 return Response(status_code=400)

#             event_registry = await get_event_registry()
#             event_type = body_json.get("subscription", {}).get("type")
#             event_data = body_json.get("event")

#             logger.debug(f"Event type: {event_type}")
#             logger.debug(f"Event data: {event_data}")

#             handler = event_registry.handlers.get(event_type)
#             if handler:
#                 try:
#                     await asyncio.wait_for(handler(event_data), timeout=5.0)
#                     return Response(status_code=204)
#                 except asyncio.TimeoutError:
#                     logger.error(f"Handler for {event_type} timed out")
#                     return Response(status_code=500)
#                 except Exception as e:
#                     logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)
#                     return Response(status_code=500)
#             else:
#                 logger.warning(f"No handler found for event type: {event_type}. Available handlers: {list(event_registry.handlers.keys())}")
#                 return Response(status_code=400)

#         if message_type == "revocation":
#             body_json = json.loads(body)
#             subscription_id = body_json.get("subscription", {}).get("id", "unknown")
#             reason = body_json.get("subscription", {}).get("status", "unknown reason")
#             logger.warning(f"Subscription {subscription_id} revoked by Twitch. Reason: {reason}")
#             return Response(status_code=204)

#     except Exception as e:
#         logger.error(f"Error processing webhook: {e}", exc_info=True)
#         return Response(status_code=500)

    
# API routes first
app.include_router(streamers.router)
app.include_router(auth.router, prefix="/auth")


#Subscription test
@app.post("/api/admin/test-subscription/{twitch_id}")
async def test_subscription(
    twitch_id: str, 
    event_registry: EventHandlerRegistry = Depends(get_event_registry)
):
    logger.debug(f"Received request to test subscription for Twitch ID: {twitch_id}")
    try:
        logger.debug(f"Starting EventSub subscription creation for Twitch ID: {twitch_id}")
        logger.debug(f"EventSub callback URL: {event_registry.settings.WEBHOOK_URL}/callback")
        logger.debug(f"EventSub secret: {event_registry.settings.EVENTSUB_SECRET}")

        # Attempt to create the subscription
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
        
        logger.debug(f"Raw subscription creation response: {response}")

        # Fetch existing subscriptions for additional context
        existing_subscriptions = await event_registry.twitch.get_eventsub_subscriptions()
        logger.debug(f"Existing EventSub subscriptions: {existing_subscriptions}")

        # Return detailed response
        return {
            "success": True,
            "response": response,
            "existing_subscriptions": existing_subscriptions.data if existing_subscriptions else "No subscriptions found"
        }
    except Exception as e:
        logger.error(f"Error during subscription test for Twitch ID {twitch_id}: {e}", exc_info=True)
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
