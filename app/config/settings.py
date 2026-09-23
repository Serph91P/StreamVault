from __future__ import annotations

import ipaddress
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _secret_value(value: SecretStr | None) -> str | None:
    return cast(str, value.get_secret_value()) if value is not None else None


def _validate_http_url(value: str, *, setting: str, origin_only: bool = False) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{setting} must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError(f"{setting} must not contain credentials")
    if origin_only and (
        parsed.path not in {"", "/"} or parsed.query or parsed.fragment
    ):
        raise ValueError(
            f"{setting} must contain an origin without path, query, or fragment"
        )
    return value.rstrip("/")


class Settings(BaseSettings):
    """Validated environment configuration without runtime I/O or key generation.

    Upper-case aliases preserve the existing deployment contract. Sensitive values
    are stored as ``SecretStr`` fields and are only unwrapped by explicit compatibility
    properties used by the service layer.
    """

    TWITCH_APP_ID: str
    twitch_app_secret: SecretStr = Field(alias="TWITCH_APP_SECRET")
    BASE_URL: str
    ENVIRONMENT: str = "production"
    WEBHOOK_URL: str | None = None
    database_url: SecretStr | None = Field(default=None, alias="DATABASE_URL")

    BASE_DIR: str = str(Path(__file__).parent.parent.parent.absolute())
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"
    LOGS_BASE_DIR: str | None = None
    LOG_DIR: str | None = None
    POSTGRES_USER: str | None = None
    postgres_password: SecretStr | None = Field(default=None, alias="POSTGRES_PASSWORD")
    POSTGRES_DB: str | None = None
    EVENTSUB_PORT: int = Field(default=8080, ge=1, le=65535)
    eventsub_secret: SecretStr | None = Field(default=None, alias="EVENTSUB_SECRET")
    APPRISE_URLS: list[str] = Field(default_factory=list)

    http_proxy: SecretStr | None = Field(default=None, alias="HTTP_PROXY")
    https_proxy: SecretStr | None = Field(default=None, alias="HTTPS_PROXY")
    twitch_oauth_token: SecretStr | None = Field(
        default=None, alias="TWITCH_OAUTH_TOKEN"
    )

    RECORDING_DIRECTORY: str = "/recordings"
    ARTWORK_BASE_PATH: str = "/recordings/.artwork"

    VAPID_PUBLIC_KEY: str | None = None
    vapid_private_key: SecretStr | None = Field(default=None, alias="VAPID_PRIVATE_KEY")
    VAPID_CLAIMS_SUB: str = "mailto:admin@streamvault.local"

    SECURE_COOKIES: bool = True
    USE_SECURE_COOKIES: bool = True
    auth_jwt_secret: SecretStr | None = Field(default=None, alias="AUTH_JWT_SECRET")
    AUTH_JWT_ALGORITHM: str = "HS256"
    AUTH_JWT_ISSUER: str = "streamvault"
    AUTH_JWT_AUDIENCE: str = "streamvault-api"
    AUTH_ACCESS_TOKEN_MINUTES: int = Field(default=15, ge=1)
    AUTH_REFRESH_TOKEN_HOURS: int = Field(default=24, ge=1)
    AUTH_REFRESH_FAMILY_MAX_HOURS: int = Field(default=168, ge=1)

    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    )
    CORS_ALLOW_HEADERS: list[str] = Field(
        default_factory=lambda: [
            "Content-Type",
            "Authorization",
            "X-Requested-With",
            "Accept",
            "Origin",
        ]
    )
    CORS_MAX_AGE: int = Field(default=86400, ge=0)
    CORS_ADDITIONAL_ORIGINS: str = ""
    TRUSTED_HOSTS: Annotated[list[str], NoDecode] = Field(default_factory=list)
    TRUSTED_PROXY_CIDRS: Annotated[list[str], NoDecode] = Field(default_factory=list)

    SECURE_HEADERS_ENABLED: bool = True
    HSTS_MAX_AGE: int = Field(default=31536000, ge=0)
    CONTENT_SECURITY_POLICY: str | None = None

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_CAPACITY: int = Field(default=300, ge=1)
    RATE_LIMIT_REFILL_PER_SEC: float = Field(default=5.0, gt=0)
    RATE_LIMIT_MAX_WAIT_MS: int = Field(default=500, ge=0)
    RATE_LIMIT_MAX_BUCKETS: int = Field(default=10000, ge=1)

    METRICS_ENABLED: bool = False
    metrics_auth_token: SecretStr | None = Field(
        default=None, alias="METRICS_AUTH_TOKEN"
    )
    METRICS_ALLOW_UNAUTHENTICATED: bool = False
    READINESS_TIMEOUT_SECONDS: float = Field(default=3.0, gt=0)
    READINESS_REQUIRED_COMPONENTS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["database", "ffmpeg", "streamlink"]
    )

    @field_validator(
        "TRUSTED_HOSTS",
        "TRUSTED_PROXY_CIDRS",
        "READINESS_REQUIRED_COMPONENTS",
        mode="before",
    )
    @classmethod
    def _split_list_settings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("BASE_URL")
    @classmethod
    def _validate_base_url(cls, value: str) -> str:
        return _validate_http_url(value, setting="BASE_URL")

    @field_validator("WEBHOOK_URL")
    @classmethod
    def _validate_webhook_url(cls, value: str | None) -> str | None:
        return (
            _validate_http_url(value, setting="WEBHOOK_URL")
            if value is not None
            else None
        )

    @field_validator("RECORDING_DIRECTORY", "ARTWORK_BASE_PATH", "BASE_DIR")
    @classmethod
    def _validate_absolute_directory(cls, value: str, info) -> str:
        if not Path(value).is_absolute():
            raise ValueError(f"{info.field_name} must be an absolute path")
        return value

    @field_validator("CORS_ADDITIONAL_ORIGINS")
    @classmethod
    def _validate_additional_origins(cls, value: str) -> str:
        for origin in (item.strip() for item in value.split(",") if item.strip()):
            _validate_http_url(
                origin, setting="CORS_ADDITIONAL_ORIGINS", origin_only=True
            )
        return value

    @field_validator("TRUSTED_PROXY_CIDRS")
    @classmethod
    def _validate_proxy_networks(cls, value: list[str]) -> list[str]:
        for network in value:
            try:
                ipaddress.ip_network(network, strict=False)
            except ValueError as error:
                raise ValueError(
                    f"TRUSTED_PROXY_CIDRS contains invalid network: {network}"
                ) from error
        return value

    @field_validator("http_proxy", "https_proxy")
    @classmethod
    def _validate_proxy_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        raw = value.get_secret_value()
        parsed = urlparse(raw)
        if (
            parsed.scheme not in {"http", "https", "socks4", "socks5"}
            or not parsed.hostname
        ):
            raise ValueError("proxy URL must use http, https, socks4, or socks5")
        return value

    @field_validator("auth_jwt_secret")
    @classmethod
    def _validate_explicit_jwt_secret(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("AUTH_JWT_SECRET must be at least 32 characters")
        return value

    @model_validator(mode="after")
    def _validate_related_settings(self) -> Settings:
        if self.WEBHOOK_URL is None:
            object.__setattr__(self, "WEBHOOK_URL", self.BASE_URL)
        if bool(self.VAPID_PUBLIC_KEY) != bool(self.vapid_private_key):
            raise ValueError(
                "VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY must be configured together"
            )
        if self.AUTH_REFRESH_FAMILY_MAX_HOURS < self.AUTH_REFRESH_TOKEN_HOURS:
            raise ValueError(
                "AUTH_REFRESH_FAMILY_MAX_HOURS must be at least AUTH_REFRESH_TOKEN_HOURS"
            )
        if self.AUTH_JWT_ALGORITHM != "HS256":
            raise ValueError("AUTH_JWT_ALGORITHM must be HS256")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        parsed_url = urlparse(self.BASE_URL)
        origins = {f"{parsed_url.scheme}://{parsed_url.netloc}"}
        if self.environment_is_development:
            origins.update(
                {
                    "http://localhost:5173",
                    "http://localhost:3000",
                    "http://localhost:7000",
                    "http://127.0.0.1:5173",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:7000",
                }
            )
        origins.update(
            origin.strip()
            for origin in self.CORS_ADDITIONAL_ORIGINS.split(",")
            if origin.strip()
        )
        return sorted(origins)

    @property
    def trusted_hosts(self) -> list[str]:
        if self.TRUSTED_HOSTS:
            return sorted(set(self.TRUSTED_HOSTS))
        if self.environment_is_development:
            return sorted({self.domain, "localhost", "127.0.0.1", "testserver"})
        return [self.domain]

    def is_trusted_proxy(self, client_ip: str) -> bool:
        try:
            address = ipaddress.ip_address(client_ip)
            return any(
                address in ipaddress.ip_network(network, strict=False)
                for network in self.TRUSTED_PROXY_CIDRS
            )
        except ValueError:
            return False

    @property
    def environment_is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"

    @property
    def has_push_notifications_configured(self) -> bool:
        return bool(self.VAPID_PUBLIC_KEY and self.vapid_private_key)

    @property
    def is_secure(self) -> bool:
        return self.BASE_URL.startswith("https://")

    @property
    def domain(self) -> str:
        return urlparse(self.BASE_URL).hostname or "localhost"

    def get_vapid_keys(self) -> dict[str, str | None]:
        """Return already-bootstrapped key material without performing I/O."""
        return {
            "public_key": self.VAPID_PUBLIC_KEY,
            "private_key": self.VAPID_PRIVATE_KEY,
            "claims_sub": self.VAPID_CLAIMS_SUB,
        }

    def apply_persistent_keys(
        self,
        *,
        eventsub_secret: str,
        vapid_public_key: str,
        vapid_private_key: str,
        jwt_secret: str,
    ) -> None:
        """Apply material resolved by the explicit post-migration bootstrap."""
        object.__setattr__(self, "eventsub_secret", SecretStr(eventsub_secret))
        object.__setattr__(self, "VAPID_PUBLIC_KEY", vapid_public_key)
        object.__setattr__(self, "vapid_private_key", SecretStr(vapid_private_key))
        object.__setattr__(self, "auth_jwt_secret", SecretStr(jwt_secret))

    @property
    def TWITCH_APP_SECRET(self) -> str:
        return cast(str, self.twitch_app_secret.get_secret_value())

    @property
    def DATABASE_URL(self) -> str | None:
        return _secret_value(self.database_url)

    @property
    def POSTGRES_PASSWORD(self) -> str | None:
        return _secret_value(self.postgres_password)

    @property
    def EVENTSUB_SECRET(self) -> str | None:
        return _secret_value(self.eventsub_secret)

    @property
    def HTTP_PROXY(self) -> str | None:
        return _secret_value(self.http_proxy)

    @property
    def HTTPS_PROXY(self) -> str | None:
        return _secret_value(self.https_proxy)

    @property
    def TWITCH_OAUTH_TOKEN(self) -> str | None:
        return _secret_value(self.twitch_oauth_token)

    @TWITCH_OAUTH_TOKEN.setter
    def TWITCH_OAUTH_TOKEN(self, value: str | None) -> None:
        object.__setattr__(
            self, "twitch_oauth_token", SecretStr(value) if value is not None else None
        )

    @property
    def VAPID_PRIVATE_KEY(self) -> str | None:
        return _secret_value(self.vapid_private_key)

    @property
    def AUTH_JWT_SECRET(self) -> str:
        return _secret_value(self.auth_jwt_secret) or ""

    @property
    def METRICS_AUTH_TOKEN(self) -> str | None:
        return _secret_value(self.metrics_auth_token)

    @METRICS_AUTH_TOKEN.setter
    def METRICS_AUTH_TOKEN(self, value: str | None) -> None:
        object.__setattr__(
            self, "metrics_auth_token", SecretStr(value) if value is not None else None
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Compatibility export. Construction now only validates configuration; persistent
# identities are resolved explicitly by the post-migration bootstrap service.
settings = get_settings()
