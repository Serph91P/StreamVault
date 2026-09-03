"""Regression contract for production Compose connectivity and health checks."""

from pathlib import Path


COMPOSE = Path("docker/docker-compose.yml")


def test_compose_uses_the_configured_postgres_password_and_live_healthcheck():
    compose = COMPOSE.read_text(encoding="utf-8")

    expected_database_url = (
        "DATABASE_URL=postgresql://${POSTGRES_USER}:${"
        "POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}"
    )
    assert expected_database_url in compose
    assert "http://localhost:7000/api/health/live" in compose
