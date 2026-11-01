"""Authentication dependencies for database-backed cookie sessions."""

from datetime import timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import sha256_token, utc_now
from app.db.session import get_db
from app.models import User, UserSession

settings = get_settings()


def get_optional_current_session(
    request: Request,
    db: Session = Depends(get_db),
) -> UserSession | None:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        return None
    record = db.query(UserSession).filter(UserSession.token_hash == sha256_token(raw_token)).one_or_none()
    if record is None or record.revoked_at is not None:
        return None
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utc_now():
        return None
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        return None
    return record


def get_current_session(
    session: UserSession | None = Depends(get_optional_current_session),
) -> UserSession:
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return session


def get_current_user(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user
