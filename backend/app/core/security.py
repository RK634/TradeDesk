"""Password hashing, opaque session tokens, cookies, and CSRF validation."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User, UserSession

settings = get_settings()
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_session(db: Session, user: User, request: Request) -> tuple[UserSession, str, str]:
    """Create a session while persisting hashes only, never raw bearer tokens."""
    raw_session_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    user_agent = request.headers.get("user-agent")
    db_session = UserSession(
        user_id=user.id,
        token_hash=sha256_token(raw_session_token),
        csrf_token_hash=sha256_token(csrf_token),
        expires_at=utc_now() + timedelta(hours=settings.session_ttl_hours),
        user_agent=user_agent[:512] if user_agent else None,
    )
    db.add(db_session)
    return db_session, raw_session_token, csrf_token


def set_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.session_cookie_secure, httponly=True, samesite="lax")
    response.delete_cookie(settings.csrf_cookie_name, path="/", secure=settings.session_cookie_secure, httponly=False, samesite="lax")


def verify_csrf(request: Request, header_token: str | None, session: UserSession | None = None) -> None:
    """Validate double-submit CSRF for anonymous auth actions and session-bound CSRF otherwise."""
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed. Refresh the page and retry.")
    if session is not None and not hmac.compare_digest(sha256_token(header_token), session.csrf_token_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token expired. Refresh the page and retry.")


def verify_same_origin_if_present(request: Request) -> None:
    """Reject browser writes from a foreign Origin while allowing non-browser API clients."""
    origin = request.headers.get("origin")
    if not origin:
        return
    normalized = origin.rstrip("/")
    if normalized not in settings.cors_origin_list:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Request origin is not allowed.")
