"""link fare quotes to route snapshots

Revision ID: fc877ccd583a
Revises: 0004_maps_places_routes
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fc877ccd583a"
down_revision: str | None = "0004_maps_places_routes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep legacy rows nullable; every new non-test quote supplies this FK."""
    op.add_column("fare_quotes", sa.Column("route_snapshot_id", sa.String(32), nullable=True))
    op.create_foreign_key(
        "fk_fare_quotes_route_snapshot_id", "fare_quotes", "route_snapshots", ["route_snapshot_id"], ["id"]
    )
    op.create_index("ix_fare_quotes_route_snapshot_id", "fare_quotes", ["route_snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_fare_quotes_route_snapshot_id", table_name="fare_quotes")
    op.drop_constraint("fk_fare_quotes_route_snapshot_id", "fare_quotes", type_="foreignkey")
    op.drop_column("fare_quotes", "route_snapshot_id")
