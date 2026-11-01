"""Organization-scoped access and user administration endpoints."""

import secrets
from datetime import timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.config import get_settings
from app.core.normalization import organization_slug
from app.core.permissions import require_org_permission, validate_role_assignment
from app.core.security import sha256_token, utc_now, verify_csrf, verify_same_origin_if_present
from app.db.session import get_db
from app.models import Organization, OrganizationInvitation, OrganizationMembership, User, UserSession
from app.schemas.auth import (
    InviteRole,
    InvitationCreateRequest,
    InvitationCreatedOut,
    MemberOut,
    MemberUpdateRequest,
    OrganizationCreateRequest,
    OrganizationMembershipOut,
    UserRole,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])
settings = get_settings()


def organization_membership_out(membership: OrganizationMembership, organization: Organization) -> dict:
    return {
        "organization_id": organization.id,
        "organization_name": organization.name,
        "organization_slug": organization.slug,
        "membership_id": membership.id,
        "role": membership.role,
        "is_active": membership.is_active,
    }


def verify_mutation(request: Request, x_csrf_token: str | None, session: UserSession) -> None:
    verify_same_origin_if_present(request)
    verify_csrf(request, x_csrf_token, session)


@router.get("", response_model=list[OrganizationMembershipOut])
def list_organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .filter(OrganizationMembership.user_id == user.id, OrganizationMembership.is_active.is_(True))
        .order_by(Organization.name.asc())
        .all()
    )
    return [organization_membership_out(membership, organization) for membership, organization in rows]


@router.post("", response_model=OrganizationMembershipOut, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreateRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    verify_mutation(request, x_csrf_token, session)
    slug_base = organization_slug(payload.name)
    slug = slug_base
    suffix = 2
    while db.query(Organization.id).filter(Organization.slug == slug).first() is not None:
        slug = f"{slug_base[:170]}-{suffix}"
        suffix += 1
    organization = Organization(name=payload.name, slug=slug)
    try:
        db.add(organization)
        db.flush()
        membership = OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role=UserRole.ORGANIZATION_OWNER.value,
            is_active=True,
        )
        db.add(membership)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create organization due to a conflicting name or slug.") from exc
    return organization_membership_out(membership, organization)


@router.get("/{organization_id}/members", response_model=list[MemberOut])
def list_members(
    organization_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    require_org_permission(db, user.id, organization_id, "members.read")
    rows = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == organization_id)
        .order_by(User.full_name.asc(), User.email.asc())
        .all()
    )
    return [
        {
            "membership_id": membership.id,
            "user_id": member.id,
            "email": member.email,
            "full_name": member.full_name,
            "role": membership.role,
            "is_active": membership.is_active,
            "joined_at": membership.joined_at,
        }
        for membership, member in rows
    ]


@router.patch("/{organization_id}/members/{membership_id}", response_model=MemberOut)
def update_member(
    organization_id: UUID,
    membership_id: UUID,
    payload: MemberUpdateRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    verify_mutation(request, x_csrf_token, session)
    actor = require_org_permission(db, user.id, organization_id, "members.manage")
    target = db.query(OrganizationMembership).filter(
        OrganizationMembership.id == membership_id,
        OrganizationMembership.organization_id == organization_id,
    ).one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Member not found.")
    validate_role_assignment(actor.role, target.role, payload.role.value if payload.role else None)
    if target.user_id == user.id and payload.is_active is False:
        raise HTTPException(status_code=422, detail="You cannot deactivate your own membership.")
    if payload.role is not None:
        target.role = payload.role.value
    if payload.is_active is not None:
        target.is_active = payload.is_active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="The member update conflicts with existing data.") from exc
    member = db.get(User, target.user_id)
    return {
        "membership_id": target.id,
        "user_id": member.id,
        "email": member.email,
        "full_name": member.full_name,
        "role": target.role,
        "is_active": target.is_active,
        "joined_at": target.joined_at,
    }


@router.post("/{organization_id}/invitations", response_model=InvitationCreatedOut, status_code=status.HTTP_201_CREATED)
def create_invitation(
    organization_id: UUID,
    payload: InvitationCreateRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    verify_mutation(request, x_csrf_token, session)
    actor = require_org_permission(db, user.id, organization_id, "members.invite")
    if actor.role == "administrator" and payload.role == InviteRole.ADMINISTRATOR:
        raise HTTPException(status_code=403, detail="Only an organization owner can invite an administrator.")

    existing_user = db.query(User).filter(User.email == payload.email).one_or_none()
    if existing_user is not None:
        existing_membership = db.query(OrganizationMembership.id).filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == existing_user.id,
        ).first()
        if existing_membership:
            raise HTTPException(status_code=409, detail="This account already has a membership in the organization.")

    now = utc_now()
    pending = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.organization_id == organization_id,
        OrganizationInvitation.email == payload.email,
        OrganizationInvitation.accepted_at.is_(None),
        OrganizationInvitation.revoked_at.is_(None),
    ).all()
    if any(item.expires_at.replace(tzinfo=timezone.utc) > now if item.expires_at.tzinfo is None else item.expires_at > now for item in pending):
        raise HTTPException(status_code=409, detail="A pending invitation already exists for this email.")

    raw_token = secrets.token_urlsafe(48)
    invitation = OrganizationInvitation(
        organization_id=organization_id,
        email=payload.email,
        role=payload.role.value,
        token_hash=sha256_token(raw_token),
        invited_by_user_id=user.id,
        expires_at=now + timedelta(hours=settings.invitation_ttl_hours),
    )
    db.add(invitation)
    db.commit()
    # No mail provider is configured in Phase 3, so return the opaque token once to the authorized inviter.
    return {
        "invitation_id": invitation.id,
        "email": invitation.email,
        "role": invitation.role,
        "invitation_token": raw_token,
        "expires_at": invitation.expires_at,
    }


@router.delete("/{organization_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    organization_id: UUID,
    invitation_id: UUID,
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "members.invite")
    invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.id == invitation_id,
        OrganizationInvitation.organization_id == organization_id,
        OrganizationInvitation.accepted_at.is_(None),
        OrganizationInvitation.revoked_at.is_(None),
    ).one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="Pending invitation not found.")
    invitation.revoked_at = utc_now()
    db.commit()
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
