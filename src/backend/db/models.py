"""ORM models — ánh xạ 1:1 với các dataclass/DTO đã có sẵn trong
`src/backend/models/*.py` và `src/backend/schemas/*.py`, KHÔNG đổi tên field so với
những gì service/controller hiện tại đang dùng để việc nối dây sau này (thay dict
in-memory bằng repository gọi các model này) là đổi tối thiểu.

ID vẫn dùng string tự sinh kiểu `usr_xxxxxxxx`/`sess_xxxxxxxx` (giữ đúng format
`uuid4().hex[:N]` đã dùng khắp project) thay vì Postgres UUID type — nhất quán với
code hiện có, tránh phải đổi format ID ở API response.

Xem thiết kế đầy đủ (ERD, lý do từng quyết định) tại `docs/database_supabase.md`.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.backend.db.base import Base

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")
BIGINT_PRIMARY_KEY = BigInteger().with_variant(Integer(), "sqlite")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="CUSTOMER")
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    totp_secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_pending_secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tokens: Mapped[list[AuthToken]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ride_sessions: Mapped[list[RideSession]] = relationship(back_populates="user")


class AuthToken(Base):
    """Bearer token đăng nhập — persist thay vì dict RAM để sống sót qua restart /
    chạy được nhiều instance backend cùng lúc (điều kiện cần khi deploy thật)."""

    __tablename__ = "auth_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="tokens")


class RideSession(Base):
    """Phiên hội thoại đặt xe — đổi tên bảng khác `sessions` (tránh nhập nhằng với
    khái niệm "phiên đăng nhập" của `auth_tokens.session_id`), field/behavior giữ
    đúng như `SessionService.sessions[...]` hiện tại."""

    __tablename__ = "ride_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    call_id: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pickup: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    destination: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(20), nullable=True, default="4_SEAT")
    confirmation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Soft-reference tới bookings.id — KHÔNG đặt ForeignKey cứng ở đây để tránh phụ
    # thuộc vòng (ride_sessions <-> bookings được tạo tuần tự: session trước, booking
    # sau khi khách xác nhận, rồi mới quay lại set booking_id lên session).
    booking_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    handoff_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_workflow: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_step: Mapped[str | None] = mapped_column(String(30), nullable=True, default="START")
    end_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    agent_state: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    # LiveKit-native state is isolated from the legacy Core Agent document so the
    # two rollout paths cannot deserialize or overwrite each other's schema.
    voice_agent_state: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    voice_state_revision: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    turn_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    handoff_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    booking_lifecycle_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    feedback: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="ride_sessions")
    bookings: Mapped[list[Booking]] = relationship(back_populates="session")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("ride_sessions.id"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    pickup: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    destination: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SEARCHING_DRIVER")
    estimated_fare: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="VND")
    eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True, index=True)
    quote_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("fare_quotes.id"), nullable=True, unique=True)
    quoted_fare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pricing_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pricing_snapshot: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    route_snapshot: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    promotion_snapshot: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    quote_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_fare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    session: Mapped[RideSession] = relationship(back_populates="bookings")
    trip: Mapped[Trip] = relationship(back_populates="booking", uselist=False, cascade="all, delete-orphan")


class Trip(Base):
    """1 booking gắn với đúng 1 trip mô phỏng — thay cho `TripService.get_status()`
    hiện tại vốn trả `trip_id` ngẫu nhiên MỚI mỗi lần gọi (bug đã ghi ở `mustdo.md`).
    """

    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    booking_id: Mapped[str] = mapped_column(String(32), ForeignKey("bookings.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SEARCHING_DRIVER")
    eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    driver_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    license_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    driver_rating: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)

    booking: Mapped[Booking] = relationship(back_populates="trip")


class Handoff(Base):
    __tablename__ = "handoffs"
    __table_args__ = (Index("ix_handoffs_status_priority", "status", "priority"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("ride_sessions.id"), index=True)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False, default="UNABLE_TO_CONTINUE")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    pending_action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="NORMAL")
    queue: Mapped[str] = mapped_column(String(50), nullable=False, default="GENERAL_OPERATOR")
    requires_immediate_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    operator_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    room_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    context_snapshot: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("ride_sessions.id"), nullable=True)
    customer_phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationEvent(Base):
    """Audit log từng bước hội thoại — phục vụ debug/observability, không có service
    nào ghi vào đây hiện tại (`src/backend/models/event.py` mới chỉ là dataclass chưa
    dùng), nhưng thêm sẵn bảng để dùng khi cần mà không phải migrate thêm lần nữa."""

    __tablename__ = "conversation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("ride_sessions.id"), nullable=True, index=True
    )
    call_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PolicyAcceptance(Base):
    __tablename__ = "policy_acceptances"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    terms_version: Mapped[str] = mapped_column(String(40), nullable=False)
    privacy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    acceptance_channel: Mapped[str] = mapped_column(String(30), nullable=False, default="WEB")
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    challenge_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSetting(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    push_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sms_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="vi")
    theme: Mapped[str] = mapped_column(String(20), nullable=False, default="light")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "turn_id", "sequence", name="uq_conversation_message_turn_sequence"),
    )
    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("ride_sessions.id", ondelete="CASCADE"), index=True)
    turn_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    text_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    stt_confidence: Mapped[float | None] = mapped_column(nullable=True)
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message_metadata: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PricingCatalogVersion(Base):
    __tablename__ = "pricing_catalog_versions"
    __table_args__ = (UniqueConstraint("version", "region", name="uq_pricing_catalog_version_region"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    catalog_snapshot: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FareQuote(Base):
    __tablename__ = "fare_quotes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("ride_sessions.id"), index=True)
    pricing_catalog_id: Mapped[str] = mapped_column(String(32), ForeignKey("pricing_catalog_versions.id"), index=True)
    route_snapshot_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("route_snapshots.id"), nullable=True, index=True
    )
    pickup_place_id: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_place_id: Mapped[str] = mapped_column(String(255), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(30), nullable=False)
    route_snapshot: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    pricing_snapshot: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    promotion_snapshot: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    base_fare: Mapped[int] = mapped_column(BigInteger, nullable=False)
    distance_fare: Mapped[int] = mapped_column(BigInteger, nullable=False)
    time_fare: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    surcharge_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    discount_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ISSUED")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_by_booking_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    scope: Mapped[str] = mapped_column(String(50), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    response_snapshot: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(BIGINT_PRIMARY_KEY, primary_key=True, autoincrement=True)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Place(Base):
    """Resolved place — persisted after user confirmation (§20).

    ``id`` uses internal ``plc_<uuid>`` format; systems MUST NOT depend on
    Nominatim's integer ``place_id`` (stored in ``provider_place_id``).
    """

    __tablename__ = "places"
    __table_args__ = (
        UniqueConstraint("provider", "provider_place_id", name="uq_places_provider_place_id"),
        Index("ix_places_created_at", "created_at"),
        Index("ix_places_serviceable", "serviceable"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_place_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    formatted_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    types: Mapped[dict] = mapped_column(JSON_DOCUMENT, nullable=False, default=list)
    serviceable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    service_area_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RouteSnapshot(Base):
    """Immutable route snapshot — once used by a quote, never mutated (§21, §22).

    If pickup/destination/provider changes, a NEW snapshot is created.
    """

    __tablename__ = "route_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    pickup_place_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("places.id"),
        nullable=False,
        index=True,
    )
    destination_place_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("places.id"),
        nullable=False,
        index=True,
    )
    distance_meters: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    geometry: Mapped[dict | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    source_data_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
