"""Private storage adapters for local development and S3-compatible production buckets."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.config import Settings, get_settings


class StorageError(RuntimeError):
    """Raised when a private storage operation cannot be completed."""


class PrivateStorage(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalPrivateStorage:
    """Filesystem storage rooted outside frontend/static directories."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise StorageError("Invalid storage key.") from exc
        return candidate

    def put(self, key: str, content: bytes, content_type: str) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Resolve again after directory creation to detect a malicious symlink.
        path = self._resolve(key)
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except OSError as exc:
            raise StorageError("Private file write failed.") from exc

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise StorageError("Private file read failed.") from exc

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("Private file deletion failed.") from exc


class S3PrivateStorage:
    """S3-compatible object storage. No public ACL or public URL is ever created."""

    def __init__(self, *, bucket: str, region: str, endpoint_url: str | None, access_key: str | None, secret_key: str | None):
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - exercised in production image
            raise StorageError("S3 storage requires the boto3 dependency.") from exc
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
        )

    def put(self, key: str, content: bytes, content_type: str) -> None:
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type)
        except Exception as exc:  # boto3 provider-specific errors are normalized at this boundary
            raise StorageError("S3 object upload failed.") from exc

    def get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception as exc:
            # Let missing keys become FileNotFoundError to preserve API 404 behavior.
            code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if code in {"NoSuchKey", "404", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise StorageError("S3 object download failed.") from exc

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise StorageError("S3 object deletion failed.") from exc


def get_storage() -> PrivateStorage:
    """Create the configured storage adapter; local storage is the development default."""
    settings: Settings = get_settings()
    if settings.storage_backend == "s3":
        if not settings.s3_bucket_name:
            raise StorageError("S3_BUCKET_NAME must be configured when STORAGE_BACKEND=s3.")
        return S3PrivateStorage(
            bucket=settings.s3_bucket_name,
            region=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key_id,
            secret_key=settings.s3_secret_access_key,
        )
    return LocalPrivateStorage(settings.private_storage_dir)
