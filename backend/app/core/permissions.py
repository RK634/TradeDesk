"""Central role-to-permission mapping for backend authorization."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import ApprovalRule, OrganizationMembership

# Permission strings are stable contracts for subsequent feature modules.
_READ_PERMISSIONS = frozenset({
    "organization.read",
    "imports.read",
    "exports.read",
    "orders.read",
    "customers.read",
    "suppliers.read",
    "products.read",
    "inventory.read",
    "shipments.read",
    "documents.read",
    "invoices.read",
    "payments.read",
    "expenses.read",
    "tasks.read",
    "approvals.read",
    "notifications.read",
    "reports.read",
    "archive.read",
})

_BUSINESS_ADMIN_PERMISSIONS = frozenset({
    "imports.create", "imports.update", "imports.submit", "imports.approve", "imports.cancel", "imports.costs.update",
    "exports.create", "exports.update", "exports.submit", "exports.approve", "exports.cancel", "exports.dispatch", "exports.deliver",
    "orders.create", "orders.update", "orders.archive", "orders.restore",
    "customers.create", "customers.update",
    "suppliers.create", "suppliers.update",
    "products.create", "products.update",
    "inventory.receive", "inventory.dispatch", "inventory.reserve", "inventory.release_reservation", "inventory.adjust",
    "shipments.create", "shipments.update",
    "documents.upload", "documents.verify", "documents.delete",
    "invoices.create", "invoices.manage", "invoices.adjust",
    "payments.create", "payments.manage", "payments.reconcile", "payments.adjust",
    "expenses.create", "expenses.manage",
    "tasks.create", "tasks.update", "tasks.assign",
    "approvals.submit", "approvals.decide",
    "notifications.manage",
    "tasks.comment",
    "approvals.rules.manage",
    "reports.finance.read", "reports.export",
    "archive.manage",
    "settings.manage",
    "members.read", "members.invite", "members.manage",
})

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "organization_owner": _READ_PERMISSIONS | _BUSINESS_ADMIN_PERMISSIONS,
    # Administrator is broad but sensitive member-management rules below still prevent
    # managing owners or granting/removing Administrator privileges.
    "administrator": _READ_PERMISSIONS | _BUSINESS_ADMIN_PERMISSIONS,
    "import_manager": frozenset({
        "organization.read", "notifications.read", "imports.read", "imports.create", "imports.update", "imports.submit", "imports.costs.update",
        "orders.read", "customers.read", "suppliers.read", "products.read", "inventory.read", "inventory.receive",
        "shipments.read", "shipments.create", "shipments.update", "documents.read", "documents.upload", "tasks.read", "tasks.create", "tasks.update", "tasks.comment", "approvals.read", "approvals.submit",
    }),
    "export_manager": frozenset({
        "organization.read", "notifications.read", "exports.read", "exports.create", "exports.update", "exports.submit", "exports.dispatch", "exports.deliver",
        "orders.read", "customers.read", "products.read", "inventory.read",
        "shipments.read", "shipments.update", "documents.read", "documents.upload", "tasks.read", "tasks.create", "tasks.update", "tasks.comment", "approvals.read", "approvals.submit",
    }),
    "operations_staff": frozenset({
        "organization.read", "notifications.read", "imports.read", "exports.read", "exports.deliver", "orders.read", "shipments.read", "shipments.update",
        "documents.read", "documents.upload", "inventory.read", "inventory.receive",
        "inventory.dispatch", "tasks.read", "tasks.update", "tasks.comment", "approvals.read",
    }),
    "finance_staff": frozenset({
        "organization.read", "notifications.read", "orders.read", "customers.read", "suppliers.read", "imports.read", "exports.read",
        "invoices.read", "invoices.create", "invoices.manage",
        "payments.read", "payments.create", "payments.manage", "payments.reconcile", "payments.adjust", "invoices.adjust", "imports.costs.update",
        "expenses.read", "expenses.create", "expenses.manage", "reports.read", "tasks.read", "tasks.comment", "approvals.read", "approvals.submit", "approvals.decide",
        "reports.finance.read", "reports.export", "documents.read",
    }),
    "read_only": _READ_PERMISSIONS,
}


def require_org_permission(
    db: Session,
    user_id,
    organization_id,
    permission: str,
) -> OrganizationMembership:
    """Resolve membership in this organization and authorize the requested permission."""
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.is_active.is_(True),
    ).one_or_none()
    if membership is None:
        # Same public response for a missing membership and an inaccessible organization
        # reduces the ability to probe organization identifiers.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    allowed = permission in ROLE_PERMISSIONS.get(membership.role, frozenset())
    if not allowed and permission in {"approvals.decide", "imports.approve", "exports.approve"}:
        action = {"imports.approve": "import_order", "exports.approve": "export_order"}.get(permission)
        if action is None:
            # Generic approval permission is dynamically granted only for actions
            # where the organization's configured approval rule includes this role.
            action = None
        rules = db.query(ApprovalRule).filter(ApprovalRule.organization_id == organization_id, ApprovalRule.is_enabled.is_(True)).all()
        allowed = any(
            membership.role in (rule.required_roles or [])
            and (action is None or rule.business_action == action)
            for rule in rules
        )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to perform this action.")
    return membership


def validate_role_assignment(actor_role: str, target_role: str, requested_role: str | None) -> None:
    """Prevent privilege escalation and protect organization-owner memberships."""
    if target_role == "organization_owner":
        raise HTTPException(status_code=403, detail="Organization owner memberships cannot be changed here.")
    if requested_role is None:
        return
    if requested_role == "organization_owner":
        raise HTTPException(status_code=422, detail="The organization-owner role cannot be assigned through member management.")
    if actor_role == "administrator" and (target_role == "administrator" or requested_role == "administrator"):
        raise HTTPException(status_code=403, detail="Only an organization owner can manage administrator roles.")
