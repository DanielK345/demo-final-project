import pytest

from src.voice_agent.session_data import (
    BookingDraft,
    BookingResult,
    PlaceCandidate,
    QuoteSnapshot,
    vehicle_spoken_label,
)
from src.voice_agent.tools import BookingToolsService, QuoteToolsService


def _place(place_id: str, name: str) -> PlaceCandidate:
    return PlaceCandidate(
        place_id=place_id,
        display_name=name,
        address=name,
        provider="test",
        city="Hà Nội",
    )


def _quoted_draft() -> BookingDraft:
    draft = BookingDraft()
    pickup = _place("place_pickup", "VinUni")
    destination = _place("place_destination", "Hồ Gươm")
    draft.set_candidates("pickup", "VinUni", [pickup])
    draft.select_place("pickup", pickup.place_id)
    draft.set_candidates("destination", "Hồ Gươm", [destination])
    draft.select_place("destination", destination.place_id)
    draft.set_vehicle_type("CAR_4")
    draft.set_quote(
        QuoteSnapshot(
            quote_id="quote_test",
            pickup_place_id=pickup.place_id,
            destination_place_id=destination.place_id,
            vehicle_type="CAR_4",
            fare_amount=100_000,
            currency="VND",
            distance_km=10,
            eta_minutes=25,
            expires_at="2099-01-01T00:00:00+00:00",
        )
    )
    return draft


class FakeQuoteService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def issue_quote(self, **payload: object) -> dict[str, object]:
        self.calls.append(payload)
        return {
            "quote_id": "quote_durable",
            "pickup_place_id": payload["pickup_place_id"],
            "destination_place_id": payload["destination_place_id"],
            "vehicle_type": payload["vehicle_type"],
            "fare_amount": 100_000,
            "currency": "VND",
            "distance_km": 10,
            "eta_minutes": 25,
            "expires_at": "2099-01-01T00:00:00+00:00",
            "estimated": True,
        }


class FakeBookingService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create_booking_from_quote(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return {
            "booking_id": "book_durable",
            "status": "SEARCHING_DRIVER",
            "quoted_fare_amount": 100_000,
            "currency": "VND",
            "eta_minutes": 25,
        }


def test_candidate_must_come_from_current_search_result() -> None:
    draft = BookingDraft()
    draft.set_candidates("pickup", "VinUni", [_place("place_1", "VinUni")])

    with pytest.raises(ValueError, match="PLACE_CANDIDATE_NOT_IN_CURRENT_SEARCH"):
        draft.select_place("pickup", "invented-place-id")


@pytest.mark.parametrize("correction", ["pickup", "destination", "vehicle"])
def test_every_booking_correction_invalidates_quote_confirmation_and_booking(
    correction: str,
) -> None:
    draft = _quoted_draft()
    draft.request_confirmation()
    draft.confirm()
    booking = BookingResult(
        booking_id="book_test",
        status="SEARCHING_DRIVER",
        estimated_fare=100_000,
        currency="VND",
        eta_minutes=25,
    )
    draft.set_booking(booking)

    if correction == "pickup":
        replacement = _place("place_pickup_new", "Cổng chính VinUni")
        draft.set_candidates("pickup", replacement.display_name, [replacement])
        draft.select_place("pickup", replacement.place_id)
    elif correction == "destination":
        replacement = _place("place_destination_new", "Bệnh viện Bạch Mai")
        draft.set_candidates("destination", replacement.display_name, [replacement])
        draft.select_place("destination", replacement.place_id)
    else:
        draft.set_vehicle_type("CAR_7")

    assert draft.quote is None
    assert draft.confirmation_status == "not_requested"
    assert draft.confirmation_fingerprint is None
    assert draft.booking is None


@pytest.mark.asyncio
async def test_booking_requires_explicit_confirmed_state() -> None:
    draft = _quoted_draft()
    draft.request_confirmation()

    with pytest.raises(ValueError, match="EXPLICIT_CONFIRMATION_REQUIRED"):
        await BookingToolsService(FakeBookingService()).create(
            user_id="user-1",
            app_session_id="session-1",
            draft=draft,
        )


@pytest.mark.asyncio
async def test_durable_booking_uses_stable_idempotency_key_for_same_session_and_quote() -> None:
    draft = _quoted_draft()
    draft.request_confirmation()
    draft.confirm()
    backend = FakeBookingService()
    service = BookingToolsService(backend)

    first = await service.create(user_id="user-1", app_session_id="session-1", draft=draft)
    second = await service.create(user_id="user-1", app_session_id="session-1", draft=draft)

    assert first == second
    assert first.booking_id == "book_durable"
    assert backend.calls[0]["idempotency_key"] == backend.calls[1]["idempotency_key"]
    assert backend.calls[0]["quote_id"] == "quote_test"


@pytest.mark.asyncio
async def test_quote_tool_uses_existing_durable_quote_service() -> None:
    draft = _quoted_draft()
    draft.quote = None
    backend = FakeQuoteService()

    quote = await QuoteToolsService(backend).estimate(
        user_id="user-1",
        app_session_id="session-1",
        draft=draft,
    )

    assert quote.quote_id == "quote_durable"
    assert backend.calls == [
        {
            "user_id": "user-1",
            "session_id": "session-1",
            "pickup_place_id": "place_pickup",
            "destination_place_id": "place_destination",
            "vehicle_type": "CAR_4",
        }
    ]


def test_public_state_excludes_queries_and_candidate_lists() -> None:
    draft = _quoted_draft()

    public = draft.public_state()

    assert "pickup_query" not in public
    assert "destination_query" not in public
    assert "pickup_candidates" not in public
    assert public["pickup"]["display_name"] == "VinUni"  # type: ignore[index]


def test_conversation_summary_is_compact_and_uses_spoken_vehicle_label() -> None:
    draft = _quoted_draft()

    summary = draft.conversation_summary()

    assert "điểm đón VinUni" in summary
    assert "điểm đến Hồ Gươm" in summary
    assert "xe ô tô bốn chỗ" in summary
    assert "CAR_4" not in summary
    assert vehicle_spoken_label("MOTORBIKE") == "xe máy"
