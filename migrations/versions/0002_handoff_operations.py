"""add typed operational fields to human handoffs

Revision ID: 0002_handoff_operations
Revises: 0001_initial
Create Date: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_handoff_operations"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "handoffs",
        sa.Column("reason_code", sa.String(length=50), nullable=False, server_default="UNABLE_TO_CONTINUE"),
    )
    op.add_column("handoffs", sa.Column("priority", sa.Integer(), nullable=False, server_default="50"))
    op.add_column("handoffs", sa.Column("severity", sa.String(length=20), nullable=False, server_default="NORMAL"))
    op.add_column(
        "handoffs",
        sa.Column("queue", sa.String(length=50), nullable=False, server_default="GENERAL_OPERATOR"),
    )
    op.add_column(
        "handoffs",
        sa.Column("requires_immediate_transfer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("handoffs", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("handoffs", sa.Column("operator_id", sa.String(length=64), nullable=True))
    op.create_index("ix_handoffs_status_priority", "handoffs", ["status", "priority"])


def downgrade() -> None:
    op.drop_index("ix_handoffs_status_priority", table_name="handoffs")
    op.drop_column("handoffs", "operator_id")
    op.drop_column("handoffs", "accepted_at")
    op.drop_column("handoffs", "requires_immediate_transfer")
    op.drop_column("handoffs", "queue")
    op.drop_column("handoffs", "severity")
    op.drop_column("handoffs", "priority")
    op.drop_column("handoffs", "reason_code")
