from datetime import timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import sha256_token, utc_now
from app.models import OrganizationInvitation, OrganizationMembership, User, UserSession
from conftest import csrf_headers, register_account


def test_registration_creates_owner_org_hashed_password_and_session(client: TestClient, db_session: Session) -> None:
    result = register_account(client)
    assert result["user"]["email"] == "owner@example.com"
    assert result["organizations"][0]["role"] == "organization_owner"
    assert result["organizations"][0]["organization_name"] == "Northwind Trade"
    assert client.cookies.get("iem_session")
    user = db_session.query(User).filter_by(email="owner@example.com").one()
    assert user.password_hash != "correct-horse-battery-12"
    raw_session = client.cookies.get("iem_session")
    session = db_session.query(UserSession).filter_by(user_id=user.id).one()
    assert session.token_hash == sha256_token(raw_session)
    assert session.token_hash != raw_session


def test_duplicate_email_registration_is_rejected(client: TestClient) -> None:
    register_account(client)
    client.get("/api/v1/auth/csrf")
    response = client.post("/api/v1/auth/register", headers=csrf_headers(client), json={
        "email": "OWNER@example.com", "full_name": "Second Owner", "password": "another-correct-password",
        "organization_name": "Second Company",
    })
    assert response.status_code == 409


def test_login_me_and_logout_revoke_session(client: TestClient, db_session: Session) -> None:
    register_account(client)
    client.post("/api/v1/auth/logout", headers=csrf_headers(client), json={})
    assert client.get("/api/v1/auth/me").status_code == 401

    client.get("/api/v1/auth/csrf")
    response = client.post("/api/v1/auth/login", headers=csrf_headers(client), json={
        "email": "OWNER@example.com", "password": "correct-horse-battery-12",
    })
    assert response.status_code == 200, response.text
    assert response.json()["user"]["email"] == "owner@example.com"
    assert client.get("/api/v1/auth/me").status_code == 200
    logout = client.post("/api/v1/auth/logout", headers=csrf_headers(client), json={})
    assert logout.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    assert db_session.query(UserSession).filter(UserSession.revoked_at.is_not(None)).count() >= 1


def test_invalid_login_uses_generic_error(client: TestClient) -> None:
    client.get("/api/v1/auth/csrf")
    response = client.post("/api/v1/auth/login", headers=csrf_headers(client), json={
        "email": "missing@example.com", "password": "a-long-password-for-test",
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_mutation_requires_csrf(client: TestClient) -> None:
    register_account(client)
    response = client.post("/api/v1/organizations", json={"name": "Blocked Organization"})
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_user_cannot_access_another_organizations_members(client: TestClient) -> None:
    first = register_account(client, email="owner-one@example.com", organization="First Organization")
    first_org_id = first["organizations"][0]["organization_id"]
    other_client = TestClient(client.app)
    other = register_account(other_client, email="owner-two@example.com", organization="Second Organization")
    assert other["organizations"][0]["organization_id"] != first_org_id
    response = other_client.get(f"/api/v1/organizations/{first_org_id}/members")
    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found."


def test_owner_cannot_be_demoted_or_deactivated(client: TestClient) -> None:
    result = register_account(client)
    membership_id = result["organizations"][0]["membership_id"]
    organization_id = result["organizations"][0]["organization_id"]
    response = client.patch(
        f"/api/v1/organizations/{organization_id}/members/{membership_id}",
        headers=csrf_headers(client),
        json={"role": "read_only", "is_active": False},
    )
    assert response.status_code == 403
    assert "owner" in response.json()["detail"].lower()


def test_invitation_acceptance_creates_account_and_membership(client: TestClient, db_session: Session) -> None:
    owner_result = register_account(client)
    organization_id = owner_result["organizations"][0]["organization_id"]
    invite_response = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=csrf_headers(client),
        json={"email": "new-member@example.com", "role": "finance_staff"},
    )
    assert invite_response.status_code == 201, invite_response.text
    invite = invite_response.json()
    preview = client.post("/api/v1/auth/invitations/preview", headers=csrf_headers(client), json={"token": invite["invitation_token"]})
    assert preview.status_code == 200
    assert preview.json()["email"] == "new-member@example.com"

    # Anonymous invite acceptance only needs the double-submit token, so refresh CSRF explicitly.
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    accept = client.post(
        "/api/v1/auth/accept-invitation",
        headers={"X-CSRF-Token": csrf},
        json={"token": invite["invitation_token"], "full_name": "Finance Member", "password": "long-password-for-member-123"},
    )
    assert accept.status_code == 200, accept.text
    assert accept.json()["accepted"] is True
    assert accept.json()["user"]["email"] == "new-member@example.com"
    assert client.get("/api/v1/auth/me").json()["user"]["email"] == "new-member@example.com"
    member = db_session.query(User).filter_by(email="new-member@example.com").one()
    membership = db_session.query(OrganizationMembership).filter_by(user_id=member.id, organization_id=UUID(organization_id)).one()
    assert membership.role == "finance_staff"
    stored_invite = db_session.query(OrganizationInvitation).filter_by(id=UUID(invite["invitation_id"])).one()
    assert stored_invite.accepted_at is not None


def test_invitation_token_is_single_use(client: TestClient) -> None:
    owner_result = register_account(client)
    organization_id = owner_result["organizations"][0]["organization_id"]
    invite = client.post(f"/api/v1/organizations/{organization_id}/invitations", headers=csrf_headers(client), json={
        "email": "invitee@example.com", "role": "read_only",
    }).json()
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    first = client.post("/api/v1/auth/accept-invitation", headers={"X-CSRF-Token": csrf}, json={
        "token": invite["invitation_token"], "full_name": "Invitee Person", "password": "long-password-for-invitee-123",
    })
    assert first.status_code == 200
    again = client.post("/api/v1/auth/invitations/preview", headers=csrf_headers(client), json={"token": invite["invitation_token"]})
    assert again.status_code == 404


def test_invitation_expiry_is_enforced(client: TestClient, db_session: Session) -> None:
    owner_result = register_account(client)
    organization_id = owner_result["organizations"][0]["organization_id"]
    invite = client.post(f"/api/v1/organizations/{organization_id}/invitations", headers=csrf_headers(client), json={
        "email": "expired@example.com", "role": "read_only",
    }).json()
    invitation = db_session.query(OrganizationInvitation).filter_by(id=UUID(invite["invitation_id"])).one()
    invitation.expires_at = utc_now() - timedelta(minutes=1)
    db_session.commit()
    response = client.post("/api/v1/auth/invitations/preview", headers=csrf_headers(client), json={"token": invite["invitation_token"]})
    assert response.status_code == 410


def test_read_only_member_cannot_manage_or_list_members(client: TestClient) -> None:
    owner_result = register_account(client)
    organization_id = owner_result["organizations"][0]["organization_id"]
    invite = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=csrf_headers(client),
        json={"email": "reader@example.com", "role": "read_only"},
    ).json()

    member_client = TestClient(client.app)
    csrf = member_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    accepted = member_client.post(
        "/api/v1/auth/accept-invitation",
        headers={"X-CSRF-Token": csrf},
        json={"token": invite["invitation_token"], "full_name": "Report Reader", "password": "long-password-for-reader-123"},
    )
    assert accepted.status_code == 200, accepted.text
    denied = member_client.get(f"/api/v1/organizations/{organization_id}/members")
    assert denied.status_code == 403


def test_administrator_cannot_invite_another_administrator(client: TestClient) -> None:
    owner_result = register_account(client)
    organization_id = owner_result["organizations"][0]["organization_id"]
    invitation = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=csrf_headers(client),
        json={"email": "admin@example.com", "role": "administrator"},
    )
    assert invitation.status_code == 201, invitation.text

    admin_client = TestClient(client.app)
    csrf = admin_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    accepted = admin_client.post(
        "/api/v1/auth/accept-invitation",
        headers={"X-CSRF-Token": csrf},
        json={"token": invitation.json()["invitation_token"], "full_name": "Organization Admin", "password": "long-password-for-admin-1234"},
    )
    assert accepted.status_code == 200, accepted.text
    rejected = admin_client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=csrf_headers(admin_client),
        json={"email": "second-admin@example.com", "role": "administrator"},
    )
    assert rejected.status_code == 403
    assert "owner" in rejected.json()["detail"].lower()
