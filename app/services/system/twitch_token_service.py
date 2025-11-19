"""
Twitch OAuth Token Management Service

Handles automatic refresh of Twitch OAuth tokens to eliminate manual token copying.

Features:
- Automatic token refresh before expiration
- Secure storage of refresh tokens (encrypted)
- Fallback to environment variable (TWITCH_OAUTH_TOKEN)
- Compatible with Twitch Turbo (ad-free streams)

Flow:
1. User completes OAuth flow (one-time) → Store refresh_token
2. Before each recording → Check if access_token expired
3. If expired → Use refresh_token to get new access_token
4. Store new access_token and expiration timestamp
5. Recording uses fresh, valid token

Security:
- Refresh tokens encrypted like proxy passwords
- Access tokens never logged
- Tokens stored in database (persist across restarts)
"""

import logging
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models import GlobalSettings
from app.config.settings import get_settings
from app.utils.proxy_encryption import ProxyEncryption

logger = logging.getLogger("streamvault")


class TwitchTokenService:
    """Service for managing Twitch OAuth token refresh"""
    
    # Twitch OAuth endpoints
    TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
    
    # Token expiration buffer (refresh 1 hour before expiration)
    EXPIRATION_BUFFER_SECONDS = 3600
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.encryption = ProxyEncryption()
    
    async def get_valid_access_token(self) -> Optional[str]:
        """
        Get a valid Twitch OAuth access token.
        
        Returns either:
        1. Existing valid token from database
        2. Refreshed token (if expired)
        3. Token from environment variable (fallback)
        4. None (if no token available)
        
        Returns:
            Optional[str]: Valid access token or None
        """
        try:
            # === PRIORITY 1: Check database for stored tokens ===
            global_settings = self.db.query(GlobalSettings).first()
            
            if global_settings and global_settings.twitch_refresh_token:
                # Check if access token is still valid
                if self._is_token_valid(global_settings):
                    logger.debug("Using existing valid access token from database")
                    return self.settings.TWITCH_OAUTH_TOKEN
                
                # Token expired → Refresh it
                logger.info("Access token expired, refreshing...")
                new_access_token = await self._refresh_access_token(global_settings)
                if new_access_token:
                    return new_access_token
                
                logger.warning("Token refresh failed, falling back to environment variable")
            
            # === PRIORITY 2: Fallback to environment variable ===
            if self.settings.TWITCH_OAUTH_TOKEN:
                logger.debug("Using access token from environment variable (TWITCH_OAUTH_TOKEN)")
                return self.settings.TWITCH_OAUTH_TOKEN
            
            # === PRIORITY 3: No token available ===
            logger.warning("No Twitch OAuth token available. H.265/1440p quality unavailable.")
            return None
            
        except Exception as e:
            logger.error(f"Error getting valid access token: {e}")
            # Fallback to environment variable
            return self.settings.TWITCH_OAUTH_TOKEN
    
    def _is_token_valid(self, global_settings: GlobalSettings) -> bool:
        """
        Check if the stored access token is still valid (not expired).
        
        Args:
            global_settings: GlobalSettings object with token info
            
        Returns:
            bool: True if token is valid, False if expired or missing
        """
        if not global_settings.twitch_token_expires_at:
            return False
        
        # Add buffer time (refresh 1 hour before expiration)
        expires_with_buffer = global_settings.twitch_token_expires_at - timedelta(
            seconds=self.EXPIRATION_BUFFER_SECONDS
        )
        
        is_valid = datetime.utcnow() < expires_with_buffer
        
        if not is_valid:
            logger.debug(f"Token expired at {global_settings.twitch_token_expires_at}")
        
        return is_valid
    
    async def _refresh_access_token(self, global_settings: GlobalSettings) -> Optional[str]:
        """
        Refresh the Twitch OAuth access token using the stored refresh token.
        
        Args:
            global_settings: GlobalSettings object with refresh token
            
        Returns:
            Optional[str]: New access token or None on failure
        """
        try:
            # Decrypt refresh token
            refresh_token = self.encryption.decrypt(global_settings.twitch_refresh_token)
            
            if not refresh_token:
                logger.error("Failed to decrypt refresh token")
                return None
            
            # === STEP 1: Request new access token from Twitch ===
            payload = {
                "client_id": self.settings.TWITCH_CLIENT_ID,
                "client_secret": self.settings.TWITCH_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.TOKEN_URL, data=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Token refresh failed ({response.status}): {error_text}")
                        return None
                    
                    token_data = await response.json()
            
            # === STEP 2: Extract new tokens ===
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token")  # Twitch may rotate refresh token
            expires_in = token_data.get("expires_in", 14400)  # Default 4 hours
            
            if not new_access_token:
                logger.error("No access token in refresh response")
                return None
            
            # === STEP 3: Calculate expiration timestamp ===
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # === STEP 4: Update database ===
            # Update environment variable (used by recording service)
            self.settings.TWITCH_OAUTH_TOKEN = new_access_token
            
            # Update database
            global_settings.twitch_token_expires_at = expires_at
            
            # Update refresh token if Twitch rotated it
            if new_refresh_token and new_refresh_token != refresh_token:
                global_settings.twitch_refresh_token = self.encryption.encrypt(new_refresh_token)
                logger.info("Refresh token rotated by Twitch")
            
            self.db.commit()
            
            logger.info(f"✅ Access token refreshed successfully (expires at {expires_at})")
            return new_access_token
            
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            self.db.rollback()
            return None
    
    async def store_oauth_tokens(
        self, 
        access_token: str, 
        refresh_token: str, 
        expires_in: int = 14400
    ) -> bool:
        """
        Store OAuth tokens received from Twitch OAuth callback.
        
        This is called after user completes OAuth flow (one-time setup).
        
        Args:
            access_token: Short-lived access token (4-6 hours)
            refresh_token: Long-lived refresh token (months/years)
            expires_in: Access token lifetime in seconds
            
        Returns:
            bool: True if stored successfully, False otherwise
        """
        try:
            global_settings = self.db.query(GlobalSettings).first()
            
            if not global_settings:
                logger.error("GlobalSettings not found, cannot store tokens")
                return False
            
            # Calculate expiration timestamp
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Encrypt refresh token
            encrypted_refresh_token = self.encryption.encrypt(refresh_token)
            
            # Store in database
            global_settings.twitch_refresh_token = encrypted_refresh_token
            global_settings.twitch_token_expires_at = expires_at
            
            # Update environment variable (for immediate use)
            self.settings.TWITCH_OAUTH_TOKEN = access_token
            
            self.db.commit()
            
            logger.info(f"✅ OAuth tokens stored successfully (expires at {expires_at})")
            logger.info("🎯 Automatic token refresh enabled!")
            return True
            
        except Exception as e:
            logger.error(f"Error storing OAuth tokens: {e}")
            self.db.rollback()
            return False
    
    async def validate_token(self, access_token: str) -> Optional[dict]:
        """
        Validate an access token with Twitch API.
        
        Useful for checking token validity and getting user info.
        
        Args:
            access_token: Access token to validate
            
        Returns:
            Optional[dict]: Token validation response or None on failure
        """
        try:
            headers = {"Authorization": f"OAuth {access_token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.VALIDATE_URL, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"Token validation failed: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return None
    
    def clear_tokens(self) -> bool:
        """
        Clear stored OAuth tokens (user logout/disconnect).
        
        Returns:
            bool: True if cleared successfully
        """
        try:
            global_settings = self.db.query(GlobalSettings).first()
            
            if global_settings:
                global_settings.twitch_refresh_token = None
                global_settings.twitch_token_expires_at = None
                self.db.commit()
                
            # Clear environment variable
            self.settings.TWITCH_OAUTH_TOKEN = None
            
            logger.info("OAuth tokens cleared")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing tokens: {e}")
            self.db.rollback()
            return False
