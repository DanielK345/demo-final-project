"""add maps places and route_snapshots tables

Revision ID: 0004_maps_places_routes
Revises: 9e9b6f420a9a
Create Date: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_maps_places_routes"
down_revision: str | None = "9e9b6f420a9a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
J = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    # -- places table (§20) --
    op.create_table(
        "places",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_place_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("formatted_address", sa.Text(), nullable=False, server_default=""),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("types", J, nullable=False, server_default="[]"),
        sa.Column("serviceable", sa.Boolean(), nullable=True),
        sa.Column("service_area_id", sa.String(64), nullable=True),
        sa.Column("source_version", sa.String(64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "provider_place_id", name="uq_places_provider_place_id"),
    )
    op.create_index("ix_places_created_at", "places", ["created_at"])
    op.create_index("ix_places_serviceable", "places", ["serviceable"])

    # -- route_snapshots table (§21) --
    op.create_table(
        "route_snapshots",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("pickup_place_id", sa.String(32), sa.ForeignKey("places.id"), nullable=False),
        sa.Column("destination_place_id", sa.String(32), sa.ForeignKey("places.id"), nullable=False),
        sa.Column("distance_meters", sa.Numeric(12, 2), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(10, 2), nullable=False),
        sa.Column("geometry", J, nullable=True),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_version", sa.String(30), nullable=False, server_default=""),
        sa.Column("source_data_version", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_route_snapshots_pickup_place_id", "route_snapshots", ["pickup_place_id"])
    op.create_index("ix_route_snapshots_destination_place_id", "route_snapshots", ["destination_place_id"])
    if op.get_bind().dialect.name == "postgresql":
        bind = op.get_bind()
        data_api_roles = {
            row[0]
            for row in bind.execute(sa.text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')"))
        }
        for table in ("places", "route_snapshots"):
            op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))
            for role in data_api_roles:
                op.execute(sa.text(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"'))


def downgrade() -> None:
    op.drop_table("route_snapshots")
    op.drop_table("places")
