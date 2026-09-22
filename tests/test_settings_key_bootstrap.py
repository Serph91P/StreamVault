from __future__ import annotations

import base64
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from urllib.parse import urlunsplit

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models import SystemConfig


def _synthetic_proxy_url() -> str:
    credentials = ":".join(("proxy-user", "proxy-secret"))
    return urlunsplit(("http", f"{credentials}@example.test:8080", "", "", ""))


def _settings(**overrides):
    from app.config.settings import Settings

    values = {
        "TWITCH_APP_ID": "test-client",
        "TWITCH_APP_SECRET": "twitch-secret-value",
        "BASE_URL": "https://streamvault.example.test",
        "DATABASE_URL": "postgresql://user:database-secret@example.test/streamvault",
        "POSTGRES_PASSWORD": "postgres-secret-value",
        "AUTH_JWT_SECRET": "jwt-secret-value-that-is-at-least-thirty-two-characters",
        "METRICS_AUTH_TOKEN": "metrics-secret-value",
        "TWITCH_OAUTH_TOKEN": "oauth-secret-value",
        "HTTP_PROXY": _synthetic_proxy_url(),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _failing_generator(message: str) -> Callable:
    def fail(*_args, **_kwargs):
        raise AssertionError(message)

    return fail


def test_settings_construction_is_pure_and_does_not_generate_identity(caplog) -> None:
    caplog.set_level(logging.DEBUG)

    settings = _settings(
        EVENTSUB_SECRET=None, VAPID_PUBLIC_KEY=None, VAPID_PRIVATE_KEY=None
    )

    assert settings.EVENTSUB_SECRET is None
    assert settings.get_vapid_keys() == {
        "public_key": None,
        "private_key": None,
        "claims_sub": "mailto:admin@streamvault.local",
    }
    assert caplog.records == []


def test_collection_defaults_are_isolated_and_use_factories() -> None:
    from app.config.settings import Settings

    first = _settings()
    second = _settings()

    first.APPRISE_URLS.append("json://example.invalid")
    assert second.APPRISE_URLS == []
    for field_name in (
        "APPRISE_URLS",
        "CORS_ALLOW_METHODS",
        "CORS_ALLOW_HEADERS",
        "TRUSTED_HOSTS",
        "TRUSTED_PROXY_CIDRS",
        "READINESS_REQUIRED_COMPONENTS",
    ):
        assert Settings.model_fields[field_name].default_factory is not None


def test_sensitive_configuration_is_redacted_from_repr_and_serialization() -> None:
    settings = _settings(
        EVENTSUB_SECRET="eventsub-secret-value",
        VAPID_PUBLIC_KEY="vapid-public-value",
        VAPID_PRIVATE_KEY="vapid-private-secret-value",
    )

    rendered = repr(settings) + settings.model_dump_json(by_alias=True)
    for secret in (
        "twitch-secret-value",
        "database-secret",
        "postgres-secret-value",
        "jwt-secret-value",
        "metrics-secret-value",
        "oauth-secret-value",
        "proxy-secret",
        "eventsub-secret-value",
        "vapid-private-secret-value",
    ):
        assert secret not in rendered

    # Compatibility access remains explicit for existing service integrations.
    assert settings.TWITCH_APP_SECRET == "twitch-secret-value"
    assert settings.EVENTSUB_SECRET == "eventsub-secret-value"


def test_validated_settings_preserve_runtime_compatibility_properties() -> None:
    settings = _settings(
        ENVIRONMENT="development",
        BASE_URL="https://streamvault.example.test/",
        WEBHOOK_URL="https://hooks.example.test/callback/",
        CORS_ADDITIONAL_ORIGINS="https://ui.example.test, http://localhost:9000",
        TRUSTED_HOSTS=["streamvault.example.test", "streamvault.example.test"],
        TRUSTED_PROXY_CIDRS=["10.0.0.0/8"],
        HTTPS_PROXY="socks5://proxy.example.test:1080",
    )

    assert settings.BASE_URL == "https://streamvault.example.test"
    assert settings.WEBHOOK_URL == "https://hooks.example.test/callback"
    assert "http://127.0.0.1:3000" in settings.allowed_origins
    assert "https://ui.example.test" in settings.allowed_origins
    assert settings.trusted_hosts == ["streamvault.example.test"]
    assert settings.is_trusted_proxy("10.2.3.4")
    assert not settings.is_trusted_proxy("not-an-ip")
    assert settings.environment_is_development
    assert settings.is_secure
    assert settings.domain == "streamvault.example.test"
    assert settings.DATABASE_URL == (
        "postgresql://user:database-secret@example.test/streamvault"
    )
    assert settings.POSTGRES_PASSWORD == "postgres-secret-value"
    assert settings.HTTP_PROXY == _synthetic_proxy_url()
    assert settings.HTTPS_PROXY == "socks5://proxy.example.test:1080"
    assert settings.AUTH_JWT_SECRET.startswith("jwt-secret-value")
    assert settings.METRICS_AUTH_TOKEN == "metrics-secret-value"

    settings.TWITCH_OAUTH_TOKEN = None
    settings.METRICS_AUTH_TOKEN = None
    assert settings.TWITCH_OAUTH_TOKEN is None
    assert settings.METRICS_AUTH_TOKEN is None

    production = _settings(HTTP_PROXY=None, HTTPS_PROXY=None)
    assert production.WEBHOOK_URL == production.BASE_URL
    assert production.trusted_hosts == ["streamvault.example.test"]
    assert not production.environment_is_development


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"BASE_URL": "not-a-url"}, "BASE_URL"),
        ({"WEBHOOK_URL": "ftp://example.test"}, "WEBHOOK_URL"),
        ({"EVENTSUB_PORT": 70_000}, "EVENTSUB_PORT"),
        ({"RECORDING_DIRECTORY": "relative/path"}, "RECORDING_DIRECTORY"),
        ({"AUTH_ACCESS_TOKEN_MINUTES": 0}, "AUTH_ACCESS_TOKEN_MINUTES"),
        (
            {"CORS_ADDITIONAL_ORIGINS": "https://good.example, javascript:alert(1)"},
            "CORS_ADDITIONAL_ORIGINS",
        ),
        ({"TRUSTED_PROXY_CIDRS": ["not-a-network"]}, "TRUSTED_PROXY_CIDRS"),
        ({"VAPID_PUBLIC_KEY": "only-one-half"}, "VAPID"),
        ({"BASE_URL": "https://user:password@example.test"}, "credentials"),
        ({"CORS_ADDITIONAL_ORIGINS": "https://example.test/path"}, "origin"),
        ({"HTTP_PROXY": "file:///tmp/proxy"}, "proxy URL"),
        (
            {"AUTH_REFRESH_TOKEN_HOURS": 48, "AUTH_REFRESH_FAMILY_MAX_HOURS": 24},
            "AUTH_REFRESH_FAMILY_MAX_HOURS",
        ),
        ({"AUTH_JWT_ALGORITHM": "none"}, "AUTH_JWT_ALGORITHM"),
    ],
)
def test_invalid_configuration_fails_fast_without_echoing_secrets(
    override: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError) as captured:
        _settings(**override)

    assert message in str(captured.value)
    assert "twitch-secret-value" not in str(captured.value)
    assert "database-secret" not in str(captured.value)


def test_vapid_generator_returns_a_valid_p256_identity() -> None:
    from app.services.system.persistent_key_service import generate_vapid_keys

    public_key, private_key = generate_vapid_keys()

    public_bytes = base64.urlsafe_b64decode(public_key + "==")
    private = serialization.load_der_private_key(base64.b64decode(private_key), None)
    assert len(public_bytes) == 65
    assert public_bytes[0] == 4
    assert isinstance(private, ec.EllipticCurvePrivateKey)
    assert private.key_size == 256


def test_bootstrap_persists_generated_keys_and_reuses_them_after_restart(
    tmp_path,
) -> None:
    from app.services.system.persistent_key_service import PersistentKeyBootstrapService

    engine = create_engine(f"sqlite:///{tmp_path / 'keys.sqlite'}")
    SystemConfig.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    calls = {"vapid": 0, "eventsub": 0}

    def generate_vapid() -> tuple[str, str]:
        calls["vapid"] += 1
        return "vapid-public-value", "vapid-private-value"

    def generate_eventsub() -> str:
        calls["eventsub"] += 1
        return "eventsub-persistent-value"

    first_settings = _settings(
        EVENTSUB_SECRET=None, VAPID_PUBLIC_KEY=None, VAPID_PRIVATE_KEY=None
    )
    material = PersistentKeyBootstrapService(
        sessions,
        vapid_key_generator=generate_vapid,
        eventsub_secret_generator=generate_eventsub,
    ).bootstrap(first_settings)

    assert material.eventsub_secret == "eventsub-persistent-value"
    assert first_settings.EVENTSUB_SECRET == "eventsub-persistent-value"
    assert first_settings.VAPID_PUBLIC_KEY == "vapid-public-value"
    assert first_settings.VAPID_PRIVATE_KEY == "vapid-private-value"

    restarted_settings = _settings(
        EVENTSUB_SECRET=None, VAPID_PUBLIC_KEY=None, VAPID_PRIVATE_KEY=None
    )
    restarted = PersistentKeyBootstrapService(
        sessions,
        vapid_key_generator=_failing_generator("VAPID identity was regenerated"),
        eventsub_secret_generator=_failing_generator(
            "EventSub identity was regenerated"
        ),
    ).bootstrap(restarted_settings)

    assert restarted == material
    assert restarted_settings.EVENTSUB_SECRET == material.eventsub_secret
    assert restarted_settings.VAPID_PRIVATE_KEY == material.vapid_private_key
    assert calls == {"vapid": 1, "eventsub": 1}

    with sessions() as session:
        stored = dict(
            session.execute(select(SystemConfig.key, SystemConfig.value)).all()
        )
    assert stored == {
        "eventsub_secret": "eventsub-persistent-value",
        "vapid_claims_sub": "mailto:admin@streamvault.local",
        "vapid_private_key": "vapid-private-value",
        "vapid_public_key": "vapid-public-value",
    }
    engine.dispose()


def test_bootstrap_uses_complete_environment_key_material_without_database_write(
    tmp_path,
) -> None:
    from app.services.system.persistent_key_service import PersistentKeyBootstrapService

    engine = create_engine(f"sqlite:///{tmp_path / 'configured.sqlite'}")
    SystemConfig.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    settings = _settings(
        EVENTSUB_SECRET="configured-eventsub",
        VAPID_PUBLIC_KEY="configured-public",
        VAPID_PRIVATE_KEY="configured-private",
    )

    material = PersistentKeyBootstrapService(
        sessions,
        vapid_key_generator=_failing_generator("must not generate VAPID keys"),
        eventsub_secret_generator=_failing_generator(
            "must not generate an EventSub secret"
        ),
    ).bootstrap(settings)

    assert material.eventsub_secret == "configured-eventsub"
    assert material.vapid_private_key == "configured-private"
    with sessions() as session:
        assert session.scalar(select(SystemConfig).limit(1)) is None
    engine.dispose()


def test_generation_failure_is_atomic(tmp_path) -> None:
    from app.services.system.persistent_key_service import (
        PersistentKeyBootstrapError,
        PersistentKeyBootstrapService,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'failure.sqlite'}")
    SystemConfig.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    settings = _settings(
        EVENTSUB_SECRET=None, VAPID_PUBLIC_KEY=None, VAPID_PRIVATE_KEY=None
    )

    with pytest.raises(PersistentKeyBootstrapError, match="VAPID"):
        PersistentKeyBootstrapService(
            sessions,
            vapid_key_generator=lambda: (None, None),
            eventsub_secret_generator=lambda: "must-not-be-stored",
        ).bootstrap(settings)

    assert settings.EVENTSUB_SECRET is None
    with sessions() as session:
        assert session.scalar(select(SystemConfig).limit(1)) is None
    engine.dispose()


def test_partial_stored_vapid_identity_is_replaced_atomically(tmp_path) -> None:
    from app.services.system.persistent_key_service import PersistentKeyBootstrapService

    engine = create_engine(f"sqlite:///{tmp_path / 'partial.sqlite'}")
    SystemConfig.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as session:
        session.add_all(
            [
                SystemConfig(key="eventsub_secret", value="stored-eventsub"),
                SystemConfig(key="vapid_public_key", value="stale-public"),
                SystemConfig(key="vapid_claims_sub", value="stale-claims"),
            ]
        )

    settings = _settings(
        EVENTSUB_SECRET=None, VAPID_PUBLIC_KEY=None, VAPID_PRIVATE_KEY=None
    )
    material = PersistentKeyBootstrapService(
        sessions,
        vapid_key_generator=lambda: ("replacement-public", "replacement-private"),
        eventsub_secret_generator=_failing_generator("must reuse EventSub identity"),
    ).bootstrap(settings)

    assert material.eventsub_secret == "stored-eventsub"
    assert material.vapid_public_key == "replacement-public"
    assert material.vapid_private_key == "replacement-private"
    assert material.vapid_claims_sub == "mailto:admin@streamvault.local"
    with sessions() as session:
        stored = dict(
            session.execute(select(SystemConfig.key, SystemConfig.value)).all()
        )
    assert stored["vapid_public_key"] == "replacement-public"
    assert stored["vapid_private_key"] == "replacement-private"
    assert stored["vapid_claims_sub"] == "mailto:admin@streamvault.local"
    engine.dispose()


def test_empty_eventsub_generation_rolls_back(tmp_path) -> None:
    from app.services.system.persistent_key_service import (
        PersistentKeyBootstrapError,
        PersistentKeyBootstrapService,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'empty-eventsub.sqlite'}")
    SystemConfig.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    with pytest.raises(PersistentKeyBootstrapError, match="EventSub"):
        PersistentKeyBootstrapService(
            sessions,
            vapid_key_generator=_failing_generator("must not generate VAPID keys"),
            eventsub_secret_generator=lambda: "",
        ).bootstrap(
            _settings(
                EVENTSUB_SECRET=None,
                VAPID_PUBLIC_KEY=None,
                VAPID_PRIVATE_KEY=None,
            )
        )

    with sessions() as session:
        assert session.scalar(select(SystemConfig).limit(1)) is None
    engine.dispose()


def test_database_outage_fails_closed_without_ephemeral_identity() -> None:
    from app.services.system.persistent_key_service import (
        PersistentKeyBootstrapError,
        PersistentKeyBootstrapService,
    )

    settings = _settings(
        EVENTSUB_SECRET=None, VAPID_PUBLIC_KEY=None, VAPID_PRIVATE_KEY=None
    )

    with pytest.raises(PersistentKeyBootstrapError, match="startup cannot continue"):
        PersistentKeyBootstrapService(
            _failing_generator("database unavailable"),
            vapid_key_generator=_failing_generator("must not generate VAPID keys"),
            eventsub_secret_generator=_failing_generator(
                "must not generate an EventSub secret"
            ),
        ).bootstrap(settings)

    assert settings.EVENTSUB_SECRET is None
    assert settings.VAPID_PRIVATE_KEY is None


def test_postgres_concurrent_first_starts_share_one_identity() -> None:
    from app.services.system.persistent_key_service import PersistentKeyBootstrapService

    url = os.environ.get("STREAMVAULT_POSTGRES_TEST_URL")
    if not url:
        pytest.skip("requires isolated STREAMVAULT_POSTGRES_TEST_URL")

    engine = create_engine(url, pool_pre_ping=True)
    SystemConfig.__table__.drop(engine, checkfirst=True)
    SystemConfig.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    calls = {"vapid": 0, "eventsub": 0}
    counter_lock = threading.Lock()

    def generate_vapid() -> tuple[str, str]:
        with counter_lock:
            calls["vapid"] += 1
        return "concurrent-public", "concurrent-private"

    def generate_eventsub() -> str:
        with counter_lock:
            calls["eventsub"] += 1
        return "concurrent-eventsub"

    def boot_once(_index: int):
        settings = _settings(
            EVENTSUB_SECRET=None, VAPID_PUBLIC_KEY=None, VAPID_PRIVATE_KEY=None
        )
        return PersistentKeyBootstrapService(
            sessions,
            vapid_key_generator=generate_vapid,
            eventsub_secret_generator=generate_eventsub,
        ).bootstrap(settings)

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            materials = list(executor.map(boot_once, range(4)))

        assert materials == [materials[0]] * 4
        assert calls == {"vapid": 1, "eventsub": 1}
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(SystemConfig)) == 4
    finally:
        SystemConfig.__table__.drop(engine, checkfirst=True)
        engine.dispose()


def test_lifespan_bootstraps_keys_immediately_after_migrations() -> None:
    import inspect

    from app import lifespan as lifespan_module

    source = inspect.getsource(lifespan_module.lifespan)
    migration = source.index("MigrationService.run_safe_migrations()")
    bootstrap = source.index("bootstrap_persistent_keys()")
    eventsub = source.index("initialize_eventsub()")

    assert migration < bootstrap < eventsub
