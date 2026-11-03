"""Web Push transport using py-vapid and RFC8291 encrypted content encoding."""

import base64
import http.client
import json
import logging
import time
import urllib.parse
from typing import Any, Dict, Union

try:
    import http_ece
    from py_vapid import Vapid
    from cryptography.hazmat.primitives.asymmetric import ec

    HAS_VAPID = True
except ImportError:
    HAS_VAPID = False

logger = logging.getLogger("streamvault")


class WebPushException(Exception):
    """Provider rejection; only HTTP 410 confirms an expired subscription."""

    def __init__(self, message, response=None):
        self.message = message
        self.response = response
        super().__init__(message)


class ModernWebPushService:
    def __init__(self, vapid_private_key: str, vapid_claims: Dict[str, str]):
        self.disabled = not HAS_VAPID
        if self.disabled:
            logger.warning("Web Push dependencies not available")
            return
        self.vapid = Vapid.from_string(private_key=vapid_private_key)
        self.claims = dict(vapid_claims)

    def encode_payload(self, data: Union[str, Dict, bytes]) -> bytes:
        if isinstance(data, str):
            return data.encode()
        if isinstance(data, dict):
            return json.dumps(data).encode()
        if isinstance(data, bytes):
            return data
        raise TypeError("Data must be string, dict, or bytes")

    def send_notification(
        self,
        subscription_info: Dict[str, Any],
        data: Union[str, Dict, bytes],
        ttl: int = 30,
    ) -> bool:
        """Send encrypted content; return False locally, raise on provider rejection."""
        if self.disabled:
            return False
        conn = None
        try:
            if isinstance(subscription_info, str):
                subscription_info = json.loads(subscription_info)
            endpoint = urllib.parse.urlsplit(subscription_info["endpoint"])
            if (
                endpoint.scheme != "https"
                or not endpoint.hostname
                or endpoint.username is not None
                or endpoint.password is not None
                or endpoint.fragment
            ):
                raise ValueError("Invalid push endpoint")
            # Derive per-request claims: neither a stale audience nor expiry may leak
            # between providers; the persistent signing identity stays unchanged.
            claims = {
                **self.claims,
                "aud": f"https://{endpoint.hostname.lower()}"
                + (f":{endpoint.port}" if endpoint.port not in (None, 443) else ""),
                "exp": int(time.time()) + 43200,
            }
            headers = self.vapid.sign(claims)
            headers["TTL"] = str(ttl)
            payload = None
            if data:
                keys = subscription_info["keys"]
                auth = base64.urlsafe_b64decode(
                    keys["auth"] + "=" * (-len(keys["auth"]) % 4)
                )
                p256dh = base64.urlsafe_b64decode(
                    keys["p256dh"] + "=" * (-len(keys["p256dh"]) % 4)
                )
                if len(auth) != 16 or len(p256dh) != 65:
                    raise ValueError("Invalid subscription keys")
                raw = self.encode_payload(data)
                # RFC8291 permits one record; 4096 includes the 86-byte header
                # and 17-byte delimiter/tag overhead (maximum plaintext 3993).
                if len(raw) > 3993:
                    raise ValueError("Push payload too large")
                payload = http_ece.encrypt(
                    raw,
                    private_key=ec.generate_private_key(ec.SECP256R1()),
                    dh=p256dh,
                    auth_secret=auth,
                    version="aes128gcm",
                )
                headers.update(
                    {
                        "Content-Encoding": "aes128gcm",
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(len(payload)),
                    }
                )
            conn = http.client.HTTPSConnection(endpoint.netloc, timeout=30)
            path = endpoint.path or "/"
            if endpoint.query:
                path += f"?{endpoint.query}"
            conn.request("POST", path, body=payload, headers=headers)
            response = conn.getresponse()
            if not 200 <= response.status < 300:
                logger.warning(
                    "Push provider rejected delivery (HTTP %s)", response.status
                )
                raise WebPushException(
                    f"Push failed (HTTP {response.status})", response=response
                )
            return True
        except WebPushException:
            raise
        except Exception:
            # Endpoint capabilities, subscription keys and provider bodies must
            # never enter logs, including exception messages from dependencies.
            logger.warning("Push delivery failed before provider acceptance")
            return False
        finally:
            if conn is not None:
                conn.close()


webpush_service = None  # Configured lazily by existing callers.
