"""Encrypt proxy credentials after all schema migrations are complete."""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text

from app.database import engine


logger = logging.getLogger("streamvault")


def upgrade(target_engine=None):
    """Persist one stable key, then encrypt plaintext HTTP(S) proxy URLs."""
    target = target_engine or engine

    try:
        with target.begin() as connection:
            if target.dialect.name == "postgresql":
                connection.execute(
                    text("LOCK TABLE global_settings IN SHARE ROW EXCLUSIVE MODE")
                )

            settings_rows = connection.execute(
                text("SELECT id, proxy_encryption_key FROM global_settings ORDER BY id")
            ).all()
            proxy_rows = connection.execute(
                text("SELECT id, proxy_url FROM proxy_settings ORDER BY id")
            ).all()

            encrypted_rows = [
                row
                for row in proxy_rows
                if row.proxy_url
                and not row.proxy_url.startswith(("http://", "https://"))
            ]
            database_keys = {
                row.proxy_encryption_key
                for row in settings_rows
                if row.proxy_encryption_key is not None
            }
            if len(database_keys) > 1:
                raise SystemExit(
                    "Conflicting stored proxy encryption keys; refusing key rotation"
                )
            database_key = next(iter(database_keys), None)

            cipher = None
            selected_key = database_key
            if database_key is not None:
                try:
                    cipher = Fernet(database_key.encode("ascii"))
                except (TypeError, ValueError, UnicodeError):
                    raise SystemExit(
                        "Stored proxy encryption key is invalid; refusing key rotation"
                    ) from None
            else:
                legacy_key = os.getenv("PROXY_ENCRYPTION_KEY")
                if legacy_key is not None:
                    try:
                        cipher = Fernet(legacy_key.encode("ascii"))
                        selected_key = legacy_key
                    except (TypeError, ValueError, UnicodeError):
                        cipher = None

                if encrypted_rows and cipher is None:
                    raise SystemExit(
                        "Cannot recover proxy encryption key; refusing key rotation"
                    )

                if cipher is None:
                    selected_key = Fernet.generate_key().decode("ascii")
                    cipher = Fernet(selected_key.encode("ascii"))

            for row in encrypted_rows:
                try:
                    cipher.decrypt(row.proxy_url.encode("ascii"))
                except (InvalidToken, TypeError, ValueError, UnicodeError):
                    raise SystemExit(
                        "Cannot recover proxy encryption key; refusing key rotation"
                    ) from None

            if settings_rows:
                connection.execute(
                    text(
                        "UPDATE global_settings SET proxy_encryption_key = :key "
                        "WHERE proxy_encryption_key IS NULL"
                    ),
                    {"key": selected_key},
                )
            else:
                connection.execute(
                    text(
                        "INSERT INTO global_settings (proxy_encryption_key) "
                        "VALUES (:key)"
                    ),
                    {"key": selected_key},
                )

        encrypted_count = 0
        with target.begin() as connection:
            plaintext_rows = connection.execute(
                text(
                    "SELECT id, proxy_url FROM proxy_settings "
                    "WHERE proxy_url LIKE 'http://%' "
                    "OR proxy_url LIKE 'https://%' ORDER BY id"
                )
            ).all()
            for row in plaintext_rows:
                ciphertext = cipher.encrypt(row.proxy_url.encode("utf-8")).decode(
                    "ascii"
                )
                result = connection.execute(
                    text(
                        "UPDATE proxy_settings SET proxy_url = :ciphertext "
                        "WHERE id = :id AND proxy_url = :plaintext"
                    ),
                    {
                        "ciphertext": ciphertext,
                        "id": row.id,
                        "plaintext": row.proxy_url,
                    },
                )
                encrypted_count += result.rowcount

        logger.info(
            "Migration 041: Proxy encryption key persisted; encrypted %d proxy row(s)",
            encrypted_count,
        )
    except RuntimeError:
        logger.error("Migration 041: Proxy credential migration failed safely")
        raise
    except Exception:
        logger.error("Migration 041: Proxy credential database operation failed")
        raise RuntimeError(
            "Migration 041 failed during proxy credential migration"
        ) from None


def downgrade(target_engine=None):
    """Keep encrypted proxy credentials and their persisted key unchanged."""
    logger.info("Migration 041 downgrade: No changes made")
