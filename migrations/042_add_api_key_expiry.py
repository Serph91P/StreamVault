"""Add optional API-key expiration without invalidating existing keys."""

from sqlalchemy import inspect, text


def upgrade(engine):
    with engine.begin() as connection:
        columns = {
            column["name"] for column in inspect(connection).get_columns("api_keys")
        }
        if "expires_at" not in columns:
            timestamp = (
                "TIMESTAMP WITH TIME ZONE"
                if connection.dialect.name == "postgresql"
                else "DATETIME"
            )
            connection.execute(
                text(f"ALTER TABLE api_keys ADD COLUMN expires_at {timestamp}")
            )


def downgrade(engine):
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        columns = {
            column["name"] for column in inspect(connection).get_columns("api_keys")
        }
        if "expires_at" in columns:
            connection.execute(text("ALTER TABLE api_keys DROP COLUMN expires_at"))
