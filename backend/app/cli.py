"""Administrative bootstrap commands; passwords are read interactively, never from argv."""

import argparse
import getpass
import re
import sys

from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Organization, OrganizationMembership, User


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:160]
    return slug or "organization"


def create_owner(email: str, full_name: str, organization_name: str) -> int:
    normalized_email = email.strip().lower()
    full_name = full_name.strip()
    organization_name = organization_name.strip()
    password = getpass.getpass("Initial owner password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if len(password) < 12 or len(password) > 128:
        print("Password must contain between 12 and 128 characters.", file=sys.stderr)
        return 2
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized_email):
        print("A valid email address is required.", file=sys.stderr)
        return 2
    if len(full_name) < 2 or len(organization_name) < 2:
        print("Name and organization must each contain at least 2 characters.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        if db.query(User.id).filter(User.email == normalized_email).first():
            print("A user with this email already exists.", file=sys.stderr)
            return 2
        base_slug = _slugify(organization_name)
        slug = base_slug
        suffix = 2
        while db.query(Organization.id).filter(Organization.slug == slug).first():
            slug = f"{base_slug[:170]}-{suffix}"
            suffix += 1
        user = User(email=normalized_email, full_name=full_name, password_hash=hash_password(password), is_active=True)
        db.add(user)
        db.flush()
        organization = Organization(name=organization_name, slug=slug)
        db.add(organization)
        db.flush()
        db.add(OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="organization_owner",
            is_active=True,
        ))
        db.commit()
        print(f"Created organization owner {normalized_email!r} for {organization_name!r}.")
        print("Sign in using the frontend login page. The plaintext password was not stored or logged.")
        return 0
    except IntegrityError:
        db.rollback()
        print("The owner could not be created because a conflicting account or organization exists.", file=sys.stderr)
        return 2
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Importer & Exporter Management System administration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    owner_parser = subparsers.add_parser("create-owner", help="Create the first organization and its owner account")
    owner_parser.add_argument("--email", required=True)
    owner_parser.add_argument("--name", required=True, help="Owner's display name")
    owner_parser.add_argument("--organization", required=True, help="Organization name")
    args = parser.parse_args()
    if args.command == "create-owner":
        return create_owner(args.email, args.name, args.organization)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
