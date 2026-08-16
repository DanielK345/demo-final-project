"""initial schema — users, auth_tokens, ride_sessions, bookings, trips, handoffs,
calls, conversation_events

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="CUSTOMER"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    op.create_table(
        "ride_sessions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("call_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("intent", sa.String(length=50), nullable=True),
        sa.Column("pickup", sa.JSON(), nullable=True),
        sa.Column("destination", sa.JSON(), nullable=True),
        sa.Column("vehicle_type", sa.String(length=20), nullable=True, server_default="4_SEAT"),
        sa.Column("confirmation_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        # Soft-reference (không FK cứng) — xem ghi chú trong src/backend/db/models.py
        sa.Column("booking_id", sa.String(length=32), nullable=True),
        sa.Column("handoff_triggered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("current_workflow", sa.String(length=50), nullable=True),
        sa.Column("current_step", sa.String(length=30), nullable=True, server_default="START"),
        sa.Column("end_reason", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ride_sessions_user_id", "ride_sessions", ["user_id"])

    op.create_table(
        "auth_tokens",
        sa.Column("token", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
    op.create_index("ix_auth_tokens_expires_at", "auth_tokens", ["expires_at"])

    op.create_table(
        "bookings",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("ride_sessions.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True, unique=True),
        sa.Column("pickup", sa.JSON(), nullable=True),
        sa.Column("destination", sa.JSON(), nullable=True),
        sa.Column("vehicle_type", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="SEARCHING_DRIVER"),
        sa.Column("estimated_fare", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="VND"),
        sa.Column("eta_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bookings_session_id", "bookings", ["session_id"])

    op.create_table(
        "trips",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("booking_id", sa.String(length=32), sa.ForeignKey("bookings.id"), nullable=False, unique=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="SEARCHING_DRIVER"),
        sa.Column("eta_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "handoffs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("ride_sessions.id"), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("pending_action", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_handoffs_session_id", "handoffs", ["session_id"])

    op.create_table(
        "calls",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("ride_sessions.id"), nullable=True),
        sa.Column("customer_phone_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "conversation_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("ride_sessions.id"), nullable=True),
        sa.Column("call_id", sa.String(length=32), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("intent", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_conversation_events_session_id", "conversation_events", ["session_id"])
    op.create_index("ix_conversation_events_created_at", "conversation_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("conversation_events")
    op.drop_table("calls")
    op.drop_table("handoffs")
    op.drop_table("trips")
    op.drop_table("bookings")
    op.drop_table("auth_tokens")
    op.drop_table("ride_sessions")
    op.drop_table("users")
