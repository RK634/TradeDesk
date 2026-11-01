"""Add users, organizations, memberships, sessions, and invitations.

Revision ID: 0002_auth_organizations
Revises: 0001_baseline
Create Date: 2026-10-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_auth_organizations"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_VALUES = "'organization_owner', 'administrator', 'import_manager', 'export_manager', 'operations_staff', 'finance_staff', 'read_only'"
INVITABLE_ROLE_VALUES = "'administrator', 'import_manager', 'export_manager', 'operations_staff', 'finance_staff', 'read_only'"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"role IN ({ROLE_VALUES})", name="ck_membership_role"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )
    op.create_index("ix_organization_memberships_organization_id", "organization_memberships", ["organization_id"], unique=False)
    op.create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"], unique=False)

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)
    op.create_index("ix_user_sessions_user_expiry", "user_sessions", ["user_id", "expires_at"], unique=False)

    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"role IN ({INVITABLE_ROLE_VALUES})", name="ck_invitation_role"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_organization_invitations_organization_id", "organization_invitations", ["organization_id"], unique=False)
    op.create_index("ix_organization_invitations_email", "organization_invitations", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_organization_invitations_email", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_organization_id", table_name="organization_invitations")
    op.drop_table("organization_invitations")
    op.drop_index("ix_user_sessions_user_expiry", table_name="user_sessions")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_organization_id", table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_table("organizations")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
