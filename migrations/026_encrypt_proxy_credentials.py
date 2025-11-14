"""
Migration 026: Encrypt Existing Proxy Credentials

SECURITY: Encrypts all existing proxy URLs in database.

Background:
Migration 025 created the proxy_settings table, but existing proxy URLs
are stored in plaintext. This migration encrypts them using Fernet encryption.

Note: This migration requires PROXY_ENCRYPTION_KEY environment variable.
If not set, a new key will be generated and logged (BACKUP THIS KEY!).

Author: StreamVault
Date: 2025-11-13
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal


def upgrade():
    """Encrypt existing proxy URLs in database"""
    with SessionLocal() as db:
        try:
            # Import encryption utility
            from app.utils.proxy_encryption import get_proxy_encryption
            encryption = get_proxy_encryption()
            
            # Get all existing proxies
            result = db.execute(text("SELECT id, proxy_url FROM proxy_settings;"))
            proxies = result.fetchall()
            
            if not proxies:
                print("ℹ️ No proxies to encrypt")
                db.commit()
                return
            
            encrypted_count = 0
            
            for proxy_id, proxy_url in proxies:
                # Check if already encrypted (encrypted strings are much longer and base64-encoded)
                if proxy_url and len(proxy_url) < 200 and proxy_url.startswith(('http://', 'https://')):
                    # This looks like plaintext - encrypt it
                    encrypted_url = encryption.encrypt(proxy_url)
                    
                    db.execute(
                        text("UPDATE proxy_settings SET proxy_url = :encrypted WHERE id = :id"),
                        {"encrypted": encrypted_url, "id": proxy_id}
                    )
                    
                    encrypted_count += 1
                    print(f"🔒 Encrypted proxy ID {proxy_id}: {proxy_url[:30]}...")
            
            db.commit()
            
            if encrypted_count > 0:
                print(f"✅ Migration 026: Encrypted {encrypted_count} proxy URL(s)")
                print("   IMPORTANT: Backup your PROXY_ENCRYPTION_KEY environment variable!")
            else:
                print("✅ Migration 026: All proxies already encrypted")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Migration 026 failed: {e}")
            print("   Make sure PROXY_ENCRYPTION_KEY is set in environment")
            raise


def downgrade():
    """Decrypt proxy URLs back to plaintext (NOT RECOMMENDED!)"""
    with SessionLocal() as db:
        try:
            from app.utils.proxy_encryption import get_proxy_encryption
            encryption = get_proxy_encryption()
            
            result = db.execute(text("SELECT id, proxy_url FROM proxy_settings;"))
            proxies = result.fetchall()
            
            if not proxies:
                print("ℹ️ No proxies to decrypt")
                db.commit()
                return
            
            decrypted_count = 0
            
            for proxy_id, proxy_url in proxies:
                # Try to decrypt (if it fails, it's already plaintext)
                try:
                    decrypted_url = encryption.decrypt(proxy_url)
                    
                    db.execute(
                        text("UPDATE proxy_settings SET proxy_url = :decrypted WHERE id = :id"),
                        {"decrypted": decrypted_url, "id": proxy_id}
                    )
                    
                    decrypted_count += 1
                    print(f"🔓 Decrypted proxy ID {proxy_id}")
                    
                except Exception:
                    # Already plaintext, skip
                    pass
            
            db.commit()
            print(f"✅ Migration 026 (downgrade): Decrypted {decrypted_count} proxy URL(s)")
            print("   ⚠️ WARNING: Proxy credentials are now stored in PLAINTEXT!")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Migration 026 downgrade failed: {e}")
            raise
