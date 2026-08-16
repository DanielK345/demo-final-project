from collections import deque

import pytest

from src.agents.agent import LLMAgent
from src.agents.core.model import ModelDecision, ModelToolCall
from src.backend.services.agent_tool_executor import AgentToolExecutor
from src.backend.services.booking_service import BookingService
from src.backend.services.pricing_service import PricingService
from src.backend.services.session_service import SessionService


class _ScriptedConversationModel:
    def __init__(self, *decisions: ModelDecision) -> None:
        self.decisions = deque(decisions)

    async def decide(self, **_kwargs) -> ModelDecision:
        return self.decisions.popleft()


class _InMemoryQuoteService:
    def __init__(self, pricing: PricingService) -> None:
        self.pricing = pricing

    async def issue_quote(
        self,
        *,
        user_id: str,
        session_id: str,
        pickup_place_id: str,
        destination_place_id: str,
        vehicle_type: str,
    ) -> dict[str, object]:
        del user_id, session_id
        return self.pricing.estimate_fare(
            pickup_place_id=pickup_place_id,
            destination_place_id=destination_place_id,
            vehicle_type=vehicle_type,
        )


def _tool(name: str, **arguments: object) -> ModelDecision:
    return ModelDecision(tool_call=ModelToolCall(name, arguments))


@pytest.mark.asyncio
async def test_vinuni_to_ho_guom_can_reach_confirmation_and_create_booking():
    model = _ScriptedConversationModel(
        _tool(
            "update_booking",
            pickup_query="VinUni",
            destination_query="Hồ Gươm",
            vehicle_type="CAR_4",
        ),
        _tool("select_place", target="pickup", index=1),
        _tool("select_place", target="destination", index=2),
        _tool("confirm_booking"),
    )
    pricing = PricingService()
    executor = AgentToolExecutor(pricing=pricing, booking_service=BookingService())
    executor._durable = False
    executor._quotes = _InMemoryQuoteService(pricing)

    SessionService.sessions.clear()
    service = SessionService()
    service._durable = False
    service._agent = LLMAgent(conversation_model=model)
    service._tool_executor = executor
    session_id = service.create_session(
        "usr_hanoi",
        "WEB_VOICE",
        phone="0901234567",
    )["session_id"]

    pickup_question = await service.process_message(
        str(session_id),
        "Cho tôi xe 4 chỗ từ VinUni tới Hồ Gươm",
        source="VOICE",
    )

    assert pickup_question["action"] == "ASK_USER"
    assert pickup_question["state"]["current_step"] == "SELECT_PICKUP_CANDIDATE"
    assert "xác nhận điểm đón cụ thể" in pickup_question["message"]
    assert "Cổng chính VinUni" in pickup_question["message"]
    assert "Cổng ký túc xá VinUni" in pickup_question["message"]

    destination_question = await service.process_message(
        str(session_id),
        "Tôi chọn cổng chính VinUni",
        source="VOICE",
    )

    assert destination_question["action"] == "ASK_USER"
    assert destination_question["state"]["current_step"] == "SELECT_DESTINATION_CANDIDATE"
    assert "xác nhận điểm đến cụ thể" in destination_question["message"]
    assert "Bưu điện Hà Nội" in destination_question["message"]
    assert "Tượng đài Vua Lý Thái Tổ" in destination_question["message"]

    confirmation = await service.process_message(
        str(session_id),
        "Tôi chọn Bưu điện Hà Nội",
        source="VOICE",
    )

    progress = confirmation["state"]["booking_progress"]
    assert confirmation["action"] == "ASK_USER"
    assert confirmation["state"]["current_step"] == "CONFIRM"
    assert progress["pickup"]["label"] == "Cổng chính VinUni"
    assert progress["pickup"]["resolved"] is True
    assert progress["destination"]["label"] == "Bưu điện Hà Nội"
    assert progress["destination"]["resolved"] is True
    assert progress["vehicle_type"] == "CAR_4"
    assert progress["missing_field"] is None
    assert "đúng không" in confirmation["message"].lower()
    assert "Cổng chính VinUni" in confirmation["message"]
    assert "Bưu điện Hà Nội" in confirmation["message"]

    completed = await service.process_message(
        str(session_id),
        "Đúng, tôi xác nhận đặt chuyến này",
        source="VOICE",
    )

    assert completed["action"] == "RESPOND"
    assert completed["booking"]["booking_id"]
    assert completed["state"]["booking_lifecycle_status"] == "SUCCESS"
    assert "đặt thành công" in completed["message"]
