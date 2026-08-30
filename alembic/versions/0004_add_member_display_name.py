"""Add a non-identifying demo display name for the Member-facing API.

Revision ID: 0004_add_member_display_name
Revises: 0003_add_operations_workflow
Create Date: 2026-08-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_add_member_display_name"
down_revision: Union[str, Sequence[str], None] = "0003_add_operations_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("display_name", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "display_name")
