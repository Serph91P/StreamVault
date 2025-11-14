"""
Proxy Credential Encryption Utility

Provides encryption/decryption for sensitive proxy credentials stored in database.
Uses Fernet symmetric encryption from cryptography library.

SECURITY: Proxy URLs contain sensitive credentials (username, password).
These MUST be encrypted in database to prevent exposure in case of database compromise.

Encryption Key:
- Stored in environment variable PROXY_ENCRYPTION_KEY
- Generated once at first use and must be backed up
- If key is lost, existing proxies cannot be decrypted
"""

import os
import logging
from typing import Optional
from cryptography.fernet import Fernet

logger = logging.getLogger('streamvault')


class ProxyEncryption:
    """
    Handles encryption/decryption of proxy credentials.
    
    Uses Fernet symmetric encryption (AES-128 CBC with HMAC).
    """
    
    def __init__(self):
        self._cipher = None
        self._initialize_cipher()
    
    def _initialize_cipher(self):
        """Initialize Fernet cipher with encryption key from environment"""
        encryption_key = os.getenv('PROXY_ENCRYPTION_KEY')
        
        if not encryption_key:
            logger.warning("⚠️ PROXY_ENCRYPTION_KEY not set! Generating new key...")
            logger.warning("⚠️ IMPORTANT: Backup this key! If lost, proxies cannot be decrypted.")
            
            # Generate new key
            new_key = Fernet.generate_key()
            encryption_key = new_key.decode('utf-8')
            
            logger.warning("=" * 80)
            logger.warning("🔑 PROXY ENCRYPTION KEY (BACKUP THIS!):")
            logger.warning(f"   {encryption_key}")
            logger.warning("")
            logger.warning("Add to your .env file:")
            logger.warning(f"   PROXY_ENCRYPTION_KEY={encryption_key}")
            logger.warning("=" * 80)
        
        try:
            self._cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            logger.info("✅ Proxy encryption initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize proxy encryption: {e}")
            raise
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt proxy URL with credentials.
        
        Args:
            plaintext: Proxy URL (e.g., "http://user:pass@host:port")
        
        Returns:
            Encrypted string (base64 encoded)
        """
        if not plaintext:
            return plaintext
        
        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode('utf-8'))
            encrypted_str = encrypted_bytes.decode('utf-8')
            
            logger.debug(f"🔒 Encrypted proxy URL: {plaintext[:20]}... → {encrypted_str[:20]}...")
            return encrypted_str
            
        except Exception as e:
            logger.error(f"❌ Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt proxy URL to retrieve credentials.
        
        Args:
            encrypted: Encrypted proxy URL (base64 encoded)
        
        Returns:
            Decrypted proxy URL with credentials
        """
        if not encrypted:
            return encrypted
        
        try:
            decrypted_bytes = self._cipher.decrypt(encrypted.encode('utf-8'))
            decrypted_str = decrypted_bytes.decode('utf-8')
            
            logger.debug(f"🔓 Decrypted proxy URL: {encrypted[:20]}... → {decrypted_str[:20]}...")
            return decrypted_str
            
        except Exception as e:
            logger.error(f"❌ Decryption failed: {e}")
            logger.error("   This may indicate:")
            logger.error("   - Wrong encryption key in PROXY_ENCRYPTION_KEY")
            logger.error("   - Corrupted database entry")
            logger.error("   - Proxy was encrypted with different key")
            raise


# Singleton instance
_proxy_encryption = None


def get_proxy_encryption() -> ProxyEncryption:
    """Get singleton instance of ProxyEncryption"""
    global _proxy_encryption
    if _proxy_encryption is None:
        _proxy_encryption = ProxyEncryption()
    return _proxy_encryption
