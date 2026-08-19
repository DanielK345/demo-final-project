from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.backend.db.base import get_session_factory
from src.backend.db.models import (
    AuthChallenge,
    AuthToken,
    Booking,
    Call,
    ConversationMessage,
    FareQuote,
    Handoff,
    IdempotencyRecord,
    OutboxEvent,
    PolicyAcceptance,
    PricingCatalogVersion,
    RideSession,
    Trip,
    User,
    UserSetting,
)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _user_dict(user: User, acceptance: PolicyAcceptance | None = None) -> dict[str, object]:
    result: dict[str, object] = {
        "user_id": user.id,
        "full_name": user.full_name,
        "phone": user.phone,
        "password_hash": user.password_hash,
        "role": user.role,
        "two_factor_enabled": user.two_factor_enabled,
        "totp_secret_ciphertext": user.totp_secret_ciphertext,
        "totp_pending_secret_ciphertext": user.totp_pending_secret_ciphertext,
    }
    if acceptance is not None:
        result["policy_acceptance"] = {
            "terms_version": acceptance.terms_version,
            "privacy_version": acceptance.privacy_version,
            "accepted_at": acceptance.accepted_at.isoformat(),
            "source_sha256": acceptance.source_sha256,
        }
    return result


def _session_dict(row: RideSession) -> dict[str, object]:
    return {
        "session_id": row.id,
        "call_id": row.call_id,
        "user_id": row.user_id,
        "user_phone": row.user_phone,
        "status": row.status,
        "channel": row.channel,
        "device_id": row.device_id,
        "intent": row.intent,
        "pickup": row.pickup,
        "destination": row.destination,
        "vehicle_type": row.vehicle_type,
        "confirmation_status": row.confirmation_status,
        "failed_count": row.failed_count,
        "booking_id": row.booking_id,
        "handoff_triggered": row.handoff_triggered,
        "handoff_id": row.handoff_id,
        "booking_lifecycle_status": row.booking_lifecycle_status,
        "feedback": row.feedback,
        "current_workflow": row.current_workflow,
        "current_step": row.current_step,
        "agent_state": row.agent_state,
        "turn_sequence": row.turn_sequence,
        "version": row.version,
        "created_at": _iso(row.created_at),
        "ended_at": _iso(row.ended_at),
        "end_reason": row.end_reason,
    }


def _booking_dict(row: Booking) -> dict[str, object]:
    return {
        "booking_id": row.id,
        "session_id": row.session_id,
        "user_id": row.user_id,
        "quote_id": row.quote_id,
        "status": row.status,
        "estimated_fare": row.estimated_fare,
        "quoted_fare_amount": row.quoted_fare_amount,
        "currency": row.currency,
        "eta_minutes": row.eta_minutes,
        "pickup": row.pickup,
        "destination": row.destination,
        "vehicle_type": row.vehicle_type,
        "pricing_version": row.pricing_version,
        "pricing_snapshot": row.pricing_snapshot,
        "route_snapshot": row.route_snapshot,
        "promotion_snapshot": row.promotion_snapshot,
        "quote_context_hash": row.quote_context_hash,
        "created_at": _iso(row.created_at),
        "cancelled_at": _iso(row.cancelled_at),
    }


class PersistenceRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self.factory = factory or get_session_factory()

    async def ensure_voice_guest(self, phone: str) -> dict[str, object]:
        try:
            async with self.factory() as db, db.begin():
                existing = (await db.execute(select(User).where(User.phone == phone))).scalar_one_or_none()
                if existing is not None:
                    return _user_dict(existing)
                row = User(
                    id=f"guest_{uuid4().hex[:10]}",
                    full_name="Khách gọi AloSM",
                    phone=phone,
                    password_hash="LOGIN_DISABLED",
                    role="GUEST",
                )
                db.add(row)
                await db.flush()
                return _user_dict(row)
        except IntegrityError:
            # A concurrent call may have inserted the same unique phone first.
            async with self.factory() as retry_db:
                found = (await retry_db.execute(select(User).where(User.phone == phone))).scalar_one()
                return _user_dict(found)

    async def create_user(
        self,
        *,
        full_name: str,
        phone: str,
        password_hash: str,
        terms_version: str,
        privacy_version: str,
        source_sha256: str,
    ) -> dict[str, object]:
        async with self.factory() as db, db.begin():
            user = User(
                id=f"usr_{uuid4().hex[:10]}",
                full_name=full_name,
                phone=phone,
                password_hash=password_hash,
                role="CUSTOMER",
            )
            acceptance = PolicyAcceptance(
                id=f"pa_{uuid4().hex[:16]}",
                user_id=user.id,
                terms_version=terms_version,
                privacy_version=privacy_version,
                source_sha256=source_sha256,
                acceptance_channel="WEB",
            )
            db.add_all((user, acceptance))
            try:
                await db.flush()
            except IntegrityError as exc:
                raise ValueError("Số điện thoại đã được đăng ký") from exc
            await db.refresh(acceptance)
            return _user_dict(user, acceptance)

    async def user_by_phone(self, phone: str) -> dict[str, object] | None:
        async with self.factory() as db:
            row = (await db.execute(select(User).where(User.phone == phone))).scalar_one_or_none()
            return await self._with_acceptance(db, row)

    async def user_by_id(self, user_id: str) -> dict[str, object] | None:
        async with self.factory() as db:
            row = await db.get(User, user_id)
            return await self._with_acceptance(db, row)

    @staticmethod
    async def _with_acceptance(db: AsyncSession, user: User | None) -> dict[str, object] | None:
        if user is None:
            return None
        acceptance = (
            await db.execute(
                select(PolicyAcceptance)
                .where(PolicyAcceptance.user_id == user.id, PolicyAcceptance.withdrawn_at.is_(None))
                .order_by(PolicyAcceptance.accepted_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return _user_dict(user, acceptance)

    async def issue_token(self, *, raw_token: str, user_id: str, session_id: str, expires_at: datetime) -> None:
        async with self.factory() as db, db.begin():
            db.add(
                AuthToken(
                    token=f"tok_{uuid4().hex[:28]}",
                    token_hash=_token_hash(raw_token),
                    user_id=user_id,
                    session_id=session_id,
                    expires_at=expires_at,
                )
            )

    async def user_for_token(self, raw_token: str) -> dict[str, object] | None:
        now = datetime.now(UTC)
        async with self.factory() as db, db.begin():
            token = (
                await db.execute(
                    select(AuthToken).where(
                        AuthToken.token_hash == _token_hash(raw_token),
                        AuthToken.expires_at > now,
                        AuthToken.revoked_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if token is None:
                return None
            token.last_used_at = now
            user = await db.get(User, token.user_id)
            return await self._with_acceptance(db, user)

    async def session_for_token(self, raw_token: str) -> str | None:
        now = datetime.now(UTC)
        async with self.factory() as db:
            return (
                await db.execute(
                    select(AuthToken.session_id).where(
                        AuthToken.token_hash == _token_hash(raw_token),
                        AuthToken.expires_at > now,
                        AuthToken.revoked_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

    async def bind_token_session(self, raw_token: str, session_id: str) -> None:
        async with self.factory() as db, db.begin():
            result = await db.execute(
                update(AuthToken)
                .where(AuthToken.token_hash == _token_hash(raw_token), AuthToken.revoked_at.is_(None))
                .values(session_id=session_id)
            )
            if result.rowcount != 1:
                raise ValueError("Token không hợp lệ")

    async def update_user_security(self, user_id: str, **updates: object) -> None:
        async with self.factory() as db, db.begin():
            await db.execute(update(User).where(User.id == user_id).values(**updates, updated_at=datetime.now(UTC)))

    async def create_auth_challenge(self, *, raw_token: str, user_id: str, expires_at: datetime) -> None:
        async with self.factory() as db, db.begin():
            db.add(
                AuthChallenge(
                    id=f"ach_{uuid4().hex[:16]}",
                    challenge_token_hash=_token_hash(raw_token),
                    user_id=user_id,
                    purpose="LOGIN_2FA",
                    expires_at=expires_at,
                )
            )

    async def auth_challenge_user(self, raw_token: str) -> dict[str, object] | None:
        now = datetime.now(UTC)
        async with self.factory() as db:
            row = (
                await db.execute(
                    select(AuthChallenge).where(
                        AuthChallenge.challenge_token_hash == _token_hash(raw_token),
                        AuthChallenge.consumed_at.is_(None),
                        AuthChallenge.expires_at > now,
                    )
                )
            ).scalar_one_or_none()
            return await self._with_acceptance(db, await db.get(User, row.user_id)) if row else None

    async def consume_auth_challenge(self, raw_token: str) -> dict[str, object] | None:
        now = datetime.now(UTC)
        async with self.factory() as db, db.begin():
            row = (
                await db.execute(
                    select(AuthChallenge)
                    .where(
                        AuthChallenge.challenge_token_hash == _token_hash(raw_token),
                        AuthChallenge.consumed_at.is_(None),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None or _as_utc(row.expires_at) <= now:
                return None
            row.consumed_at = now
            return await self._with_acceptance(db, await db.get(User, row.user_id))

    async def create_session(
        self, *, user_id: str, channel: str, device_id: str | None, phone: str | None
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        row = RideSession(
            id=f"sess_{uuid4().hex[:12]}",
            call_id=f"call_{uuid4().hex[:8]}",
            user_id=user_id,
            user_phone=phone,
            status="ACTIVE",
            channel=channel,
            device_id=device_id,
            confirmation_status="pending",
            failed_count=0,
            turn_sequence=0,
            version=1,
            created_at=now,
        )
        async with self.factory() as db, db.begin():
            db.add(row)
        return _session_dict(row)

    async def get_session(self, session_id: str) -> dict[str, object] | None:
        async with self.factory() as db:
            row = await db.get(RideSession, session_id)
            return _session_dict(row) if row else None

    async def update_session(
        self, session_id: str, updates: Mapping[str, object], *, expected_version: int | None = None
    ) -> dict[str, object] | None:
        allowed = {
            "status",
            "channel",
            "device_id",
            "intent",
            "pickup",
            "destination",
            "vehicle_type",
            "confirmation_status",
            "failed_count",
            "booking_id",
            "handoff_triggered",
            "current_workflow",
            "current_step",
            "end_reason",
            "ended_at",
            "user_phone",
            "agent_state",
            "turn_sequence",
            "handoff_id",
            "booking_lifecycle_status",
            "feedback",
        }
        values = {key: value for key, value in updates.items() if key in allowed}
        values["updated_at"] = datetime.now(UTC)
        async with self.factory() as db, db.begin():
            statement = update(RideSession).where(RideSession.id == session_id)
            if expected_version is not None:
                statement = statement.where(RideSession.version == expected_version)
            statement = statement.values(**values, version=RideSession.version + 1).returning(RideSession)
            row = (await db.execute(statement)).scalar_one_or_none()
            return _session_dict(row) if row else None

    async def list_sessions(self, user_id: str) -> list[dict[str, object]]:
        async with self.factory() as db:
            rows = (
                (
                    await db.execute(
                        select(RideSession)
                        .where(RideSession.user_id == user_id)
                        .order_by(RideSession.created_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            return [_session_dict(row) for row in rows]

    async def append_messages(
        self,
        *,
        session_id: str,
        turn_id: str,
        user_text: str,
        agent_text: str,
        source: str,
        confidence: float | None,
        action: str | None,
    ) -> None:
        async with self.factory() as db, db.begin():
            db.add_all(
                (
                    ConversationMessage(
                        session_id=session_id,
                        turn_id=turn_id,
                        sequence=1,
                        role="user",
                        source=source,
                        text_redacted=user_text,
                        stt_confidence=confidence,
                    ),
                    ConversationMessage(
                        session_id=session_id,
                        turn_id=turn_id,
                        sequence=2,
                        role="agent",
                        source="AGENT",
                        text_redacted=agent_text,
                        action=action,
                    ),
                )
            )

    async def conversation_messages(self, session_id: str) -> list[dict[str, object]]:
        async with self.factory() as db:
            rows = (
                (
                    await db.execute(
                        select(ConversationMessage)
                        .where(ConversationMessage.session_id == session_id)
                        .order_by(ConversationMessage.id)
                    )
                )
                .scalars()
                .all()
            )
            return [
                {
                    "timestamp": _iso(row.created_at),
                    "role": row.role,
                    "text": row.text_redacted,
                    "source": row.source,
                    "stt_confidence": row.stt_confidence,
                    "action": row.action,
                }
                for row in rows
            ]

    async def get_settings(self, user_id: str) -> dict[str, object]:
        async with self.factory() as db:
            row = await db.get(UserSetting, user_id)
            if row is None:
                return {
                    "push_notifications": True,
                    "email_notifications": False,
                    "sms_notifications": True,
                    "language": "vi",
                    "theme": "light",
                }
            return {
                "push_notifications": row.push_notifications,
                "email_notifications": row.email_notifications,
                "sms_notifications": row.sms_notifications,
                "language": row.language,
                "theme": row.theme,
            }

    async def update_settings(self, user_id: str, values: Mapping[str, object]) -> dict[str, object]:
        clean = {
            key: value
            for key, value in values.items()
            if value is not None
            and key in {"push_notifications", "email_notifications", "sms_notifications", "language", "theme"}
        }
        async with self.factory() as db, db.begin():
            row = await db.get(UserSetting, user_id, with_for_update=True)
            if row is None:
                row = UserSetting(user_id=user_id, **clean)
                db.add(row)
            else:
                for key, value in clean.items():
                    setattr(row, key, value)
                row.updated_at = datetime.now(UTC)
            await db.flush()
            return {
                "push_notifications": row.push_notifications,
                "email_notifications": row.email_notifications,
                "sms_notifications": row.sms_notifications,
                "language": row.language,
                "theme": row.theme,
            }

    async def create_handoff(self, values: Mapping[str, object]) -> dict[str, object]:
        row = Handoff(id=f"handoff_{uuid4().hex[:8]}", **values)
        async with self.factory() as db, db.begin():
            db.add(row)
            await db.flush()
        return self._handoff_dict(row)

    async def list_handoffs(self, status: str) -> list[dict[str, object]]:
        async with self.factory() as db:
            rows = (
                (
                    await db.execute(
                        select(Handoff)
                        .where(Handoff.status == status)
                        .order_by(Handoff.priority.desc(), Handoff.created_at)
                    )
                )
                .scalars()
                .all()
            )
            return [self._handoff_dict(row) for row in rows]

    async def accept_handoff(self, handoff_id: str, operator_id: str | None) -> dict[str, object] | None:
        async with self.factory() as db, db.begin():
            row = (
                await db.execute(select(Handoff).where(Handoff.id == handoff_id).with_for_update())
            ).scalar_one_or_none()
            if row is None:
                return None
            row.status, row.operator_id, row.accepted_at = "accepted", operator_id, datetime.now(UTC)
            return self._handoff_dict(row)

    @staticmethod
    def _handoff_dict(row: Handoff) -> dict[str, object]:
        return {
            "handoff_id": row.id,
            "session_id": row.session_id,
            "reason": row.reason,
            "reason_code": row.reason_code,
            "summary": row.summary,
            "pending_action": row.pending_action,
            "priority": row.priority,
            "severity": row.severity,
            "queue": row.queue,
            "requires_immediate_transfer": row.requires_immediate_transfer,
            "status": row.status,
            "created_at": row.created_at,
            "accepted_at": row.accepted_at,
            "operator_id": row.operator_id,
        }

    async def create_call(self, *, session_id: str | None, customer_phone_hash: str) -> dict[str, object]:
        row = Call(
            id=f"call_{uuid4().hex[:8]}",
            session_id=session_id,
            customer_phone_hash=customer_phone_hash,
            status="active",
        )
        async with self.factory() as db, db.begin():
            db.add(row)
        return {"call_id": row.id, "session_id": row.session_id, "status": row.status}

    async def get_or_create_trip(self, booking_id: str, defaults: Mapping[str, object]) -> dict[str, object]:
        async with self.factory() as db, db.begin():
            row = (
                await db.execute(select(Trip).where(Trip.booking_id == booking_id).with_for_update())
            ).scalar_one_or_none()
            if row is None:
                row = Trip(id=f"trip_{booking_id.removeprefix('book_')}", booking_id=booking_id, **defaults)
                db.add(row)
                await db.flush()
            return {
                "trip_id": row.id,
                "booking_id": row.booking_id,
                "status": row.status,
                "eta_minutes": row.eta_minutes,
                "driver_name": row.driver_name,
                "vehicle": row.vehicle,
                "license_plate": row.license_plate,
                "driver_rating": float(row.driver_rating) if row.driver_rating is not None else None,
                "driver_phone": row.driver_phone,
                "created_at": row.created_at,
            }

    async def update_trip(self, booking_id: str, *, status: str, eta_minutes: int) -> None:
        async with self.factory() as db, db.begin():
            await db.execute(
                update(Trip)
                .where(Trip.booking_id == booking_id)
                .values(status=status, eta_minutes=eta_minutes, updated_at=datetime.now(UTC))
            )

    async def ensure_pricing_catalog(self, snapshot: Mapping[str, Any]) -> PricingCatalogVersion:
        version, region = str(snapshot["version"]), str(snapshot["region"])
        try:
            async with self.factory() as db, db.begin():
                row = (
                    await db.execute(
                        select(PricingCatalogVersion).where(
                            PricingCatalogVersion.version == version,
                            PricingCatalogVersion.region == region,
                        )
                    )
                ).scalar_one_or_none()
                if row is not None:
                    if row.source_sha256 != snapshot["source_sha256"]:
                        raise ValueError("PRICING_VERSION_IMMUTABILITY_VIOLATION")
                    return row
                effective = datetime.fromisoformat(str(snapshot["effective_from"]))
                if effective.tzinfo is None:
                    effective = effective.replace(tzinfo=UTC)
                row = PricingCatalogVersion(
                    id=f"pcv_{uuid4().hex[:16]}",
                    version=version,
                    region=region,
                    currency=str(snapshot["currency"]),
                    status=str(snapshot["status"]),
                    effective_from=effective,
                    source_sha256=str(snapshot["source_sha256"]),
                    catalog_snapshot=dict(snapshot),
                    approved_by=str(snapshot.get("approver") or "UNVERIFIED"),
                )
                db.add(row)
                await db.flush()
                return row
        except IntegrityError:
            # A concurrent quote may have inserted this immutable version first.
            async with self.factory() as retry_db:
                row = (
                    await retry_db.execute(
                        select(PricingCatalogVersion).where(
                            PricingCatalogVersion.version == version,
                            PricingCatalogVersion.region == region,
                        )
                    )
                ).scalar_one()
                if row.source_sha256 != snapshot["source_sha256"]:
                    raise ValueError("PRICING_VERSION_IMMUTABILITY_VIOLATION")
                return row

    async def create_quote(self, values: Mapping[str, Any]) -> dict[str, object]:
        row = FareQuote(**values)
        async with self.factory() as db, db.begin():
            db.add(row)
            await db.flush()
        return self._quote_dict(row)

    async def get_quote(self, quote_id: str) -> dict[str, object] | None:
        async with self.factory() as db:
            row = await db.get(FareQuote, quote_id)
            return self._quote_dict(row) if row else None

    @staticmethod
    def _quote_dict(row: FareQuote) -> dict[str, object]:
        return {
            "quote_id": row.id,
            "estimate_id": row.id,
            "user_id": row.user_id,
            "session_id": row.session_id,
            "pricing_catalog_id": row.pricing_catalog_id,
            "route_snapshot_id": row.route_snapshot_id,
            "pickup_place_id": row.pickup_place_id,
            "destination_place_id": row.destination_place_id,
            "vehicle_type": row.vehicle_type,
            "route_snapshot": row.route_snapshot,
            "pricing_snapshot": row.pricing_snapshot,
            "promotion_snapshot": row.promotion_snapshot,
            "fare_breakdown": {
                "base_fare": row.base_fare,
                "distance_fare": row.distance_fare,
                "time_fare": row.time_fare,
                "surcharge_amount": row.surcharge_amount,
                "discount_amount": row.discount_amount,
                "applied_surcharges": row.pricing_snapshot.get("applied_surcharges", []),
            },
            "fare_amount": row.total_amount,
            "currency": row.currency,
            "context_hash": row.context_hash,
            "signature": row.signature,
            "status": row.status,
            "issued_at": _iso(row.issued_at),
            "expires_at": _iso(row.expires_at),
        }

    async def create_booking_from_quote(
        self,
        *,
        quote_id: str,
        user_id: str,
        session_id: str,
        idempotency_key: str,
        request_hash: str,
        pickup: dict | None,
        destination: dict | None,
        eta_minutes: int | None,
    ) -> dict[str, object]:
        now = datetime.now(UTC)
        async with self.factory() as db, db.begin():
            previous = await db.get(
                IdempotencyRecord, {"scope": "CREATE_BOOKING", "idempotency_key": idempotency_key}, with_for_update=True
            )
            if previous is not None:
                if previous.request_hash != request_hash:
                    raise ValueError("IDEMPOTENCY_KEY_REUSED")
                if previous.response_snapshot:
                    return {**previous.response_snapshot, "status": "ALREADY_CREATED"}
            quote = (
                await db.execute(select(FareQuote).where(FareQuote.id == quote_id).with_for_update())
            ).scalar_one_or_none()
            if quote is None:
                raise ValueError("QUOTE_NOT_FOUND")
            if quote.user_id != user_id or quote.session_id != session_id:
                raise ValueError("QUOTE_OWNERSHIP_MISMATCH")
            if _as_utc(quote.expires_at) <= now:
                quote.status = "EXPIRED"
                raise ValueError("QUOTE_EXPIRED")
            if quote.status == "CONSUMED" and quote.consumed_by_booking_id:
                existing = await db.get(Booking, quote.consumed_by_booking_id)
                if existing:
                    return {**_booking_dict(existing), "status": "ALREADY_CREATED"}
            if quote.status != "ISSUED":
                raise ValueError("QUOTE_NOT_USABLE")
            booking = Booking(
                id=f"book_{uuid4().hex[:8]}",
                session_id=session_id,
                user_id=user_id,
                quote_id=quote.id,
                idempotency_key=idempotency_key,
                pickup=pickup,
                destination=destination,
                vehicle_type=quote.vehicle_type,
                status="SEARCHING_DRIVER",
                estimated_fare=quote.total_amount,
                quoted_fare_amount=quote.total_amount,
                currency=quote.currency,
                eta_minutes=eta_minutes,
                pricing_version=quote.pricing_snapshot.get("pricing_version"),
                pricing_snapshot=quote.pricing_snapshot,
                route_snapshot=quote.route_snapshot,
                promotion_snapshot=quote.promotion_snapshot,
                quote_context_hash=quote.context_hash,
                confirmed_at=now,
            )
            db.add(booking)
            response = _booking_dict(booking)
            record = previous or IdempotencyRecord(
                scope="CREATE_BOOKING",
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                status="COMPLETED",
                expires_at=now + timedelta(hours=24),
            )
            record.resource_type, record.resource_id, record.response_snapshot = "BOOKING", booking.id, response
            if previous is None:
                db.add(record)
            quote.status, quote.consumed_at, quote.consumed_by_booking_id = "CONSUMED", now, booking.id
            db.add(
                OutboxEvent(
                    aggregate_type="BOOKING",
                    aggregate_id=booking.id,
                    event_type="BOOKING_CREATED",
                    payload={"booking_id": booking.id, "quote_id": quote.id},
                )
            )
            await db.flush()
            return _booking_dict(booking)

    async def booking(self, booking_id: str) -> dict[str, object] | None:
        async with self.factory() as db:
            row = await db.get(Booking, booking_id)
            return _booking_dict(row) if row else None

    async def bookings_for_user(self, user_id: str) -> list[dict[str, object]]:
        async with self.factory() as db:
            rows = (
                (
                    await db.execute(
                        select(Booking).where(Booking.user_id == user_id).order_by(Booking.created_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            return [_booking_dict(row) for row in rows]

    async def cancel_booking(
        self, booking_id: str, user_id: str | None, idempotency_key: str
    ) -> dict[str, object] | None:
        now = datetime.now(UTC)
        request_hash = hashlib.sha256(f"{booking_id}:{user_id}".encode()).hexdigest()
        async with self.factory() as db, db.begin():
            previous = await db.get(
                IdempotencyRecord, {"scope": "CANCEL_BOOKING", "idempotency_key": idempotency_key}, with_for_update=True
            )
            if previous is not None:
                if previous.request_hash != request_hash:
                    raise ValueError("IDEMPOTENCY_KEY_REUSED")
                return previous.response_snapshot
            row = (
                await db.execute(select(Booking).where(Booking.id == booking_id).with_for_update())
            ).scalar_one_or_none()
            if row is None or (user_id is not None and row.user_id != user_id):
                return None
            row.status, row.cancelled_at = "CANCELLED", now
            response = _booking_dict(row)
            db.add(
                IdempotencyRecord(
                    scope="CANCEL_BOOKING",
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    status="COMPLETED",
                    resource_type="BOOKING",
                    resource_id=row.id,
                    response_snapshot=response,
                    expires_at=now + timedelta(hours=24),
                )
            )
            db.add(
                OutboxEvent(
                    aggregate_type="BOOKING",
                    aggregate_id=row.id,
                    event_type="BOOKING_CANCELLED",
                    payload={"booking_id": row.id},
                )
            )
            return response
