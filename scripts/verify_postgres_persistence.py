"""Live PostgreSQL acceptance for durable state and quote integrity.

This script refuses SQLite, uses no service/repository mocks, never prints secrets,
and removes only records created by its own unique verification run.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import secrets
import sys
from datetime import UTC, datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from src.backend.config import get_settings
from src.backend.db.base import get_engine, get_session_factory, reset_engine_for_tests
from src.backend.maps.contracts import ResolvedPlace, RouteResult
from src.backend.repositories.maps_repository import MapsRepository
from src.backend.repositories.persistence_repository import PersistenceRepository
from src.backend.services.booking_service import BookingService
from src.backend.services.quote_service import QuoteService

ACCEPTED_REVISIONS = ("0004_maps_places_routes", "0005_livekit_voice_state", "acc88dbc1e83")

RLS_TABLES = (
    "users",
    "auth_tokens",
    "ride_sessions",
    "bookings",
    "trips",
    "handoffs",
    "calls",
    "conversation_events",
    "policy_acceptances",
    "auth_challenges",
    "user_settings",
    "conversation_messages",
    "pricing_catalog_versions",
    "fare_quotes",
    "idempotency_records",
    "outbox_events",
)



async def _cleanup(ids: dict[str, str]) -> None:
    factory = get_session_factory()
    async with factory() as db, db.begin():
        statements = (
            ("DELETE FROM outbox_events WHERE aggregate_id = :value", ids.get("booking_id")),
            ("DELETE FROM trips WHERE booking_id = :value", ids.get("booking_id")),
            ("DELETE FROM idempotency_records WHERE resource_id = :value", ids.get("booking_id")),
            ("DELETE FROM bookings WHERE id = :value", ids.get("booking_id")),
            ("DELETE FROM fare_quotes WHERE id = :value", ids.get("quote_id")),
            ("DELETE FROM route_snapshots WHERE id = :value", ids.get("route_id")),
            ("DELETE FROM places WHERE id = :value", ids.get("pickup_place_id")),
            ("DELETE FROM places WHERE id = :value", ids.get("destination_place_id")),
            ("DELETE FROM calls WHERE id = :value", ids.get("call_id")),
            ("DELETE FROM handoffs WHERE id = :value", ids.get("handoff_id")),
            ("DELETE FROM conversation_messages WHERE session_id = :value", ids.get("session_id")),
            ("DELETE FROM user_settings WHERE user_id = :value", ids.get("user_id")),
            ("DELETE FROM auth_tokens WHERE user_id = :value", ids.get("user_id")),
            ("DELETE FROM ride_sessions WHERE id = :value", ids.get("session_id")),
            ("DELETE FROM policy_acceptances WHERE user_id = :value", ids.get("user_id")),
            ("DELETE FROM users WHERE id = :value", ids.get("user_id")),
        )

        for statement, value in statements:
            if value:
                await db.execute(text(statement), {"value": value})


async def main() -> None:
    settings = get_settings()
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        raise SystemExit("Refusing acceptance: DATABASE_URL is not PostgreSQL")
    if len(settings.quote_signing_key) < 32 or len(settings.field_encryption_key) < 32:
        raise SystemExit("Refusing acceptance: signing/encryption keys are not configured")

    factory = get_session_factory()
    async with factory() as db:
        revision = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        if revision not in ACCEPTED_REVISIONS:
            raise SystemExit(f"Refusing acceptance: database revision is {revision}, expected one of {ACCEPTED_REVISIONS}")
        rows = (
            await db.execute(
                text("""
            SELECT c.relname, c.relrowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(:tables)
        """),
                {"tables": list(RLS_TABLES)},
            )
        ).all()
        rls = {name: enabled for name, enabled in rows}
        missing_or_open = sorted(table for table in RLS_TABLES if not rls.get(table, False))
        if missing_or_open:
            raise AssertionError(f"RLS_NOT_ENABLED: {missing_or_open}")

    suffix = secrets.token_hex(5)
    repository = PersistenceRepository()
    ids: dict[str, str] = {}
    try:
        user = await repository.create_user(
            full_name="Postgres Persistence Verification",
            phone=f"09{int(suffix, 16) % 100_000_000:08d}",
            password_hash="LOGIN_DISABLED_ACCEPTANCE_ONLY",
            terms_version="acceptance-test",
            privacy_version="acceptance-test",
            source_sha256=hashlib.sha256(suffix.encode()).hexdigest(),
        )
        ids["user_id"] = str(user["user_id"])
        session = await repository.create_session(
            user_id=ids["user_id"], channel="ACCEPTANCE", device_id=f"verify-{suffix}", phone=None
        )
        ids["session_id"] = str(session["session_id"])
        raw_token = secrets.token_urlsafe(32)
        await repository.issue_token(
            raw_token=raw_token,
            user_id=ids["user_id"],
            session_id=ids["session_id"],
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        assert (await repository.user_for_token(raw_token))["user_id"] == ids["user_id"]
        await repository.update_settings(ids["user_id"], {"language": "vi", "theme": "dark"})
        await repository.append_messages(
            session_id=ids["session_id"],
            turn_id=f"turn-{suffix}",
            user_text="Nội dung đã ẩn danh",
            agent_text="Đã tiếp nhận",
            source="ACCEPTANCE",
            confidence=0.99,
            action="VERIFY",
        )
        handoff = await repository.create_handoff(
            {
                "session_id": ids["session_id"],
                "reason": "acceptance",
                "reason_code": "VERIFY",
                "summary": "PostgreSQL acceptance",
                "pending_action": None,
                "priority": 1,
                "severity": "NORMAL",
                "queue": "GENERAL_OPERATOR",
                "requires_immediate_transfer": False,
                "status": "pending",
            }
        )
        ids["handoff_id"] = str(handoff["handoff_id"])
        await repository.accept_handoff(ids["handoff_id"], "acceptance-operator")
        call = await repository.create_call(
            session_id=ids["session_id"],
            customer_phone_hash=hashlib.sha256(suffix.encode()).hexdigest(),
        )
        ids["call_id"] = str(call["call_id"])

        maps_repository = MapsRepository()
        ids["pickup_place_id"] = f"plc_verify_a_{suffix}"
        ids["destination_place_id"] = f"plc_verify_b_{suffix}"
        ids["route_id"] = f"route_verify_{suffix}"
        await maps_repository.create_place(
            ResolvedPlace(
                place_id=ids["pickup_place_id"],
                provider="acceptance",
                provider_place_id=f"a-{suffix}",
                display_name="Điểm kiểm thử A",
                formatted_address="Hà Nội",
                latitude=21.0,
                longitude=105.8,
                types=["pickup"],
                serviceable=True,
                source_version="acceptance-v1",
            )
        )
        await maps_repository.create_place(
            ResolvedPlace(
                place_id=ids["destination_place_id"],
                provider="acceptance",
                provider_place_id=f"b-{suffix}",
                display_name="Điểm kiểm thử B",
                formatted_address="Hà Nội",
                latitude=21.1,
                longitude=105.9,
                types=["destination"],
                serviceable=True,
                source_version="acceptance-v1",
            )
        )
        await maps_repository.create_route_snapshot(
            RouteResult(
                route_id=ids["route_id"],
                pickup_place_id=ids["pickup_place_id"],
                destination_place_id=ids["destination_place_id"],
                distance_meters=12_300,
                duration_seconds=1_500,
                provider="acceptance",
                provider_version="acceptance-v1",
            )
        )
        quote_service = QuoteService(repository=repository, maps_repository=maps_repository, settings=settings)
        quote = await quote_service.issue_quote(
            user_id=ids["user_id"],
            session_id=ids["session_id"],
            pickup_place_id=ids["pickup_place_id"],
            destination_place_id=ids["destination_place_id"],
            route_id=ids["route_id"],
            vehicle_type="CAR_4",
        )
        ids["quote_id"] = str(quote["quote_id"])
        tampered = {**quote, "fare_amount": int(quote["fare_amount"]) + 1}
        try:
            await quote_service.verify_quote(tampered)
        except ValueError as exc:
            assert str(exc) == "QUOTE_INTEGRITY_INVALID"
        else:
            raise AssertionError("Tampered quote was accepted")

        booking_service = BookingService(repository=repository, quote_service=quote_service)
        booking_payload = {
            "quote_id": ids["quote_id"],
            "session_id": ids["session_id"],
            "user_id": ids["user_id"],
            "idempotency_key": f"acceptance-{suffix}",
            "pickup_place_id": ids["pickup_place_id"],
            "destination_place_id": ids["destination_place_id"],
            "vehicle_type": "CAR_4",
        }

        first, retry = await asyncio.gather(
            booking_service.create_booking_from_quote(booking_payload),
            booking_service.create_booking_from_quote(booking_payload),
        )
        assert first["booking_id"] == retry["booking_id"]
        ids["booking_id"] = str(first["booking_id"])
        await repository.get_or_create_trip(
            ids["booking_id"],
            {
                "status": "SEARCHING_DRIVER",
                "eta_minutes": 8,
                "driver_name": "Acceptance Driver",
                "vehicle": "Acceptance Vehicle",
                "license_plate": "TEST-000.00",
                "driver_rating": 5.0,
                "driver_phone": None,
            },
        )

        await reset_engine_for_tests()
        restarted_repository = PersistenceRepository()
        persisted = await restarted_repository.booking(ids["booking_id"])
        assert persisted is not None
        assert persisted["quote_id"] == ids["quote_id"]
        assert persisted["pricing_snapshot"] == quote["pricing_snapshot"]
        assert len(await restarted_repository.conversation_messages(ids["session_id"])) == 2
        restarted_maps = MapsRepository()
        assert (await restarted_maps.get_place(ids["pickup_place_id"])) is not None
        assert (await restarted_maps.get_route_snapshot(ids["route_id"]))["distance_meters"] == 12_300
        print("POSTGRES_PERSISTENCE_ACCEPTANCE=PASS")
        print(f"ALEMBIC_REVISION={revision}")
        print("QUOTE_TAMPER_REJECTION=PASS")
        print("CONCURRENT_IDEMPOTENCY=PASS")
        print("RESTART_READBACK=PASS")
        print("RLS_ENABLED=PASS")

    finally:
        await _cleanup(
            {
                "user_id": ids.get("user_id", ""),
                "session_id": ids.get("session_id", ""),
                "quote_id": ids.get("quote_id", ""),
                "booking_id": ids.get("booking_id", ""),
                "handoff_id": ids.get("handoff_id", ""),
                "call_id": ids.get("call_id", ""),
                "route_id": ids.get("route_id", ""),
                "pickup_place_id": ids.get("pickup_place_id", ""),
                "destination_place_id": ids.get("destination_place_id", ""),
            }
        )
        await reset_engine_for_tests()


if __name__ == "__main__":
    asyncio.run(main())
