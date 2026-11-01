"""Registration, login, logout, CSRF, and invitation acceptance endpoints."""

import logging
import secrets
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user, get_optional_current_session
from app.core.config import get_settings
from app.core.normalization import organization_slug
from app.core.security import (
    clear_session_cookies,
    create_session,
    hash_password,
    set_session_cookies,
    sha256_token,
    utc_now,
    verify_csrf,
    verify_password,
    verify_same_origin_if_present,
)
from app.db.session import get_db
from app.models import Organization, OrganizationInvitation, OrganizationMembership, User, UserSession
from app.schemas.auth import (
    AuthMeOut,
    AuthResultOut,
    InvitationAcceptRequest,
    InvitationPreviewOut,
    InvitationTokenRequest,
    LoginRequest,
    RegisterRequest,
    UserRole,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()
logger = logging.getLogger(__name__)
# Perform a comparable Argon2 verification for unknown accounts to reduce email enumeration by timing.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-never-used-for-authentication")


def build_auth_payload(db: Session, user: User) -> dict:
    rows = (
        db.query(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .filter(OrganizationMembership.user_id == user.id, OrganizationMembership.is_active.is_(True))
        .order_by(Organization.name.asc())
        .all()
    )
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "created_at": user.created_at,
        },
        "organizations": [
            {
                "organization_id": membership.organization_id,
                "organization_name": organization.name,
                "organization_slug": organization.slug,
                "membership_id": membership.id,
                "role": membership.role,
                "is_active": membership.is_active,
            }
            for membership, organization in rows
        ],
    }


def build_invitation_payload(db: Session, invitation: OrganizationInvitation) -> dict:
    organization = db.get(Organization, invitation.organization_id)
    return {
        "email": invitation.email,
        "organization_name": organization.name if organization else "Unknown organization",
        "role": invitation.role,
        "expires_at": invitation.expires_at,
        "user_exists": db.query(User.id).filter(User.email == invitation.email).first() is not None,
    }


def active_invitation_or_404(db: Session, raw_token: str) -> OrganizationInvitation:
    invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == sha256_token(raw_token)
    ).one_or_none()
    if invitation is None or invitation.accepted_at is not None or invitation.revoked_at is not None:
        raise HTTPException(status_code=404, detail="Invitation is invalid or no longer available.")
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utc_now():
        raise HTTPException(status_code=410, detail="This invitation has expired. Ask an organization administrator for a new invitation.")
    return invitation


@router.get("/csrf", tags=["authentication"], summary="Issue or refresh a CSRF token")
def issue_csrf_token(
    response: Response,
    db: Session = Depends(get_db),
    session: UserSession | None = Depends(get_optional_current_session),
) -> dict[str, str]:
    """Issue a double-submit token for anonymous forms or rotate a session-bound token."""
    csrf_token = secrets.token_urlsafe(32)
    max_age = settings.session_ttl_hours * 3600
    if session is not None:
        session.csrf_token_hash = sha256_token(csrf_token)
        db.commit()
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return {"csrf_token": csrf_token}


@router.post("/register", response_model=AuthResultOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> dict:
    """Create the first user in an organization as its owner and start a session."""
    verify_same_origin_if_present(request)
    verify_csrf(request, x_csrf_token)
    if not settings.allow_self_registration:
        raise HTTPException(status_code=403, detail="Self-registration is disabled. Accept an organization invitation or contact an administrator.")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    organization_name = payload.organization_name
    slug_base = organization_slug(organization_name)
    slug = slug_base
    suffix = 2
    while db.query(Organization.id).filter(Organization.slug == slug).first() is not None:
        slug = f"{slug_base[:170]}-{suffix}"
        suffix += 1
    organization = Organization(name=organization_name, slug=slug)
    try:
        db.add(user)
        db.flush()
        db.add(organization)
        db.flush()
        db.add(OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=UserRole.ORGANIZATION_OWNER.value,
            is_active=True,
        ))
        db.flush()
        _, raw_session_token, csrf_token = create_session(db, user, request)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.info("Registration conflict", extra={"event": "auth.register.conflict"})
        raise HTTPException(status_code=409, detail="An account with this email may already exist, or organization details conflict.") from exc

    set_session_cookies(response, raw_session_token, csrf_token)
    return {**build_auth_payload(db, user), "csrf_token": csrf_token}


@router.post("/login", response_model=AuthResultOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: Session = Depends(get_db),
) -> dict:
    verify_same_origin_if_present(request)
    verify_csrf(request, x_csrf_token)
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if user is None:
        verify_password(payload.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    password_valid = verify_password(payload.password, user.password_hash)
    if not user.is_active or not password_valid:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not db.query(OrganizationMembership.id).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.is_active.is_(True),
    ).first():
        raise HTTPException(status_code=403, detail="This account has no active organization membership. Contact an administrator.")

    _, raw_session_token, csrf_token = create_session(db, user, request)
    db.commit()
    set_session_cookies(response, raw_session_token, csrf_token)
    logger.info("User session created", extra={"event": "auth.login.success", "user_id": str(user.id)})
    return {**build_auth_payload(db, user), "csrf_token": csrf_token}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    verify_same_origin_if_present(request)
    verify_csrf(request, x_csrf_token, session)
    session.revoked_at = utc_now()
    db.commit()
    clear_session_cookies(response)
    return {"success": True}


@router.get("/me", response_model=AuthMeOut)
def me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return build_auth_payload(db, user)


@router.post("/invitations/preview", response_model=InvitationPreviewOut)
def preview_invitation(
    payload: InvitationTokenRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    current_session: UserSession | None = Depends(get_optional_current_session),
    db: Session = Depends(get_db),
) -> dict:
    # Keep invitation tokens in POST bodies rather than request URLs, which are commonly logged.
    verify_same_origin_if_present(request)
    verify_csrf(request, x_csrf_token, current_session)
    invitation = active_invitation_or_404(db, payload.token)
    return build_invitation_payload(db, invitation)


@router.post("/accept-invitation")
def accept_invitation(
    payload: InvitationAcceptRequest,
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    current_session: UserSession | None = Depends(get_optional_current_session),
    db: Session = Depends(get_db),
) -> dict:
    """Accept a one-time invitation; new users receive a session, existing users must sign in."""
    verify_same_origin_if_present(request)
    invitation = active_invitation_or_404(db, payload.token)
    user = db.query(User).filter(User.email == invitation.email).one_or_none()
    created_user = user is None

    if user is not None:
        if current_session is None or current_session.user_id != user.id:
            raise HTTPException(status_code=401, detail="Sign in to the invited account before accepting this invitation.")
        verify_csrf(request, x_csrf_token, current_session)
    else:
        verify_csrf(request, x_csrf_token)
        if not payload.full_name or not payload.password:
            raise HTTPException(status_code=422, detail="full_name and a password of at least 12 characters are required for a new account.")
        user = User(email=invitation.email, full_name=payload.full_name, password_hash=hash_password(payload.password), is_active=True)
        db.add(user)
        db.flush()

    existing_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == invitation.organization_id,
        OrganizationMembership.user_id == user.id,
    ).one_or_none()
    if existing_membership is not None and existing_membership.is_active:
        raise HTTPException(status_code=409, detail="This account is already an active member of the organization.")
    if existing_membership is not None:
        existing_membership.role = invitation.role
        existing_membership.is_active = True
    else:
        db.add(OrganizationMembership(
            organization_id=invitation.organization_id,
            user_id=user.id,
            role=invitation.role,
            is_active=True,
        ))
    invitation.accepted_at = utc_now()

    session_data: tuple[UserSession, str, str] | None = None
    if created_user:
        session_data = create_session(db, user, request)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="The invitation could not be accepted because the account or membership already exists.") from exc

    if session_data is not None:
        _, raw_session_token, csrf_token = session_data
        set_session_cookies(response, raw_session_token, csrf_token)
        return {"accepted": True, **build_auth_payload(db, user), "csrf_token": csrf_token}
    return {"accepted": True, **build_auth_payload(db, user)}
