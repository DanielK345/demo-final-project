"""add durable persistence and fare quote integrity

Revision ID: 9e9b6f420a9a
Revises: 0002_handoff_operations
Create Date: 2026-08-16
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9e9b6f420a9a"
down_revision: str | None = "0002_handoff_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
J = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
BIGINT_PRIMARY_KEY = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.add_column("users", sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("totp_secret_ciphertext", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("totp_pending_secret_ciphertext", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("auth_tokens", sa.Column("token_hash", sa.String(64), nullable=True))
    op.add_column("auth_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("auth_tokens", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ux_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=True)

    for name, column in (
        ("user_phone", sa.Column("user_phone", sa.String(20), nullable=True)),
        ("agent_state", sa.Column("agent_state", J, nullable=True)),
        ("turn_sequence", sa.Column("turn_sequence", sa.BigInteger(), nullable=False, server_default="0")),
        ("handoff_id", sa.Column("handoff_id", sa.String(32), nullable=True)),
        ("booking_lifecycle_status", sa.Column("booking_lifecycle_status", sa.String(30), nullable=True)),
        ("feedback", sa.Column("feedback", J, nullable=True)),
        ("version", sa.Column("version", sa.Integer(), nullable=False, server_default="1")),
        ("updated_at", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())),
    ):
        op.add_column("ride_sessions", column)
    op.create_index("ix_ride_sessions_user_created", "ride_sessions", ["user_id", "created_at"])

    # SQLite cannot add foreign-key constraints with ALTER TABLE. Alembic's
    # batch mode recreates the table there, while preserving normal ALTER TABLE
    # semantics on PostgreSQL.
    with op.batch_alter_table("bookings") as batch_op:
        for column in (
            sa.Column("user_id", sa.String(32), nullable=True),
            sa.Column("quoted_fare_amount", sa.BigInteger(), nullable=True),
            sa.Column("pricing_version", sa.String(64), nullable=True),
            sa.Column("pricing_snapshot", J, nullable=True),
            sa.Column("route_snapshot", J, nullable=True),
            sa.Column("promotion_snapshot", J, nullable=True),
            sa.Column("quote_context_hash", sa.String(64), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("final_fare_amount", sa.BigInteger(), nullable=True),
        ):
            batch_op.add_column(column)
        batch_op.create_foreign_key("fk_bookings_user_id", "users", ["user_id"], ["id"])
    op.create_index("ix_bookings_user_created", "bookings", ["user_id", "created_at"])
    op.create_index("ix_bookings_session_created", "bookings", ["session_id", "created_at"])

    for column in (
        sa.Column("driver_name", sa.String(100), nullable=True),
        sa.Column("vehicle", sa.String(100), nullable=True),
        sa.Column("license_plate", sa.String(20), nullable=True),
        sa.Column("driver_phone", sa.String(20), nullable=True),
        sa.Column("driver_rating", sa.Numeric(3, 2), nullable=True),
    ):
        op.add_column("trips", column)

    op.create_table("policy_acceptances",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("terms_version", sa.String(40), nullable=False),
        sa.Column("privacy_version", sa.String(40), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("acceptance_channel", sa.String(30), nullable=False, server_default="WEB"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_policy_acceptances_user_accepted", "policy_acceptances", ["user_id", "accepted_at"])

    op.create_table("auth_challenges",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("challenge_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_count >= 0", name="ck_auth_challenge_attempt_count"),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_challenge_expiry"))
    op.create_index("ix_auth_challenges_active", "auth_challenges", ["challenge_token_hash", "expires_at"])
    op.create_index("ix_auth_challenges_user_id", "auth_challenges", ["user_id"])

    op.create_table("user_settings",
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("push_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sms_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("language", sa.String(10), nullable=False, server_default="vi"),
        sa.Column("theme", sa.String(20), nullable=False, server_default="light"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))

    op.create_table("conversation_messages",
        sa.Column("id", BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(32), sa.ForeignKey("ride_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_id", sa.String(64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("source", sa.String(20), nullable=True),
        sa.Column("text_redacted", sa.Text(), nullable=False),
        sa.Column("stt_confidence", sa.Float(), nullable=True),
        sa.Column("action", sa.String(50), nullable=True),
        sa.Column("tool_name", sa.String(50), nullable=True),
        sa.Column("tool_call_id", sa.String(64), nullable=True),
        sa.Column("message_metadata", J, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("session_id", "turn_id", "sequence", name="uq_conversation_message_turn_sequence"))
    op.create_index("ix_conversation_messages_session_sequence", "conversation_messages", ["session_id", "id"])

    op.create_table("pricing_catalog_versions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("region", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("catalog_snapshot", J, nullable=False),
        sa.Column("approved_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("version", "region", name="uq_pricing_catalog_version_region"),
        sa.CheckConstraint("effective_until is null or effective_until > effective_from", name="ck_pricing_catalog_effective_range"))

    op.create_table("fare_quotes",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.String(32), sa.ForeignKey("ride_sessions.id"), nullable=False),
        sa.Column("pricing_catalog_id", sa.String(32), sa.ForeignKey("pricing_catalog_versions.id"), nullable=False),
        sa.Column("pickup_place_id", sa.String(255), nullable=False),
        sa.Column("destination_place_id", sa.String(255), nullable=False),
        sa.Column("vehicle_type", sa.String(30), nullable=False),
        sa.Column("route_snapshot", J, nullable=False),
        sa.Column("pricing_snapshot", J, nullable=False),
        sa.Column("promotion_snapshot", J, nullable=False),
        sa.Column("base_fare", sa.BigInteger(), nullable=False),
        sa.Column("distance_fare", sa.BigInteger(), nullable=False),
        sa.Column("time_fare", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("surcharge_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ISSUED"),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by_booking_id", sa.String(32), nullable=True),
        sa.CheckConstraint("expires_at > issued_at", name="ck_fare_quote_expiry"),
        sa.CheckConstraint("base_fare >= 0 and distance_fare >= 0 and time_fare >= 0 and surcharge_amount >= 0 and discount_amount >= 0", name="ck_fare_quote_nonnegative"),
        sa.CheckConstraint("total_amount = base_fare + distance_fare + time_fare + surcharge_amount - discount_amount and total_amount >= 0", name="ck_fare_quote_total"))
    op.create_index("ix_fare_quotes_session_status_expiry", "fare_quotes", ["session_id", "status", "expires_at"])
    op.create_index("ix_fare_quotes_pricing_catalog_id", "fare_quotes", ["pricing_catalog_id"])
    op.create_index("ix_fare_quotes_user_issued", "fare_quotes", ["user_id", "issued_at"])

    with op.batch_alter_table("bookings") as batch_op:
        batch_op.add_column(sa.Column("quote_id", sa.String(32), nullable=True))
        batch_op.create_foreign_key("fk_bookings_quote_id", "fare_quotes", ["quote_id"], ["id"])
    op.create_index("ux_bookings_quote_id", "bookings", ["quote_id"], unique=True)

    op.create_table("idempotency_records",
        sa.Column("scope", sa.String(50), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), primary_key=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(32), nullable=True),
        sa.Column("response_snapshot", J, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("expires_at > created_at", name="ck_idempotency_expiry"))
    op.create_index("ix_idempotency_expiry", "idempotency_records", ["expires_at"])

    op.create_table("outbox_events",
        sa.Column("id", BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", J, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_count >= 0", name="ck_outbox_attempt_count"))
    op.create_index("ix_outbox_pending", "outbox_events", ["status", "available_at", "created_at"])

    if op.get_bind().dialect.name == "postgresql":
        tables = ("users", "auth_tokens", "ride_sessions", "bookings", "trips", "handoffs", "calls", "conversation_events", "policy_acceptances", "auth_challenges", "user_settings", "conversation_messages", "pricing_catalog_versions", "fare_quotes", "idempotency_records", "outbox_events")
        bind = op.get_bind()
        data_api_roles = {
            row[0]
            for row in bind.execute(
                sa.text(
                    "SELECT rolname FROM pg_roles "
                    "WHERE rolname IN (:anon_role, :authenticated_role)"
                ),
                {"anon_role": "anon", "authenticated_role": "authenticated"},
            )
        }
        for table in tables:
            op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))
            for role in data_api_roles:
                op.execute(sa.text(f'REVOKE ALL ON TABLE public."{table}" FROM "{role}"'))


def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("idempotency_records")
    op.drop_index("ux_bookings_quote_id", table_name="bookings")
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_constraint("fk_bookings_quote_id", type_="foreignkey")
        batch_op.drop_column("quote_id")
    op.drop_table("fare_quotes")
    op.drop_table("pricing_catalog_versions")
    op.drop_table("conversation_messages")
    op.drop_table("user_settings")
    op.drop_table("auth_challenges")
    op.drop_table("policy_acceptances")
    for name in ("driver_rating", "driver_phone", "license_plate", "vehicle", "driver_name"):
        op.drop_column("trips", name)
    op.drop_index("ix_bookings_session_created", table_name="bookings")
    op.drop_index("ix_bookings_user_created", table_name="bookings")
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_constraint("fk_bookings_user_id", type_="foreignkey")
        for name in ("final_fare_amount", "cancelled_at", "confirmed_at", "quote_context_hash", "promotion_snapshot", "route_snapshot", "pricing_snapshot", "pricing_version", "quoted_fare_amount", "user_id"):
            batch_op.drop_column(name)
    op.drop_index("ix_ride_sessions_user_created", table_name="ride_sessions")
    for name in ("updated_at", "version", "feedback", "booking_lifecycle_status", "handoff_id", "turn_sequence", "agent_state", "user_phone"):
        op.drop_column("ride_sessions", name)
    op.drop_index("ux_auth_tokens_token_hash", table_name="auth_tokens")
    for name in ("last_used_at", "revoked_at", "token_hash"):
        op.drop_column("auth_tokens", name)
    for name in ("updated_at", "password_changed_at", "totp_pending_secret_ciphertext", "totp_secret_ciphertext", "two_factor_enabled"):
        op.drop_column("users", name)
