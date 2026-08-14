from typing import Any

import pytest

from src.agents.graph import AgentGraphAdapter
from src.agents.history import acknowledge_assistant_delivery, build_message_id
from src.agents.schemas import (
    ActionType,
    AgentAction,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import (
    AgentState,
    AssistantDeliveryEvent,
    ConversationRole,
    DeliveryStatus,
)
from src.agents.workflows.booking_models import BookingData
from src.agents.workflows.faq_models import FAQData
from src.agents.workflows.trip_lookup_models import TripLookupData


class GraphScenario:
    """Minimal Backend simulator for one session and one-action turns."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.turn_sequence = 0
        self.state = AgentState(session_id=session_id)
        self.graph = AgentGraphAdapter()

    async def user_turn(
        self,
        transcript: str,
        *,
        stt_confidence: float | None = None,
    ) -> AgentAction:
        return await self._turn(
            query=transcript,
            stt_confidence=stt_confidence,
        )

    async def tool_turn(self, result: ToolResult) -> AgentAction:
        return await self._turn(tool_result=result.model_dump(mode="json"))

    async def _turn(self, **values: Any) -> AgentAction:
        self.turn_sequence += 1
        turn_id = f"turn-{self.turn_sequence:03d}"
        response = await self.graph.ainvoke(
            {
                "session_id": self.session_id,
                "turn_id": turn_id,
                "state": self.state.model_dump(mode="json"),
                **values,
            }
        )
        action = AgentAction.model_validate(response["action"])
        self.state = self.state.apply(action.state_updates)
        if action.action_type is not ActionType.CALL_TOOL and action.message:
            history = acknowledge_assistant_delivery(
                self.state.conversation_history,
                AssistantDeliveryEvent(
                    session_id=self.session_id,
                    turn_id=turn_id,
                    message_id=build_message_id(
                        turn_id,
                        ConversationRole.ASSISTANT,
                    ),
                    status=DeliveryStatus.DELIVERED,
                ),
                session_id=self.session_id,
            )
            self.state = self.state.apply({"conversation_history": history})
        return action


def successful_result(
    action: AgentAction,
    *,
    data: dict[str, Any],
) -> ToolResult:
    assert action.tool_call is not None
    return ToolResult(
        tool_name=action.tool_call.tool_name,
        call_id=action.tool_call.call_id,
        status=ToolStatus.SUCCESS,
        data=data,
    )


@pytest.mark.asyncio
async def test_booking_happy_path_through_langgraph():
    scenario = GraphScenario("integration-booking")

    ask_pickup = await scenario.user_turn("Tôi muốn đặt xe", stt_confidence=0.98)
    assert ask_pickup.action_type is ActionType.ASK_USER
    assert scenario.state.current_workflow is WorkflowType.RIDE_BOOKING
    assert scenario.state.last_stt_confidence == 0.98
    assert scenario.state.conversation_history[-1].delivery_status is DeliveryStatus.DELIVERED

    pickup_call = await scenario.user_turn("Hồ Gươm")
    assert pickup_call.action_type is ActionType.CALL_TOOL
    assert pickup_call.tool_call is not None
    assert pickup_call.tool_call.tool_name is ToolName.SEARCH_PLACE
    assert scenario.state.pending_tool_call_id == pickup_call.tool_call.call_id

    ask_destination = await scenario.tool_turn(
        successful_result(
            pickup_call,
            data={"candidates": [{"place_id": "pickup-1", "display_name": "Hồ Gươm"}]},
        )
    )
    assert ask_destination.action_type is ActionType.ASK_USER
    assert scenario.state.pending_tool_call_id is None

    destination_call = await scenario.user_turn("Times City")
    assert destination_call.action_type is ActionType.CALL_TOOL
    ask_vehicle = await scenario.tool_turn(
        successful_result(
            destination_call,
            data={
                "candidates": [
                    {
                        "place_id": "destination-1",
                        "display_name": "Times City",
                    }
                ]
            },
        )
    )
    assert ask_vehicle.action_type is ActionType.ASK_USER
    assert "bao nhiêu người" in ask_vehicle.message

    fare_call = await scenario.user_turn("Ô tô 4 chỗ")
    assert fare_call.action_type is ActionType.CALL_TOOL
    assert fare_call.tool_call is not None
    assert fare_call.tool_call.tool_name is ToolName.ESTIMATE_FARE

    ask_phone = await scenario.tool_turn(
        successful_result(
            fare_call,
            data={
                "estimate_id": "fare-001",
                "fare_amount": 75000,
                "currency": "VND",
                "eta_minutes": 6,
            },
        )
    )
    assert ask_phone.action_type is ActionType.ASK_USER
    assert "số điện thoại" in ask_phone.message

    confirmation = await scenario.user_turn("0901234567")
    assert confirmation.action_type is ActionType.ASK_USER
    assert "xác nhận" in confirmation.message

    booking_call = await scenario.user_turn("Đúng, đặt giúp tôi")
    assert booking_call.action_type is ActionType.CALL_TOOL
    assert booking_call.tool_call is not None
    assert booking_call.tool_call.tool_name is ToolName.CREATE_BOOKING
    assert booking_call.tool_call.params == {
        "pickup_place_id": "pickup-1",
        "destination_place_id": "destination-1",
        "phone_number": "0901234567",
        "vehicle_type": "CAR_4",
        "fare_estimate_id": "fare-001",
        "idempotency_key": booking_call.tool_call.params["idempotency_key"],
    }

    completed = await scenario.tool_turn(
        successful_result(
            booking_call,
            data={
                "booking_id": "booking-001",
                "status": "CONFIRMED",
                "eta_minutes": 5,
            },
        )
    )
    assert completed.action_type is ActionType.RESPOND
    assert "5 phút" in completed.message
    assert scenario.state.current_workflow is None
    assert scenario.state.pending_tool_call_id is None
    booking_data = BookingData.model_validate(scenario.state.collected_data["booking"])
    assert booking_data.booking_id == "booking-001"


@pytest.mark.asyncio
async def test_trip_lookup_happy_path_through_langgraph():
    scenario = GraphScenario("integration-trip")

    ask_identifier = await scenario.user_turn("Tra cứu chuyến của tôi")
    assert ask_identifier.action_type is ActionType.ASK_USER

    lookup_call = await scenario.user_turn("Mã chuyến là GSM-12345")
    assert lookup_call.action_type is ActionType.CALL_TOOL
    assert lookup_call.tool_call is not None
    assert lookup_call.tool_call.tool_name is ToolName.LOOKUP_TRIP

    completed = await scenario.tool_turn(
        successful_result(
            lookup_call,
            data={
                "found": True,
                "booking_id": "GSM-12345",
                "status": "Đang đến điểm đón",
                "eta_minutes": 4,
            },
        )
    )
    assert completed.action_type is ActionType.RESPOND
    assert "Đang đến điểm đón" in completed.message
    assert "4 phút" in completed.message
    trip_data = TripLookupData.model_validate(scenario.state.collected_data["trip_lookup"])
    assert trip_data.trip_status == "Đang đến điểm đón"


@pytest.mark.asyncio
async def test_grounded_faq_through_langgraph():
    scenario = GraphScenario("integration-faq")

    retrieval_call = await scenario.user_turn("Dịch vụ hỗ trợ thanh toán thế nào?")
    assert retrieval_call.action_type is ActionType.CALL_TOOL
    assert retrieval_call.tool_call is not None
    assert retrieval_call.tool_call.tool_name is ToolName.RETRIEVE_KNOWLEDGE

    completed = await scenario.tool_turn(
        successful_result(
            retrieval_call,
            data={
                "documents": [
                    {
                        "content": "Khách có thể thanh toán bằng tiền mặt.",
                        "source": "mock-approved-faq",
                        "score": 0.92,
                    },
                    {
                        "content": "Thông tin không đủ tin cậy.",
                        "source": "mock-low-score",
                        "score": 0.3,
                    },
                ]
            },
        )
    )
    assert completed.action_type is ActionType.RESPOND
    assert completed.message == "Khách có thể thanh toán bằng tiền mặt."
    assert "không đủ tin cậy" not in completed.message
    faq_data = FAQData.model_validate(scenario.state.collected_data["faq"])
    assert faq_data.sources == ["mock-approved-faq"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("transcript", "stt_confidence", "expected_reason"),
    [
        ("Cho tôi gặp tổng đài viên", None, "USER_REQUEST"),
        ("Tôi đang gặp nguy hiểm", None, "EMERGENCY"),
        ("Tôi muốn đặt xe", 0.2, "LOW_CONFIDENCE"),
    ],
)
async def test_handoff_policies_through_langgraph(
    transcript: str,
    stt_confidence: float | None,
    expected_reason: str,
):
    scenario = GraphScenario(f"integration-handoff-{expected_reason.lower()}")

    action = await scenario.user_turn(
        transcript,
        stt_confidence=stt_confidence,
    )

    assert action.action_type is ActionType.HANDOFF
    assert scenario.state.current_workflow is WorkflowType.HUMAN_HANDOFF
    context = scenario.state.collected_data["handoff_context"]
    assert context["reason_code"] == expected_reason
    assert scenario.state.pending_tool_call_id is None


@pytest.mark.asyncio
async def test_handoff_redacts_phone_in_summary_through_langgraph():
    scenario = GraphScenario("integration-handoff-pii")

    action = await scenario.user_turn("Cho tôi gặp tổng đài viên, số của tôi là 090 123 4567")

    assert action.action_type is ActionType.HANDOFF
    summary = scenario.state.collected_data["handoff_context"]["summary"]
    assert "090 123 4567" not in summary
    assert "[REDACTED_PHONE]" in summary
