from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.backend.config import Settings
from src.backend.db.base import Base
from src.backend.maps.contracts import ResolvedPlace, RouteResult
from src.backend.repositories.maps_repository import MapsRepository
from src.backend.repositories.persistence_repository import PersistenceRepository
from src.backend.services.booking_service import BookingService
from src.backend.services.quote_service import QuoteService


@pytest.mark.asyncio
async def test_durable_quote_booking_survives_engine_restart(tmp_path: Path) -> None:
    """Real SQL round-trip: no repository, quote, or transaction mocks."""
    database_path = tmp_path / "persistence.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = PersistenceRepository(factory)
    user = await repository.create_user(
        full_name="Persistence Verification",
        phone="0900000001",
        password_hash="not-a-real-login",
        terms_version="test-terms",
        privacy_version="test-privacy",
        source_sha256="a" * 64,
    )
    session = await repository.create_session(
        user_id=str(user["user_id"]), channel="WEB", device_id="test-device", phone="0900000001"
    )
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        QUOTE_SIGNING_KEY="quote-test-key-with-at-least-thirty-two-bytes",
        FIELD_ENCRYPTION_KEY="field-test-key-with-at-least-thirty-two-bytes",
    )
    quote_service = QuoteService(repository=repository, settings=settings)
    quote = await quote_service.issue_quote(
        user_id=str(user["user_id"]),
        session_id=str(session["session_id"]),
        pickup_place_id="place_hanoi_a",
        destination_place_id="place_hanoi_b",
        vehicle_type="CAR_4",
    )
    booking_service = BookingService(repository=repository, quote_service=quote_service)
    payload = {
        "quote_id": quote["quote_id"],
        "session_id": session["session_id"],
        "user_id": user["user_id"],
        "idempotency_key": "test-create-booking-1",
        "pickup_place_id": "place_hanoi_a",
        "destination_place_id": "place_hanoi_b",
        "vehicle_type": "CAR_4",
    }
    booking = await booking_service.create_booking_from_quote(payload)
    duplicate = await booking_service.create_booking_from_quote(payload)
    assert duplicate["booking_id"] == booking["booking_id"]
    assert duplicate["status"] == "ALREADY_CREATED"
    assert booking["quoted_fare_amount"] == quote["fare_amount"]
    assert booking["pricing_snapshot"] == quote["pricing_snapshot"]
    assert booking["route_snapshot"] == quote["route_snapshot"]

    tampered = {**quote, "fare_amount": int(quote["fare_amount"]) + 1}
    with pytest.raises(ValueError, match="QUOTE_INTEGRITY_INVALID"):
        await quote_service.verify_quote(tampered)

    maps_repository = MapsRepository(factory)
    pickup_place = ResolvedPlace(
        place_id="plc_acceptance_a",
        provider="acceptance",
        provider_place_id="provider_a",
        display_name="Điểm A",
        formatted_address="Hà Nội",
        latitude=21.0,
        longitude=105.8,
        types=["pickup"],
        serviceable=True,
        source_version="test-v1",
    )
    destination_place = ResolvedPlace(
        place_id="plc_acceptance_b",
        provider="acceptance",
        provider_place_id="provider_b",
        display_name="Điểm B",
        formatted_address="Hà Nội",
        latitude=21.1,
        longitude=105.9,
        types=["destination"],
        serviceable=True,
        source_version="test-v1",
    )
    await maps_repository.create_place(pickup_place)
    await maps_repository.create_place(destination_place)
    await maps_repository.create_route_snapshot(
        RouteResult(
            route_id="route_acceptance",
            pickup_place_id=pickup_place.place_id,
            destination_place_id=destination_place.place_id,
            distance_meters=12_300,
            duration_seconds=1_500,
            provider="acceptance",
            provider_version="test-v1",
        )
    )

    booking_id = str(booking["booking_id"])
    await engine.dispose()

    restarted_engine = create_async_engine(database_url)
    restarted_repository = PersistenceRepository(async_sessionmaker(restarted_engine, expire_on_commit=False))
    persisted = await restarted_repository.booking(booking_id)
    assert persisted is not None
    assert persisted["quote_id"] == quote["quote_id"]
    assert persisted["quoted_fare_amount"] == quote["fare_amount"]
    restarted_maps = MapsRepository(async_sessionmaker(restarted_engine, expire_on_commit=False))
    assert (await restarted_maps.get_place("plc_acceptance_a")).display_name == "Điểm A"
    assert (await restarted_maps.get_route_snapshot("route_acceptance"))["distance_meters"] == 12_300
    await restarted_engine.dispose()
