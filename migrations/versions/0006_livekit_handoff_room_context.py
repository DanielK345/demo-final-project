"""persist LiveKit room binding and operator handoff context"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Keep the revision ID within Alembic's default alembic_version.version_num
# length (VARCHAR(32)). The original ID was 33 characters and could not be
# persisted after the DDL completed.
revision: str = "0006_livekit_handoff_context"
down_revision: str | None = "acc88dbc1e83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

J = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("handoffs", sa.Column("room_name", sa.String(length=128), nullable=True))
    op.add_column("handoffs", sa.Column("context_snapshot", J, nullable=True))
    op.add_column("handoffs", sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("handoffs", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("handoffs", "resolved_at")
    op.drop_column("handoffs", "connected_at")
    op.drop_column("handoffs", "context_snapshot")
    op.drop_column("handoffs", "room_name")
