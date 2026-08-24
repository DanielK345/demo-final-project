"""add isolated durable state for the LiveKit voice agent

Revision ID: 0005_livekit_voice_state
Revises: 0004_maps_places_routes
Create Date: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_livekit_voice_state"
down_revision: str | None = "0004_maps_places_routes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

J = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("ride_sessions") as batch_op:
        batch_op.add_column(sa.Column("voice_agent_state", J, nullable=True))
        batch_op.add_column(
            sa.Column(
                "voice_state_revision",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.create_check_constraint(
            "ck_ride_sessions_voice_state_revision_nonnegative",
            "voice_state_revision >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("ride_sessions") as batch_op:
        batch_op.drop_constraint(
            "ck_ride_sessions_voice_state_revision_nonnegative",
            type_="check",
        )
        batch_op.drop_column("voice_state_revision")
        batch_op.drop_column("voice_agent_state")
