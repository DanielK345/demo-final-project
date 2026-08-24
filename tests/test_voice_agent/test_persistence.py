from collections.abc import Mapping

import pytest

from src.voice_agent.persistence import DatabaseVoiceStateStore, VoiceStateConflictError
from src.voice_agent.session_data import AloSMSessionData, BookingResult, PlaceCandidate, QuoteSnapshot


class FakePersistenceRepository:
    def __init__(self) -> None:
        self.state: dict[str, object] | None = None
        self.revision = 0
        self.status = "ACTIVE"
        self.session_updates: list[dict[str, object]] = []

    async def get_voice_agent_state(self, session_id: str) -> dict[str, object]:
        return {
            "session_id": session_id,
            "user_id": "user-real",
            "status": self.status,
            "state": self.state,
            "revision": self.revision,
        }

    async def save_voice_agent_state(
        self,
        session_id: str,
        state: Mapping[str, object],
        *,
        expected_revision: int,
    ) -> dict[str, object] | None:
        if expected_revision != self.revision:
            return None
        self.state = dict(state)
        self.revision += 1
        return {"session_id": session_id, "revision": self.revision}

    async def update_session(
        self,
        session_id: str,
        updates: Mapping[str, object],
        *,
        expected_version: int | None = None,
    ) -> dict[str, object]:
        self.session_updates.append(dict(updates))
        self.status = str(updates.get("status") or self.status)
        return {"session_id": session_id, **updates}


def _userdata() -> AloSMSessionData:
    return AloSMSessionData(
        app_session_id="session-livekit",
        call_id="call-livekit",
        user_id="untrusted-participant",
        participant_identity="customer-hash",
    )


@pytest.mark.asyncio
async def test_voice_draft_survives_reconnect_and_uses_session_owner() -> None:
    repository = FakePersistenceRepository()
    store = DatabaseVoiceStateStore(repository)
    original = _userdata()
    assert await store.restore(original) is False
    candidate = PlaceCandidate(
        place_id="vinuni",
        display_name="VinUni",
        address="Gia Lâm",
        provider="test",
    )
    original.booking_draft.set_candidates("pickup", "VinUni", [candidate])
    original.booking_draft.select_place("pickup", "vinuni")
    await store.save(original)

    reconnected = _userdata()
    assert await store.restore(reconnected) is True
    assert reconnected.user_id == "user-real"
    assert reconnected.booking_draft.pickup == candidate
    assert reconnected.recovered is True
    assert reconnected.persistence_revision == 1


@pytest.mark.asyncio
async def test_voice_state_rejects_stale_concurrent_writer() -> None:
    repository = FakePersistenceRepository()
    store = DatabaseVoiceStateStore(repository)
    first = _userdata()
    second = _userdata()
    await store.restore(first)
    await store.restore(second)
    await store.save(first)
    with pytest.raises(VoiceStateConflictError):
        await store.save(second)


@pytest.mark.asyncio
async def test_completed_booking_from_older_state_is_not_restored() -> None:
    repository = FakePersistenceRepository()
    store = DatabaseVoiceStateStore(repository)
    original = _userdata()
    pickup = PlaceCandidate(
        place_id="pickup",
        display_name="VinUni",
        address="Gia Lâm",
        provider="test",
    )
    destination = PlaceCandidate(
        place_id="destination",
        display_name="Hồ Gươm",
        address="Hoàn Kiếm",
        provider="test",
    )
    draft = original.booking_draft
    draft.set_candidates("pickup", "VinUni", [pickup])
    draft.select_place("pickup", "pickup")
    draft.set_candidates("destination", "Hồ Gươm", [destination])
    draft.select_place("destination", "destination")
    draft.set_vehicle_type("CAR_4")
    draft.set_quote(
        QuoteSnapshot(
            quote_id="quote_test",
            pickup_place_id="pickup",
            destination_place_id="destination",
            vehicle_type="CAR_4",
            fare_amount=100_000,
            distance_km=10,
            eta_minutes=25,
            expires_at="2099-01-01T00:00:00+00:00",
        )
    )
    draft.request_confirmation()
    draft.confirm()
    draft.set_booking(
        BookingResult(
            booking_id="book_test",
            status="SEARCHING_DRIVER",
            estimated_fare=100_000,
            eta_minutes=25,
        )
    )
    original.lifecycle_status = "completed"
    await store.save(original)

    assert repository.session_updates[-1]["booking_id"] == "book_test"
    assert repository.session_updates[-1]["booking_lifecycle_status"] == "SUCCESS"
    assert repository.session_updates[-1]["confirmation_status"] == "confirmed"

    reconnected = _userdata()
    assert await store.restore(reconnected) is False
    assert reconnected.persistence_enabled is False


@pytest.mark.asyncio
async def test_terminal_voice_state_ends_application_session_and_is_not_restored() -> None:
    repository = FakePersistenceRepository()
    store = DatabaseVoiceStateStore(repository)
    completed = _userdata()
    completed.lifecycle_status = "completed"

    await store.save(completed)

    assert repository.session_updates[-1]["status"] == "ENDED"
    assert repository.session_updates[-1]["end_reason"] == "BOOKING_COMPLETED"
    reconnected = _userdata()
    assert await store.restore(reconnected) is False
    assert reconnected.persistence_enabled is False
