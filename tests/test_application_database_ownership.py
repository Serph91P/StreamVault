"""The real factory's auth read path must use its own configured database."""

from pathlib import Path
from http.cookies import SimpleCookie
from secrets import token_urlsafe

import httpx
import pytest
from pydantic import SecretStr

from app.config.settings import get_settings
from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.models import Category, User


@pytest.mark.asyncio
async def test_factory_auth_cookies_and_tokens_use_only_its_configuration(
    tmp_path: Path,
) -> None:
    configurations = [
        get_settings().model_copy(
            update={
                "database_url": SecretStr(f"sqlite:///{tmp_path / (name + '.db')}"),
                "auth_jwt_secret": SecretStr(token_urlsafe(48)),
                "AUTH_JWT_ISSUER": name,
                "USE_SECURE_COOKIES": secure,
                "RECORDING_DIRECTORY": str(tmp_path / name / "recordings"),
            }
        )
        for name, secure in (("cookie-first", False), ("cookie-second", True))
    ]
    applications = [create_app(settings=config) for config in configurations]
    lifecycles = [app.state.database_lifecycle for app in applications]
    credentials = {"username": "scope-admin", "password": token_urlsafe(32)}
    try:
        for lifecycle, config in zip(lifecycles, configurations, strict=True):
            with lifecycle.sync_engine.begin() as connection:
                Base.metadata.create_all(connection)
            with lifecycle.sync_session_factory() as session:
                session.add(
                    Category(
                        id=1, twitch_id="scope-category", name=config.AUTH_JWT_ISSUER
                    )
                )
                session.commit()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=applications[0]),
            base_url="https://localhost:8000",
        ) as first:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=applications[1]),
                base_url="https://localhost:8000",
            ) as second:
                for client, config in zip((first, second), configurations, strict=True):
                    setup = await client.post("/auth/setup", json=credentials)
                    assert setup.status_code == 200
                    cookies = SimpleCookie()
                    for header in setup.headers.get_list("set-cookie"):
                        cookies.load(header)
                    assert (
                        bool(cookies["session"]["secure"]) == config.USE_SECURE_COOKIES
                    )
                    login = await client.post("/auth/login", json=credentials)
                    assert login.status_code == 200
                    cookies = SimpleCookie()
                    for header in login.headers.get_list("set-cookie"):
                        cookies.load(header)
                    assert (
                        bool(cookies["access_token"]["secure"])
                        == config.USE_SECURE_COOKIES
                    )
                    assert (await client.get("/auth/check")).json() == {
                        "authenticated": True
                    }
                for client, config in zip((first, second), configurations, strict=True):
                    categories = await client.get("/api/categories")
                    assert categories.status_code == 200
                    assert [row["name"] for row in categories.json()["categories"]] == [
                        config.AUTH_JWT_ISSUER
                    ]
                assert (
                    await first.post(
                        "/api/categories/favorites", json={"category_id": 1}
                    )
                ).status_code == 200
                first_favorites = await first.get("/api/categories/favorites")
                second_favorites = await second.get("/api/categories/favorites")
                assert (
                    first_favorites.status_code == second_favorites.status_code == 200
                )
                assert [row["id"] for row in first_favorites.json()["categories"]] == [
                    1
                ]
                assert second_favorites.json() == {"categories": []}
                foreign = first.cookies.get("access_token")
                denied = await second.get(
                    "/auth/check", headers={"cookie": f"access_token={foreign}"}
                )
                assert denied.json() == {"authenticated": False}
                assert (await first.post("/auth/refresh")).status_code == 200
                assert (await second.post("/auth/refresh")).status_code == 200
                assert (await first.post("/auth/logout")).status_code == 200
                assert (await first.get("/auth/check")).json() == {
                    "authenticated": False
                }
                assert (await second.get("/auth/check")).json() == {
                    "authenticated": True
                }
    finally:
        for lifecycle in lifecycles:
            await lifecycle.adispose()


def test_factory_accepts_an_explicit_lazy_database_lifecycle() -> None:
    lifecycle = DatabaseLifecycle("sqlite:///:memory:")
    application = create_app(database=lifecycle)
    assert application.state.database_lifecycle is lifecycle
    assert lifecycle._sync_engine is None
    assert lifecycle._async_engine is None


@pytest.mark.asyncio
async def test_distinct_factories_keep_auth_database_state_separate(
    tmp_path: Path,
) -> None:
    configurations = [
        get_settings().model_copy(
            update={
                "database_url": SecretStr(f"sqlite:///{tmp_path / (name + '.db')}"),
                "RECORDING_DIRECTORY": str(tmp_path / name / "recordings"),
            }
        )
        for name in ("first", "second")
    ]
    applications = [create_app(settings=config) for config in configurations]
    lifecycles = [app.state.database_lifecycle for app in applications]
    assert all(isinstance(lifecycle, DatabaseLifecycle) for lifecycle in lifecycles)
    assert lifecycles[0] is not lifecycles[1]
    assert all(lifecycle._sync_engine is None for lifecycle in lifecycles)
    try:
        for lifecycle in lifecycles:
            with lifecycle.sync_engine.begin() as connection:
                Base.metadata.create_all(connection)
        with lifecycles[0].sync_session_factory() as session:
            session.add(
                User(username="scope-first", password="not-a-login", is_admin=True)
            )
            session.commit()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=applications[0]),
            base_url="http://localhost:8000",
        ) as first:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=applications[1]),
                base_url="http://localhost:8000",
            ) as second:
                first_status = await first.get("/auth/check")
                second_status = await second.get("/auth/check")
                first_protected = await first.get("/api/settings")
                second_protected = await second.get("/api/settings")
        assert first_protected.status_code == second_protected.status_code == 307
        assert first_protected.headers["location"] == "/auth/login"
        assert second_protected.headers["location"] == "/auth/setup"
        assert first_status.status_code == second_status.status_code == 200
        assert first_status.json() == {"authenticated": False}
        assert second_status.json() == {"setup_required": True}
        await lifecycles[0].adispose()
        with lifecycles[1].sync_session_factory() as session:
            assert session.query(User).count() == 0
    finally:
        for lifecycle in lifecycles:
            await lifecycle.adispose()
