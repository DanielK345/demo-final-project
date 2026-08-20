from collections.abc import Mapping

import pytest

from src.voice_agent.persistence import DatabaseVoiceStateStore, VoiceStateConflictError
from src.voice_agent.session_data import AloSMSessionData, PlaceCandidate
from src.voice_agent.tools import BookingToolsService, QuoteToolsService


class FakePersistenceRepository:
    def __init__(self) -> None:
        self.state: dict[str, object] | None = None
        self.revision = 0

    async def get_voice_agent_state(self, session_id: str) -> dict[str, object]:
        return {
            "session_id": session_id,
            "user_id": "user-real",
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
async def test_completed_booking_restores_without_creating_a_second_result() -> None:
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
    draft.set_quote(QuoteToolsService().estimate(draft))
    draft.request_confirmation()
    draft.confirm()
    booking_service = BookingToolsService()
    booking = booking_service.create(app_session_id=original.app_session_id, draft=draft)
    draft.set_booking(booking)
    await store.save(original)

    reconnected = _userdata()
    assert await store.restore(reconnected) is True
    restored = reconnected.booking_draft
    assert restored.booking == booking
    assert restored.locked_fields == frozenset({"pickup", "destination", "vehicle_type"})
    assert booking_service.create(app_session_id=reconnected.app_session_id, draft=restored) == booking
