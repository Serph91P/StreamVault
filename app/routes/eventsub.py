from fastapi import APIRouter, Request, Response
import hmac
import hashlib
import json
import asyncio
import logging

from app.dependencies import get_event_registry
from app.config.settings import settings
from app.config.constants import TIMEOUTS

logger = logging.getLogger("streamvault")

router = APIRouter()


@router.get("/eventsub")
@router.head("/eventsub")
async def eventsub_root():
    return Response(content="Twitch EventSub Endpoint", media_type="text/plain")


@router.post("/eventsub")
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
        # SECURITY: Do not log signatures or raw body, CWE-532

        # Validate required headers
        if not all([message_id, timestamp, received_signature, message_type]):
            logger.error("Missing required headers for signature verification.")
            return Response(status_code=403)

        # Create message exactly as Twitch does
        hmac_message = (
            message_id.encode() + timestamp.encode() + body
        )  # Calculate HMAC using raw bytes
        calculated_signature = (
            "sha256="
            + hmac.new(
                settings.EVENTSUB_SECRET.encode(), hmac_message, hashlib.sha256
            ).hexdigest()
        )

        # Debug HMAC calculation (without exposing sensitive data)
        logger.debug(f"HMAC message length: {len(hmac_message)}")

        if not hmac.compare_digest(received_signature, calculated_signature):
            logger.error(
                f"Signature mismatch. Got: {received_signature[:16]}..., Expected: {calculated_signature[:16]}..."
            )
            return Response(status_code=403)

        # SECURITY: Reject messages older than 10 minutes to prevent replay attacks
        try:
            from datetime import datetime as _dt, timezone as _tz

            msg_time = _dt.fromisoformat(timestamp.replace("Z", "+00:00"))
            if abs((_dt.now(_tz.utc) - msg_time).total_seconds()) > 600:
                logger.warning(
                    f"EventSub message too old (timestamp: {timestamp}), rejecting replay"
                )
                return Response(status_code=403)
        except (ValueError, TypeError):
            logger.error(f"Invalid EventSub timestamp format: {timestamp}")
            return Response(status_code=403)

        # Process webhook message based on message_type
        if message_type == "webhook_callback_verification":
            try:
                body_json = json.loads(body)
                challenge = body_json.get("challenge")
                if challenge:
                    logger.info(
                        "Challenge request received and processed successfully."
                    )
                    return Response(
                        content=challenge,
                        media_type=None,
                        headers={"Content-Type": "text/plain"},
                    )
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

                if event_registry.is_duplicate_message(
                    message_id,
                    event_type,
                    (event_data or {}).get("broadcaster_user_id"),
                ):
                    return Response(status_code=204)

                logger.debug(f"Processing EventSub notification: {event_type}")
                logger.debug(f"Event data: {event_data}")

                handler = event_registry.handlers.get(event_type)
                if handler:
                    try:
                        await asyncio.wait_for(
                            handler(event_data), timeout=TIMEOUTS.EVENT_HANDLER_TIMEOUT
                        )
                        logger.info(f"Event {event_type} handled successfully.")
                        return Response(status_code=204)
                    except asyncio.TimeoutError:
                        logger.error(f"Handler for {event_type} timed out.")
                        event_registry.forget_message(
                            message_id,
                            event_type,
                            (event_data or {}).get("broadcaster_user_id"),
                        )
                        return Response(status_code=500)
                    except Exception as e:
                        logger.error(
                            f"Error in event handler for {event_type}: {e}",
                            exc_info=True,
                        )
                        event_registry.forget_message(
                            message_id,
                            event_type,
                            (event_data or {}).get("broadcaster_user_id"),
                        )
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
            logger.warning(
                f"Subscription {subscription_id} revoked by Twitch. Reason: {reason}"
            )
            return Response(status_code=204)

        else:
            logger.warning(f"Unsupported message type: {message_type}")
            return Response(status_code=400)

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return Response(status_code=500)
