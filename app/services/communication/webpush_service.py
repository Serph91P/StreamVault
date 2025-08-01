"""
A modernized web push service that uses py-vapid directly instead of pywebpush
This service is a drop-in replacement for the pywebpush-based implementation
"""

import json
import logging
import base64
import http.client
import urllib.parse
import os
from typing import Dict, Any, Optional, Union

try:
    from py_vapid import Vapid
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    HAS_VAPID = True
except ImportError:
    HAS_VAPID = False

logger = logging.getLogger("streamvault")

class WebPushException(Exception):
    """Exception for WebPush errors"""
    def __init__(self, message, response=None):
        self.message = message
        self.response = response
        super().__init__(message)

class ModernWebPushService:
    def __init__(self, vapid_private_key: str, vapid_claims: Dict[str, str]):
        """Initialize the web push service with VAPID keys and claims"""
        if not HAS_VAPID:
            logger.warning("py-vapid not available, web push service will be disabled")
            self.disabled = True
            return
        
        self.disabled = False
        
        # Args:
        #     vapid_private_key: The private VAPID key as a base64url-encoded string
        #     vapid_claims: Dictionary containing at least 'sub' (mailto: or https: URI)
        self.vapid = Vapid.from_string(private_key=vapid_private_key)
        self.claims = vapid_claims
        
    def _encrypt_payload(self, payload: bytes, auth: bytes, p256dh: bytes) -> bytes:
        """Encrypt payload using AES128GCM according to RFC 8291"""
        # Generate ephemeral key pair
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        
        # Get the public key in uncompressed format
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        # Deserialize the receiver's public key
        receiver_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), p256dh
        )
        
        # Perform ECDH
        shared_key = private_key.exchange(ec.ECDH(), receiver_public_key)
        
        # Derive keys using HKDF
        # Info for IKM
        info_ikm = b"WebPush: info\x00" + p256dh + public_key_bytes
        ikm = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=auth,
            info=info_ikm,
        ).derive(shared_key)
        
        # Info for CEK and Nonce
        info_cek = b"Content-Encoding: aes128gcm\x00"
        cek = HKDF(
            algorithm=hashes.SHA256(),
            length=16,
            salt=b"",
            info=info_cek,
        ).derive(ikm)
        
        info_nonce = b"Content-Encoding: nonce\x00"
        nonce = HKDF(
            algorithm=hashes.SHA256(),
            length=12,
            salt=b"",
            info=info_nonce,
        ).derive(ikm)
        
        # Encrypt the payload
        aesgcm = AESGCM(cek)
        # Add padding delimiter (0x02 followed by padding)
        padded_payload = payload + b'\x02'
        ciphertext = aesgcm.encrypt(nonce, padded_payload, None)
        
        # Return the encrypted payload with public key prepended
        return public_key_bytes + ciphertext
    
    def encode_payload(self, data: Union[str, Dict, bytes]) -> bytes:
        """Encode the payload data for sending"""
        if isinstance(data, str):
            return data.encode()
        elif isinstance(data, dict):
            return json.dumps(data).encode()
        elif isinstance(data, bytes):
            return data
        else:
            raise TypeError("Data must be string, dict, or bytes")
    
    def send_notification(self, 
                         subscription_info: Dict[str, Any], 
                         data: Union[str, Dict, bytes],
                         ttl: int = 30) -> bool:
        """Send a web push notification
        
        Args:
            subscription_info: A dict containing 'endpoint', and 'keys' with 'p256dh' and 'auth'
            data: The notification payload (string, dict, or bytes)
            ttl: Time to live in seconds
            
        Returns:
            bool: True if the notification was sent successfully
        """
        if self.disabled:
            logger.warning("WebPush service is disabled (py-vapid not available)")
            return False
        # Debug logging to see what we're getting
        logger.debug(f"Received subscription_info type: {type(subscription_info)}")
        logger.debug(f"Subscription_info content: {subscription_info}")
        
        # Handle case where subscription_info might be a string (JSON)
        if isinstance(subscription_info, str):
            try:
                subscription_info = json.loads(subscription_info)
                logger.debug(f"Parsed subscription_info from string: {subscription_info}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse subscription_info JSON: {e}")
                return False
        
        # Ensure subscription_info is a dictionary
        if not isinstance(subscription_info, dict):
            logger.error(f"subscription_info must be a dictionary, got {type(subscription_info)}")
            return False
        
        endpoint = subscription_info.get("endpoint")
        if not endpoint:
            logger.error(f"No endpoint provided in subscription info: {subscription_info}")
            return False
            
        # Parse the endpoint URL
        endpoint_url = urllib.parse.urlparse(endpoint)
        
        # Generate VAPID auth headers
        try:
            headers = {
                "TTL": str(ttl),
                "Content-Encoding": "aes128gcm",
            }
            
            # Add VAPID authentication
            vapid_headers = self.vapid.sign(endpoint, self.claims)
            headers.update(vapid_headers)
            
            # Encode the payload if provided
            payload = None
            if data:
                # Handle different subscription data structures
                keys = subscription_info.get("keys")
                if not keys:
                    logger.error(f"No keys found in subscription info: {subscription_info}")
                    return False
                
                auth_key = keys.get("auth")
                p256dh_key = keys.get("p256dh")
                
                if not auth_key or not p256dh_key:
                    logger.error(f"Missing auth or p256dh keys in subscription: {keys}")
                    return False
                
                try:
                    auth = base64.urlsafe_b64decode(auth_key)
                    p256dh = base64.urlsafe_b64decode(p256dh_key)
                except Exception as e:
                    logger.error(f"Failed to decode subscription keys: {e}")
                    return False
                
                raw_payload = self.encode_payload(data)
                payload = self._encrypt_payload(raw_payload, auth, p256dh)
                headers["Content-Type"] = "application/octet-stream"
                headers["Content-Length"] = str(len(payload))
            
            # Send the request
            conn = http.client.HTTPSConnection(endpoint_url.netloc)
            path = endpoint_url.path
            if endpoint_url.query:
                path = f"{path}?{endpoint_url.query}"
                
            conn.request("POST", path, body=payload, headers=headers)
            response = conn.getresponse()
            
            if response.status >= 400:
                logger.error(f"Push notification failed with status {response.status}: {response.read()}")
                raise WebPushException(
                    f"Push failed with status {response.status}", 
                    response=response
                )
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Failed to send push notification: {str(e)}")
            return False

# Example usage:
# service = ModernWebPushService(
#     vapid_private_key="your_base64_private_key",
#     vapid_claims={"sub": "mailto:admin@example.com"}
# )
# 
# service.send_notification(
#     subscription_info={
#         "endpoint": "https://fcm.googleapis.com/fcm/send/...",
#         "keys": {
#             "p256dh": "base64_p256dh_key",
#             "auth": "base64_auth_secret"
#         }
#     },
#     data={"title": "Hello", "body": "World"},
#     ttl=30
# )

# Global instance for backward compatibility  
# Initialized with empty defaults - will be configured later
webpush_service = None  # Will be initialized when needed
