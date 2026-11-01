"""Initial migration baseline for the project foundation.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-30

This revision intentionally creates no business tables. Domain schema is added
in reviewed, feature-specific migrations beginning in later phases.
"""
from typing import Sequence, Union

from alembic import op  # noqa: F401 - retained as migration template convention
import sqlalchemy as sa  # noqa: F401 - retained as migration template convention

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Establish the first migration revision without application tables."""
    pass


def downgrade() -> None:
    """Remove the baseline revision (there are no application objects yet)."""
    pass
