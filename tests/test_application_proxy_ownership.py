"""Factory proxy owners do not inherit global databases, credentials or shutdown."""

import asyncio
from secrets import token_urlsafe

from cryptography.fernet import Fernet
from pydantic import SecretStr
import pytest

from app import dependencies
from app.models import GlobalSettings, ProxySettings
from app.services.system.migration_service import MigrationService
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_image_http_ownership, test_proxy_managed_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize("faulted_startup", [False, True])
async def test_factory_proxy_lifetime_is_owning_and_fault_cleanup_preserves_peer(
    image_applications, monkeypatch, faulted_startup
):
    applications, databases, _, _ = image_applications
    services = []
    async with test_proxy_managed_http_ownership.origin() as (url, seen, _, _):
        try:
            for index, (app, database) in enumerate(
                zip(applications, databases, strict=True)
            ):
                assert hasattr(app.state, "proxy_health_service")
                assert app.state.proxy_health_service is None
                app.state.settings.TWITCH_APP_ID = f"owner-{index}"
                app.state.settings.twitch_app_secret = SecretStr(token_urlsafe(24))
                with database.sync_session_factory() as session:
                    row = session.query(GlobalSettings).first()
                    if row is None:
                        row = GlobalSettings(
                            proxy_encryption_key=Fernet.generate_key().decode()
                        )
                        session.add(row)
                    elif not row.proxy_encryption_key:
                        row.proxy_encryption_key = Fernet.generate_key().decode()
                    session.flush()
                    from app.utils.proxy_encryption import get_proxy_encryption

                    get_proxy_encryption(session)
                    proxy = ProxySettings(id=1)
                    session.add(proxy)
                    proxy.proxy_url = url
                    session.commit()
                same = await asyncio.gather(
                    *(
                        run_in_thread_pool(
                            dependencies._get_application_proxy_health_service, app
                        )
                        for _ in range(3)
                    )
                )
                assert same[0] is same[1] is same[2]
                service = same[0]
                services.append(service)
                assert (
                    service._session_factory is database.sync_session_factory
                    or service._session_factory.kw["bind"] is database.sync_engine
                )
                assert service._settings is app.state.settings
                assert service._websocket_manager is app.state.websocket_manager
                service.token_endpoint = url + "/token"
                service.test_endpoint = "http://upstream.invalid/health"
                assert (await service.check_proxy_health_manual(1))[
                    "health_status"
                ] == "healthy"
                assert seen[-2][4]["client_id"] == f"owner-{index}"
            assert services[0] is not services[1]
            if faulted_startup:
                from app.lifespan import lifespan

                monkeypatch.setattr(
                    MigrationService,
                    "run_safe_migrations",
                    staticmethod(lambda *args, **kwargs: False),
                )
                with pytest.raises(
                    RuntimeError,
                    match="Database migrations did not complete successfully",
                ):
                    await lifespan(applications[0]).__aenter__()
            else:
                from app.lifespan import _close_application_proxy

                await _close_application_proxy(applications[0])
            assert applications[0].state.proxy_health_service is None
            assert services[0]._supervisor.closed
            assert services[0]._token_http._closed and not services[0]._proxy_clients
            assert not services[1]._supervisor.closed
            assert (await services[1].check_proxy_health_manual(1))[
                "health_status"
            ] == "healthy"
        finally:
            for service in services:
                await service.stop()
