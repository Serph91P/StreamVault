import pytest


@pytest.mark.asyncio
async def test_lifespan_fails_startup_when_database_migrations_fail(monkeypatch):
    from app.main import lifespan
    from app.services.system.migration_service import MigrationService

    monkeypatch.setattr(
        MigrationService,
        "run_safe_migrations",
        staticmethod(lambda: False),
    )

    with pytest.raises(
        RuntimeError, match="Database migrations did not complete successfully"
    ):
        await lifespan(None).__aenter__()
