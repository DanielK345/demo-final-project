from collections import deque

import pytest

from src.agents.agent import LLMAgent
from src.agents.capabilities import build_tool_registry
from src.agents.contracts.schemas import ActionType, AgentInput, ToolResult, ToolStatus, WorkflowType
from src.agents.contracts.state import AgentState, ConfirmationStatus
from src.agents.core.booking import BookingData, BookingStep
from src.agents.core.model import ConversationModelError, ModelDecision, ModelToolCall
from src.agents.core.session import TurnSession
from src.agents.tools.schemas import PlaceCandidate


class ScriptedConversationModel:
    def __init__(self, *decisions: ModelDecision) -> None:
        self.decisions = deque(decisions)
        self.contexts = []
        self.tool_sets = []

    async def decide(self, *, instructions, context, tools, exchanges=()):
        self.contexts.append(context)
        self.tool_sets.append({item["function"]["name"] for item in tools})
        return self.decisions.popleft()


class FailingConversationModel:
    async def decide(self, **_kwargs):
        raise ConversationModelError("temporary provider failure")


def tool(name: str, **arguments) -> ModelDecision:
    return ModelDecision(tool_call=ModelToolCall(name, arguments))


def apply(state: AgentState, action) -> AgentState:
    return state.apply(action.state_updates)


@pytest.mark.asyncio
async def test_active_booking_greeting_is_answered_naturally_without_becoming_a_place():
    model = ScriptedConversationModel(
        ModelDecision(message="Chào bạn! Mình vẫn đang giữ yêu cầu đặt xe. Bạn muốn đón ở đâu?")
    )
    agent = LLMAgent(conversation_model=model)
    state = AgentState(
        session_id="session-1",
        current_workflow=WorkflowType.RIDE_BOOKING,
        collected_data={"booking": BookingData(vehicle_type="CAR_4").model_dump(mode="json")},
    )

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="xin chào"),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert "Chào bạn" in action.message
    booking = BookingData.model_validate(action.state_updates["collected_data"]["booking"])
    assert booking.pickup_query is None


@pytest.mark.asyncio
async def test_greeting_does_not_start_an_empty_booking_workflow():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(ModelDecision(message="Chào bạn! Tôi có thể giúp gì?"))
    )
    state = AgentState(session_id="session-1")

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="xin chào"),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates.get("current_workflow") is None
    assert "booking" not in action.state_updates.get("collected_data", {})


@pytest.mark.asyncio
async def test_trip_lookup_remains_an_external_backend_tool():
    agent = LLMAgent(conversation_model=ScriptedConversationModel(tool("lookup_trip", booking_id="BK-123")))
    state = AgentState(session_id="session-1")

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="tra cứu chuyến BK-123"),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call.tool_name.value == "lookup_trip"
    assert action.tool_call.params == {"booking_id": "BK-123"}
    assert action.state_updates["current_workflow"] is WorkflowType.TRIP_LOOKUP


def test_only_state_valid_tools_are_exposed_to_the_model():
    state = AgentState(session_id="session-1")
    registry = build_tool_registry()
    empty = TurnSession.load(state, event={})
    empty_names = {tool["function"]["name"] for tool in registry.definitions(empty)}

    assert "respond" in empty_names
    assert "update_booking" in empty_names
    assert "confirm_booking" not in empty_names
    assert "search_pickup" not in empty_names

    booking = BookingData(pickup_query="Chợ Bến Thành")
    session = TurnSession.load(
        AgentState(session_id="session-1", collected_data={"booking": booking.model_dump(mode="json")}),
        event={},
    )
    names = {tool["function"]["name"] for tool in registry.definitions(session)}
    assert "search_pickup" in names
    assert "confirm_booking" not in names


@pytest.mark.asyncio
async def test_typed_respond_tool_controls_whether_agent_expects_an_answer():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(
            tool("respond", message="Chào bạn! Tôi có thể giúp gì?", expects_response=True)
        )
    )

    action = await agent.handle(
        AgentInput(session_id="session-1", turn_id="turn-1", transcript="xin chào"),
        AgentState(session_id="session-1"),
    )

    assert action.action_type is ActionType.ASK_USER
    assert action.message == "Chào bạn! Tôi có thể giúp gì?"


@pytest.mark.asyncio
async def test_trip_result_is_reduced_to_typed_state_then_spoken_by_model():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(
            tool("respond", message="Chuyến BK-123 đang đến, dự kiến 5 phút.", expects_response=False)
        )
    )
    state = AgentState(
        session_id="session-1",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step="WAITING_FOR_TRIP_RESULT",
        pending_tool_call_id="lookup-1",
        pending_tool_name="lookup_trip",
    )

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="tool-1",
            tool_result=ToolResult(
                tool_name="lookup_trip",
                call_id="lookup-1",
                status=ToolStatus.SUCCESS,
                data={"found": True, "booking_id": "BK-123", "status": "ARRIVING", "eta_minutes": 5},
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.RESPOND
    assert action.state_updates["current_workflow"] is None
    assert action.state_updates["collected_data"]["trip_lookup"]["status"] == "ARRIVING"


@pytest.mark.asyncio
async def test_faq_response_is_grounded_in_current_backend_documents():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(
            tool("respond", message="Theo chính sách hiện hành, bạn được miễn phí chờ 5 phút.", expects_response=False)
        )
    )
    state = AgentState(
        session_id="session-1",
        current_workflow=WorkflowType.FAQ,
        current_step="WAITING_FOR_KNOWLEDGE",
        pending_tool_call_id="rag-1",
        pending_tool_name="retrieve_knowledge",
        collected_data={"faq": {"question": "chờ miễn phí bao lâu"}},
    )

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="tool-1",
            tool_result=ToolResult(
                tool_name="retrieve_knowledge",
                call_id="rag-1",
                status=ToolStatus.SUCCESS,
                data={
                    "documents": [
                        {
                            "content": "Miễn phí chờ 5 phút",
                            "source": "policy/2026",
                            "score": 0.95,
                            "citation_id": "wait-policy",
                        },
                        {"content": "Nội dung yếu", "source": "old", "score": 0.2},
                    ]
                },
            ),
        ),
        state,
    )

    faq = action.state_updates["collected_data"]["faq"]
    assert faq["sources"] == ["policy/2026"]
    assert faq["citations"] == ["wait-policy"]
    assert faq["answer"] == action.message
    assert action.state_updates["current_workflow"] is None


@pytest.mark.asyncio
async def test_handoff_contains_safe_structured_conversation_context():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(tool("handoff", reason="Khách yêu cầu gặp người thật"))
    )
    state = AgentState(session_id="session-1", current_workflow=WorkflowType.RIDE_BOOKING)

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="cho tôi gặp tổng đài viên"),
        state,
    )

    assert action.action_type is ActionType.HANDOFF
    context = action.state_updates["collected_data"]["handoff"]
    assert context["reason"] == "Khách yêu cầu gặp người thật"
    assert context["source_workflow"] == "RIDE_BOOKING"


@pytest.mark.asyncio
async def test_transient_model_failure_keeps_state_and_only_handoffs_after_threshold():
    agent = LLMAgent(conversation_model=FailingConversationModel())
    state = AgentState(
        session_id="session-1",
        current_workflow=WorkflowType.RIDE_BOOKING,
        collected_data={"booking": BookingData(destination_query="bệnh viện").model_dump(mode="json")},
    )

    first = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="đón ở VinUni"),
        state,
    )
    state = apply(state, first)
    state_after_first_failure = state
    second = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-2", transcript="thử lại"),
        state,
    )
    state = apply(state, second)
    third = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-3", transcript="thử lại"),
        state,
    )

    assert first.action_type is ActionType.ASK_USER
    assert second.action_type is ActionType.ASK_USER
    assert first.state_updates["model_failure_count"] == 1
    assert second.state_updates["model_failure_count"] == 2
    assert state_after_first_failure.collected_data["booking"]["destination_query"] == "bệnh viện"
    assert third.action_type is ActionType.HANDOFF
    assert third.state_updates["model_failure_count"] == 3


@pytest.mark.asyncio
async def test_not_found_place_is_not_searched_repeatedly_without_a_new_query():
    model = ScriptedConversationModel(
        tool("update_booking", destination_query="bệnh viện"),
        tool("search_destination"),
        tool(
            "respond",
            message="Bạn muốn đến bệnh viện nào ạ?",
            expects_response=True,
        ),
    )
    agent = LLMAgent(conversation_model=model)
    state = AgentState(session_id="session-1")

    search = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="đi bệnh viện"),
        state,
    )
    state = apply(state, search)
    answer = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="tool-1",
            tool_result=ToolResult(
                tool_name="search_place",
                call_id=search.tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data={"candidates": []},
            ),
        ),
        state,
    )

    assert answer.action_type is ActionType.ASK_USER
    assert "bệnh viện nào" in answer.message
    assert "search_destination" not in model.tool_sets[-1]
    booking = answer.state_updates["collected_data"]["booking"]
    assert booking["destination_resolution"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_low_stt_confidence_is_repaired_before_calling_the_model():
    model = ScriptedConversationModel(ModelDecision(message="should not be used"))
    agent = LLMAgent(conversation_model=model)

    action = await agent.handle(
        AgentInput(
            session_id="session-1",
            turn_id="turn-1",
            transcript="không rõ",
            stt_confidence=0.2,
        ),
        AgentState(session_id="session-1"),
    )

    assert action.action_type is ActionType.ASK_USER
    assert "chưa nghe rõ" in action.message
    assert model.contexts == []
    assert action.state_updates["last_stt_confidence"] == 0.2


@pytest.mark.asyncio
async def test_repeated_low_stt_confidence_handoffs_without_calling_the_model():
    model = ScriptedConversationModel(ModelDecision(message="should not be used"))
    agent = LLMAgent(conversation_model=model)
    state = AgentState(session_id="session-1", last_stt_confidence=0.2)

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-2",
            transcript="vẫn không rõ",
            stt_confidence=0.2,
        ),
        state,
    )

    assert action.action_type is ActionType.HANDOFF
    assert action.state_updates["current_workflow"] is WorkflowType.HUMAN_HANDOFF
    assert model.contexts == []


@pytest.mark.asyncio
async def test_completed_booking_tool_result_replay_does_not_call_model_or_book_again():
    model = ScriptedConversationModel(ModelDecision(message="should not be used"))
    agent = LLMAgent(conversation_model=model)
    booking = BookingData(
        booking_id="BK-1",
        booking_status="CONFIRMED",
        completed_booking_call_id="create-call-1",
    )
    state = AgentState(
        session_id="session-1",
        collected_data={"booking": booking.model_dump(mode="json")},
    )

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="tool-replay",
            tool_result=ToolResult(
                tool_name="create_booking",
                call_id="create-call-1",
                status=ToolStatus.SUCCESS,
                data={"booking_id": "BK-1", "status": "CONFIRMED"},
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.RESPOND
    assert "trước đó" in action.message
    assert model.contexts == []


@pytest.mark.asyncio
async def test_user_can_abandon_booking_only_after_explicit_confirmation():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(
            tool("request_abandon_confirmation"),
            tool("confirm_abandon_booking"),
        )
    )
    state = AgentState(
        session_id="session-1",
        current_workflow=WorkflowType.RIDE_BOOKING,
        collected_data={"booking": BookingData(pickup_query="Bến Thành").model_dump(mode="json")},
    )

    request = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="tôi không muốn đặt xe"),
        state,
    )
    state = apply(state, request)
    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-2", transcript="đúng, dừng đi"),
        state,
    )

    assert request.action_type is ActionType.ASK_USER
    assert "booking" in request.state_updates["collected_data"]
    assert action.action_type is ActionType.RESPOND
    assert action.state_updates["current_workflow"] is None
    assert "booking" not in action.state_updates["collected_data"]


@pytest.mark.asyncio
async def test_ambiguous_abandonment_can_be_corrected_without_losing_booking_memory():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(
            tool("request_abandon_confirmation"),
            tool("keep_booking"),
            tool(
                "respond",
                message="Mình vẫn giữ chuyến đến Times City. Bạn muốn chọn xe nào?",
                expects_response=True,
            ),
        )
    )
    booking = BookingData(
        pickup_query="Phố đi bộ Hồ Gươm",
        pickup={"place_id": "p1", "display_name": "Phố đi bộ Hồ Gươm"},
        destination_query="Times City",
        destination={"place_id": "p2", "display_name": "Times City"},
        passenger_count=2,
    )
    state = AgentState(
        session_id="session-1",
        current_workflow=WorkflowType.RIDE_BOOKING,
        collected_data={"booking": booking.model_dump(mode="json")},
    )

    request = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="tôi muốn đi ngủ"),
        state,
    )
    state = apply(state, request)
    retained = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-2",
            transcript="tôi muốn ngủ trên xe, không phải hủy",
        ),
        state,
    )

    saved = retained.state_updates["collected_data"]["booking"]
    assert retained.action_type is ActionType.ASK_USER
    assert saved["pickup"]["display_name"] == "Phố đi bộ Hồ Gươm"
    assert saved["destination"]["display_name"] == "Times City"
    assert saved["passenger_count"] == 2


@pytest.mark.asyncio
async def test_vehicle_correction_updates_typed_state_before_next_backend_call():
    model = ScriptedConversationModel(
        tool("update_booking", vehicle_type="CAR_4"),
        tool("estimate_fare"),
    )
    agent = LLMAgent(conversation_model=model)
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "Bến Thành"},
            "destination": {"place_id": "p2", "display_name": "Sân bay Tân Sơn Nhất"},
            "vehicle_type": "CAR_7",
            "fare_estimate_id": "fare-7",
            "estimated_fare_amount": 105000,
            "estimated_currency": "VND",
            "phone_number": "0387018233",
        }
    )
    state = AgentState(
        session_id="session-1",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step=BookingStep.CONFIRM.value,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
        collected_data={"booking": data.model_dump(mode="json")},
    )

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="thôi 4 chỗ đi"),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call.params["vehicle_type"] == "CAR_4"
    booking = BookingData.model_validate(action.state_updates["collected_data"]["booking"])
    assert booking.vehicle_type == "CAR_4"
    assert booking.fare_estimate_id is None


@pytest.mark.asyncio
async def test_explicit_vehicle_with_resolved_route_estimates_without_asking_passengers_or_luggage():
    model = ScriptedConversationModel(
        tool("update_booking", vehicle_type="CAR_4"),
        ModelDecision(
            message="Bạn đi bao nhiêu người và có bao nhiêu hành lý?",
        ),
    )
    agent = LLMAgent(conversation_model=model)
    data = BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "VinUniversity"},
            "destination": {"place_id": "p2", "display_name": "Hồ Hoàn Kiếm"},
        }
    )
    state = AgentState(
        session_id="session-1",
        current_workflow=WorkflowType.RIDE_BOOKING,
        collected_data={"booking": data.model_dump(mode="json")},
    )

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-1", transcript="xe 4 chỗ"),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call.tool_name.value == "estimate_fare"
    assert action.tool_call.params == {
        "pickup_place_id": "p1",
        "destination_place_id": "p2",
        "vehicle_type": "CAR_4",
    }
    assert len(model.contexts) == 1


@pytest.mark.asyncio
async def test_complete_route_update_keeps_explicit_vehicle_type():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(
            tool(
                "update_booking",
                pickup_query="VinUni",
                destination_query="Hồ Gươm",
                vehicle_type="CAR_4",
            ),
            tool("search_pickup"),
        )
    )

    action = await agent.handle(
        AgentInput(
            session_id="session-hanoi-route",
            turn_id="turn-1",
            transcript="Cho tôi xe 4 chỗ từ VinUni tới Hồ Gươm",
        ),
        AgentState(session_id="session-hanoi-route"),
    )

    booking = BookingData.model_validate(action.state_updates["collected_data"]["booking"])
    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call.tool_name.value == "search_place"
    assert action.tool_call.params == {"query": "VinUni"}
    assert booking.destination_query == "Hồ Gươm"
    assert booking.vehicle_type == "CAR_4"


@pytest.mark.asyncio
async def test_complete_booking_conversation_uses_backend_tool_results():
    model = ScriptedConversationModel(
        tool(
            "update_booking",
            pickup_query="Chợ Bến Thành",
            destination_query="Sân bay Tân Sơn Nhất",
            passenger_count=2,
            phone_number="0387018233",
        ),
        tool("request_vehicle_options"),
        tool("select_vehicle", option_id="car-4"),
        tool("confirm_booking"),
    )
    agent = LLMAgent(conversation_model=model)
    state = AgentState(session_id="session-full")

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-1",
            transcript="Đón tôi ở Chợ Bến Thành đi sân bay, 2 người, số 0387018233.",
        ),
        state,
    )
    assert action.tool_call.tool_name.value == "search_place"
    state = apply(state, action)

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="tool-1",
            tool_result=ToolResult(
                tool_name=state.pending_tool_name,
                call_id=state.pending_tool_call_id,
                status=ToolStatus.SUCCESS,
                data={"candidates": [{"place_id": "p1", "display_name": "Chợ Bến Thành"}]},
            ),
        ),
        state,
    )
    state = apply(state, action)

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="tool-2",
            tool_result=ToolResult(
                tool_name=state.pending_tool_name,
                call_id=state.pending_tool_call_id,
                status=ToolStatus.SUCCESS,
                data={"candidates": [{"place_id": "p2", "display_name": "Sân bay Tân Sơn Nhất"}]},
            ),
        ),
        state,
    )
    state = apply(state, action)

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="tool-3",
            tool_result=ToolResult(
                tool_name=state.pending_tool_name,
                call_id=state.pending_tool_call_id,
                status=ToolStatus.SUCCESS,
                data={
                    "options": [
                        {
                            "option_id": "car-4",
                            "vehicle_type": "CAR_4",
                            "display_name": "Ô tô 4 chỗ",
                            "capacity": 4,
                            "estimate_id": "fare-1",
                            "fare_amount": 75000,
                            "currency": "VND",
                        }
                    ]
                },
            ),
        ),
        state,
    )
    assert action.action_type is ActionType.ASK_USER
    assert "Bạn xác nhận" in action.message
    state = apply(state, action)

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-2", transcript="xác nhận"),
        state,
    )
    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call.tool_name.value == "create_booking"
    state = apply(state, action)

    action = await agent.handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="tool-4",
            tool_result=ToolResult(
                tool_name=state.pending_tool_name,
                call_id=state.pending_tool_call_id,
                status=ToolStatus.SUCCESS,
                data={"booking_id": "BK-1", "status": "CONFIRMED", "eta_minutes": 5},
            ),
        ),
        state,
    )
    assert action.action_type is ActionType.RESPOND
    assert "thành công" in action.message
    assert action.state_updates["current_workflow"] is None


@pytest.mark.asyncio
async def test_pending_booking_confirmation_uses_policy_gate_for_natural_yes():
    agent = LLMAgent(conversation_model=ScriptedConversationModel(ModelDecision(message="model should not speak")))
    booking = BookingData(
        pickup=PlaceCandidate(place_id="place-vinuni", display_name="VinUniversity"),
        destination=PlaceCandidate(place_id="place-ho-guom", display_name="Hồ Hoàn Kiếm"),
        vehicle_type="MOTORBIKE",
        selected_vehicle_option_id="bike-1",
        fare_estimate_id="fare-1",
        estimated_fare_amount=45000,
        estimated_currency="VND",
        passenger_count=1,
        phone_number="0387018233",
    )
    state = AgentState(
        session_id="session-confirm",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step=BookingStep.CONFIRM.value,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
        collected_data={"booking": booking.model_dump(mode="json")},
    )

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-confirm", transcript="ừ"),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name.value == "create_booking"
    assert action.tool_call.params["pickup_place_id"] == "place-vinuni"
    assert action.tool_call.params["destination_place_id"] == "place-ho-guom"
    assert action.state_updates["confirmation"] is ConfirmationStatus.CONFIRMED
    assert agent._model_agent.model.contexts == []


@pytest.mark.asyncio
async def test_abandon_confirmation_keeps_booking_when_user_says_book_it():
    agent = LLMAgent(conversation_model=ScriptedConversationModel(ModelDecision(message="model should not speak")))
    booking = BookingData(
        pickup=PlaceCandidate(place_id="place-vinuni", display_name="VinUniversity"),
        destination=PlaceCandidate(place_id="place-ho-guom", display_name="Hồ Hoàn Kiếm"),
        vehicle_type="MOTORBIKE",
        selected_vehicle_option_id="bike-1",
        fare_estimate_id="fare-1",
        estimated_fare_amount=45000,
        estimated_currency="VND",
        passenger_count=1,
        phone_number="0387018233",
    )
    state = AgentState(
        session_id="session-abandon",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="CONFIRM_ABANDON",
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
        collected_data={"booking": booking.model_dump(mode="json")},
    )

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-keep", transcript="đặt xe đi"),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert "Bạn xác nhận đặt xe" in action.message
    assert action.state_updates["current_step"] == BookingStep.CONFIRM.value
    assert action.state_updates["confirmation"] is ConfirmationStatus.AWAITING_CONFIRMATION
    assert "booking" in action.state_updates.get("collected_data", state.collected_data)
    assert agent._model_agent.model.contexts == []


@pytest.mark.asyncio
async def test_rebook_from_cancelled_trip_starts_a_fresh_draft_without_old_side_effects():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(
            tool("start_rebook"),
            tool("request_vehicle_options"),
        )
    )
    booking = BookingData(
        pickup_query="VinUniversity",
        pickup=PlaceCandidate(place_id="place-vinuni", display_name="VinUniversity"),
        destination_query="Hồ Gươm",
        destination=PlaceCandidate(place_id="place-ho-guom", display_name="Hồ Hoàn Kiếm"),
        vehicle_type="CAR_4",
        selected_vehicle_option_id="car-4",
        vehicle_display_name="Ô tô 4 chỗ",
        fare_estimate_id="fare-old",
        estimated_fare_amount=75000,
        estimated_currency="VND",
        passenger_count=4,
        luggage_count=2,
        phone_number="0387018233",
        booking_id="DEMO-BOOKING-001",
        booking_status="CANCELLED",
        completed_booking_call_id="create-1",
        completed_cancellation_call_id="cancel-1",
    )
    state = AgentState(
        session_id="session-rebook",
        collected_data={"booking": booking.model_dump(mode="json")},
    )

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-rebook", transcript="đặt lại chuyến vừa hủy"),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name.value == "get_vehicle_options"
    updated = BookingData.model_validate(action.state_updates["collected_data"]["booking"])
    assert updated.pickup.display_name == "VinUniversity"
    assert updated.destination.display_name == "Hồ Hoàn Kiếm"
    assert updated.passenger_count == 4
    assert updated.luggage_count == 2
    assert updated.phone_number == "0387018233"
    assert updated.booking_id is None
    assert updated.booking_status is None
    assert updated.completed_booking_call_id is None
    assert updated.completed_cancellation_call_id is None
    assert updated.fare_estimate_id is None
    assert updated.vehicle_type is None
    assert updated.selected_vehicle_option_id is None


@pytest.mark.asyncio
async def test_update_after_completed_booking_converts_it_to_draft_and_searches_changed_destination_once():
    agent = LLMAgent(
        conversation_model=ScriptedConversationModel(
            tool("update_booking", destination_query="Times City"),
            tool("search_destination"),
        )
    )
    booking = BookingData(
        pickup_query="VinUniversity",
        pickup=PlaceCandidate(place_id="place-vinuni", display_name="VinUniversity"),
        destination_query="Hồ Gươm",
        destination=PlaceCandidate(place_id="place-ho-guom", display_name="Hồ Hoàn Kiếm"),
        vehicle_type="CAR_4",
        selected_vehicle_option_id="car-4",
        fare_estimate_id="fare-old",
        estimated_fare_amount=75000,
        estimated_currency="VND",
        passenger_count=4,
        luggage_count=2,
        phone_number="0387018233",
        booking_id="DEMO-BOOKING-001",
        booking_status="CANCELLED",
        completed_cancellation_call_id="cancel-1",
    )
    state = AgentState(
        session_id="session-rebook-change",
        collected_data={"booking": booking.model_dump(mode="json")},
    )

    action = await agent.handle(
        AgentInput(session_id=state.session_id, turn_id="turn-change", transcript="đổi điểm đến thành Times City"),
        state,
    )

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name.value == "search_place"
    assert action.tool_call.params == {"query": "Times City"}
    updated = BookingData.model_validate(action.state_updates["collected_data"]["booking"])
    assert updated.booking_id is None
    assert updated.booking_status is None
    assert updated.destination is None
    assert updated.destination_query == "Times City"
    assert updated.fare_estimate_id is None
    assert updated.vehicle_type is None
