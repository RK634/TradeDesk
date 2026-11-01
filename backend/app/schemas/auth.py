"""Pydantic contracts for authentication, organizations, and invitations."""

import re
from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserRole(str, Enum):
    ORGANIZATION_OWNER = "organization_owner"
    ADMINISTRATOR = "administrator"
    IMPORT_MANAGER = "import_manager"
    EXPORT_MANAGER = "export_manager"
    OPERATIONS_STAFF = "operations_staff"
    FINANCE_STAFF = "finance_staff"
    READ_ONLY = "read_only"


class InviteRole(str, Enum):
    ADMINISTRATOR = "administrator"
    IMPORT_MANAGER = "import_manager"
    EXPORT_MANAGER = "export_manager"
    OPERATIONS_STAFF = "operations_staff"
    FINANCE_STAFF = "finance_staff"
    READ_ONLY = "read_only"


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 320 or not _EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    return email


class RegisterRequest(BaseModel):
    email: str
    full_name: Annotated[str, Field(min_length=2, max_length=160)]
    password: Annotated[str, Field(min_length=12, max_length=128)]
    organization_name: Annotated[str, Field(min_length=2, max_length=160)]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("full_name", "organization_name")
    @classmethod
    def strip_required_names(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter at least 2 characters.")
        return value


class LoginRequest(BaseModel):
    email: str
    password: Annotated[str, Field(min_length=1, max_length=128)]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganizationMembershipOut(BaseModel):
    organization_id: UUID
    organization_name: str
    organization_slug: str
    membership_id: UUID
    role: UserRole
    is_active: bool


class AuthMeOut(BaseModel):
    user: UserOut
    organizations: list[OrganizationMembershipOut]


class AuthResultOut(AuthMeOut):
    csrf_token: str


class OrganizationCreateRequest(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=160)]

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Organization name must contain at least 2 characters.")
        return value


class MemberOut(BaseModel):
    membership_id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    joined_at: datetime


class MemberUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> "MemberUpdateRequest":
        if self.role is None and self.is_active is None:
            raise ValueError("Provide a role or is_active change.")
        return self


class InvitationCreateRequest(BaseModel):
    email: str
    role: InviteRole = InviteRole.READ_ONLY

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class InvitationCreatedOut(BaseModel):
    invitation_id: UUID
    email: str
    role: InviteRole
    invitation_token: str
    expires_at: datetime


class InvitationTokenRequest(BaseModel):
    token: Annotated[str, Field(min_length=32, max_length=256)]


class InvitationPreviewOut(BaseModel):
    email: str
    organization_name: str
    role: InviteRole
    expires_at: datetime
    user_exists: bool


class InvitationAcceptRequest(BaseModel):
    token: Annotated[str, Field(min_length=32, max_length=256)]
    full_name: Annotated[str, Field(min_length=2, max_length=160)] | None = None
    password: Annotated[str, Field(min_length=12, max_length=128)] | None = None

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter your full name.")
        return value
