from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.storage import LocalPrivateStorage, StorageError


def test_development_settings_allow_local_storage_and_http_origins() -> None:
    settings = Settings(
        _env_file=None,
        app_env=" DEVELOPMENT ",
        storage_backend="LOCAL",
        cors_origins="http://localhost:5173, http://localhost:8080/",
    )
    assert settings.app_env == "development"
    assert settings.storage_backend == "local"
    assert settings.cors_origin_list == ["http://localhost:5173", "http://localhost:8080"]


def test_production_settings_accept_explicit_secure_configuration() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        session_cookie_secure=True,
        storage_backend="s3",
        s3_bucket_name="private-trade-documents",
        database_url="postgresql+psycopg://trade_app:strong-password@db:5432/trade_prod",
        cors_origins="https://trade.example.com,https://admin.example.com",
    )
    assert settings.app_env == "production"
    assert settings.session_cookie_secure is True
    assert settings.storage_backend == "s3"


@pytest.mark.parametrize(
    "overrides, expected_message",
    [
        ({"session_cookie_secure": False}, "SESSION_COOKIE_SECURE"),
        ({"storage_backend": "local", "s3_bucket_name": None}, "STORAGE_BACKEND=s3"),
        ({"cors_origins": "*"}, "explicit HTTPS origins"),
        ({"cors_origins": "http://trade.example.com"}, "explicit HTTPS origins"),
        ({"cors_origins": "https://trade.example.com/private"}, "explicit HTTPS origins"),
        ({"database_url": "sqlite:///./local.db"}, "requires PostgreSQL"),
        ({"database_url": "postgresql+psycopg://change_me_local_only@db/trade"}, "configured PostgreSQL host"),
    ],
)
def test_production_settings_reject_insecure_or_development_configuration(overrides, expected_message) -> None:
    values = {
        "_env_file": None,
        "app_env": "production",
        "session_cookie_secure": True,
        "storage_backend": "s3",
        "s3_bucket_name": "private-trade-documents",
        "database_url": "postgresql+psycopg://trade_app:strong-password@db:5432/trade_prod",
        "cors_origins": "https://trade.example.com",
    }
    values.update(overrides)
    with pytest.raises(ValidationError, match=expected_message):
        Settings(**values)


def test_unknown_runtime_environment_is_rejected() -> None:
    with pytest.raises(ValidationError, match="APP_ENV must be"):
        Settings(_env_file=None, app_env="prod-ish")


def test_local_private_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalPrivateStorage(tmp_path / "private")
    with pytest.raises(StorageError, match="Invalid storage key"):
        storage.put("../outside.txt", b"do not write", "text/plain")
    assert not (tmp_path / "outside.txt").exists()


def test_local_private_storage_does_not_overwrite_existing_object(tmp_path: Path) -> None:
    storage = LocalPrivateStorage(tmp_path / "private")
    storage.put("org-a/document-1/version-1", b"first", "text/plain")
    with pytest.raises(StorageError, match="Private file write failed"):
        storage.put("org-a/document-1/version-1", b"replacement", "text/plain")
    assert storage.get("org-a/document-1/version-1") == b"first"


def test_local_private_storage_rejects_symlink_escape(tmp_path: Path) -> None:
    private_root = tmp_path / "private"
    outside_root = tmp_path / "outside"
    private_root.mkdir()
    outside_root.mkdir()
    (private_root / "escape").symlink_to(outside_root, target_is_directory=True)
    storage = LocalPrivateStorage(private_root)
    with pytest.raises(StorageError, match="Invalid storage key"):
        storage.put("escape/leaked.txt", b"must stay private", "text/plain")
    assert not (outside_root / "leaked.txt").exists()
