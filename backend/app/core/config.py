"""Centralized application configuration."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Settings loaded from environment variables and an optional root .env file."""

    app_name: str = "Importer & Exporter Management System"
    app_version: str = "1.0.0"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = (
        "postgresql+psycopg://import_export_dev:change_me_local_only"
        "@localhost:5432/import_export_dev"
    )
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    allow_self_registration: bool = True
    session_ttl_hours: int = Field(default=12, ge=1, le=168)
    session_cookie_secure: bool = False
    session_cookie_name: str = "iem_session"
    csrf_cookie_name: str = "iem_csrf"
    invitation_ttl_hours: int = Field(default=72, ge=1, le=720)
    private_storage_dir: str = ".private_storage"
    max_upload_bytes: int = Field(default=15 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    storage_backend: str = "local"
    s3_bucket_name: str | None = None
    s3_region: str = "eu-central-1"
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    automation_enabled: bool = True
    automation_poll_seconds: int = Field(default=60, ge=15, le=3600)

    model_config = SettingsConfigDict(
        env_file=str(ROOT_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return a normalized list from a comma-separated environment value."""
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> "Settings":
        """Normalize settings and reject deployment configurations known to be unsafe."""
        self.app_env = self.app_env.lower().strip()
        if self.app_env not in {"development", "test", "staging", "production"}:
            raise ValueError("APP_ENV must be development, test, staging, or production.")

        self.storage_backend = self.storage_backend.lower().strip()
        self.s3_bucket_name = self.s3_bucket_name.strip() if self.s3_bucket_name else None
        if self.storage_backend not in {"local", "s3"}:
            raise ValueError("STORAGE_BACKEND must be either 'local' or 's3'.")
        if self.storage_backend == "s3" and not self.s3_bucket_name:
            raise ValueError("S3_BUCKET_NAME is required when STORAGE_BACKEND=s3.")

        if self.app_env == "production":
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be true when APP_ENV=production.")
            if self.storage_backend != "s3" or not self.s3_bucket_name:
                raise ValueError("Production requires STORAGE_BACKEND=s3 and S3_BUCKET_NAME.")

            parsed_database_url = urlsplit(self.database_url)
            if parsed_database_url.scheme not in {"postgres", "postgresql", "postgresql+psycopg"}:
                raise ValueError("Production requires PostgreSQL; SQLite is development/test only.")
            if "change_me_local_only" in self.database_url or not parsed_database_url.hostname:
                raise ValueError("Production DATABASE_URL must contain a configured PostgreSQL host and credentials.")

            origins = self.cors_origin_list
            parsed_origins = [urlsplit(origin) for origin in origins]
            if not origins or any(
                origin == "*"
                or parsed.scheme != "https"
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                for origin, parsed in zip(origins, parsed_origins, strict=True)
            ):
                raise ValueError("Production CORS_ORIGINS must contain explicit HTTPS origins only; wildcards, paths, and HTTP are not allowed.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings for dependency injection and application startup."""
    return Settings()
