"""Add hashed refresh-token family storage for JWT rotation."""

from sqlalchemy import inspect, text


def upgrade(engine):
    with engine.begin() as connection:
        user_columns = {
            column["name"] for column in inspect(connection).get_columns("users")
        }
        if "is_active" not in user_columns:
            connection.execute(
                text(
                    "ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
                )
            )
        connection.execute(
            text("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                family_id VARCHAR(64) NOT NULL, token_hash VARCHAR(64) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL, family_expires_at DATETIME NOT NULL,
                used_at DATETIME, revoked_at DATETIME, parent_token_hash VARCHAR(64),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_family_id ON refresh_tokens (family_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id)"
            )
        )


def downgrade(engine):
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS refresh_tokens"))
