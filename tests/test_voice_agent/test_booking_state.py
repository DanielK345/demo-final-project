import pytest

from src.voice_agent.session_data import BookingDraft, PlaceCandidate, vehicle_spoken_label
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
    draft.set_quote(QuoteToolsService().estimate(draft))
    return draft


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
    booking = BookingToolsService().create(app_session_id="session-1", draft=draft)
    draft.set_booking(booking)

    if correction == "pickup":
        replacement = _place("place_pickup_new", "Cổng chính VinUni")
        draft.unlock_field("pickup")
        draft.set_candidates("pickup", replacement.display_name, [replacement])
        draft.select_place("pickup", replacement.place_id)
    elif correction == "destination":
        replacement = _place("place_destination_new", "Bệnh viện Bạch Mai")
        draft.unlock_field("destination")
        draft.set_candidates("destination", replacement.display_name, [replacement])
        draft.select_place("destination", replacement.place_id)
    else:
        draft.unlock_field("vehicle_type")
        draft.set_vehicle_type("CAR_7")

    assert draft.quote is None
    assert draft.confirmation_status == "not_requested"
    assert draft.confirmation_fingerprint is None
    assert draft.booking is None


def test_booking_requires_explicit_confirmed_state() -> None:
    draft = _quoted_draft()
    draft.request_confirmation()

    with pytest.raises(ValueError, match="EXPLICIT_CONFIRMATION_REQUIRED"):
        BookingToolsService().create(app_session_id="session-1", draft=draft)


def test_demo_booking_is_idempotent_for_same_session_and_quote() -> None:
    draft = _quoted_draft()
    draft.request_confirmation()
    draft.confirm()
    service = BookingToolsService()

    first = service.create(app_session_id="session-1", draft=draft)
    second = service.create(app_session_id="session-1", draft=draft)

    assert first == second
    assert first.booking_id.startswith("demo_")


def test_public_state_excludes_queries_and_candidate_lists() -> None:
    draft = _quoted_draft()

    public = draft.public_state()

    assert "pickup_query" not in public
    assert "destination_query" not in public
    assert "pickup_candidates" not in public
    assert public["pickup"]["display_name"] == "VinUni"  # type: ignore[index]
    assert public["locked_fields"] == ["destination", "pickup", "vehicle_type"]


def test_selected_fields_cannot_be_overwritten_without_explicit_unlock() -> None:
    draft = _quoted_draft()
    original_pickup = draft.pickup
    original_destination = draft.destination

    with pytest.raises(ValueError, match="BOOKING_FIELD_LOCKED:pickup"):
        draft.set_candidates("pickup", "Hồ Tây", [_place("ho-tay", "Hồ Tây")])
    with pytest.raises(ValueError, match="BOOKING_FIELD_LOCKED:vehicle_type"):
        draft.set_vehicle_type("CAR_7")

    assert draft.pickup == original_pickup
    assert draft.destination == original_destination
    assert draft.vehicle_type == "CAR_4"


def test_changing_one_unlocked_field_preserves_and_locks_all_other_fields() -> None:
    draft = _quoted_draft()
    original_pickup = draft.pickup
    replacement = _place("ho-tay", "Hồ Tây")

    draft.unlock_field("destination")
    draft.set_candidates("destination", "Hồ Tây", [replacement])

    # Searching does not erase the previously confirmed value while the user is
    # still choosing a replacement candidate.
    assert draft.destination is not None
    assert draft.destination.display_name == "Hồ Gươm"
    assert draft.pickup == original_pickup
    assert draft.vehicle_type == "CAR_4"

    draft.select_place("destination", replacement.place_id)

    assert draft.destination == replacement
    assert draft.pickup == original_pickup
    assert draft.vehicle_type == "CAR_4"
    assert draft.locked_fields == frozenset({"pickup", "destination", "vehicle_type"})


def test_reselecting_same_value_relocks_field_before_quote() -> None:
    draft = _quoted_draft()
    assert draft.destination is not None
    destination_id = draft.destination.place_id

    draft.unlock_field("destination")
    with pytest.raises(ValueError, match="BOOKING_FIELDS_NOT_LOCKED"):
        draft.set_quote(QuoteToolsService().estimate(draft))

    draft.set_candidates("destination", "Hồ Gươm", [draft.destination])
    draft.select_place("destination", destination_id)
    draft.set_quote(QuoteToolsService().estimate(draft))

    assert "destination" in draft.locked_fields
    assert draft.quote is not None


def test_conversation_summary_is_compact_and_uses_spoken_vehicle_label() -> None:
    draft = _quoted_draft()

    summary = draft.conversation_summary()

    assert "điểm đón đã khóa VinUni" in summary
    assert "điểm đến đã khóa Hồ Gươm" in summary
    assert "xe ô tô bốn chỗ" in summary
    assert "CAR_4" not in summary
    assert vehicle_spoken_label("MOTORBIKE") == "xe máy"
