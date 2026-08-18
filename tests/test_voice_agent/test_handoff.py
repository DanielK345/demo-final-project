import pytest

from src.voice_agent.session_data import AloSMSessionData, PlaceCandidate
from src.voice_agent.tools.handoffs import HandoffToolsService


class FakeHandoffService:
    def __init__(self) -> None:
        self.payload: dict[str, object] | None = None

    async def create_handoff_durable(self, payload: dict[str, object]) -> dict[str, object]:
        self.payload = payload
        return {
            **payload,
            "handoff_id": "handoff_test",
            "status": "pending",
        }


@pytest.mark.asyncio
async def test_handoff_summary_excludes_raw_query_and_full_address() -> None:
    userdata = AloSMSessionData(
        app_session_id="session-livekit",
        call_id="call-livekit",
        user_id="user-real",
        participant_identity="customer-hash",
    )
    place = PlaceCandidate(
        place_id="pickup",
        display_name="VinUni",
        address="Địa chỉ đầy đủ không được chuyển",
        provider="test",
    )
    userdata.booking_draft.set_candidates("pickup", "câu ASR thô", [place])
    userdata.booking_draft.select_place("pickup", "pickup")
    fake = FakeHandoffService()

    result = await HandoffToolsService(fake).create(userdata, reason="Khách yêu cầu")

    assert result["handoff_id"] == "handoff_test"
    assert fake.payload is not None
    summary = str(fake.payload["summary"])
    assert "VinUni" in summary
    assert "câu ASR thô" not in summary
    assert "Địa chỉ đầy đủ" not in summary
