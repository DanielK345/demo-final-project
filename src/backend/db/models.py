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

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.backend.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="CUSTOMER")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tokens: Mapped[list["AuthToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ride_sessions: Mapped[list["RideSession"]] = relationship(back_populates="user")


class AuthToken(Base):
    """Bearer token đăng nhập — persist thay vì dict RAM để sống sót qua restart /
    chạy được nhiều instance backend cùng lúc (điều kiện cần khi deploy thật)."""

    __tablename__ = "auth_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped["User"] = relationship(back_populates="tokens")


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
    pickup: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    destination: Mapped[dict | None] = mapped_column(JSON, nullable=True)
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

    user: Mapped["User"] = relationship(back_populates="ride_sessions")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="session")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("ride_sessions.id"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    pickup: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    destination: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="SEARCHING_DRIVER")
    estimated_fare: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="VND")
    eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["RideSession"] = relationship(back_populates="bookings")
    trip: Mapped["Trip"] = relationship(back_populates="booking", uselist=False, cascade="all, delete-orphan")


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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    booking: Mapped["Booking"] = relationship(back_populates="trip")


class Handoff(Base):
    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("ride_sessions.id"), index=True)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    pending_action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
    session_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("ride_sessions.id"), nullable=True, index=True)
    call_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
