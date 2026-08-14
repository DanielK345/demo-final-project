import pytest

from src.agents.router import AgentRouter
from src.agents.schemas import (
    ActionType,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.workflows.handoff import HandoffReason, HandoffWorkflow


@pytest.mark.parametrize(
    ("agent_input", "state"),
    [
        (
            AgentInput(
                session_id="session-001",
                turn_id="turn-001",
                transcript="Tôi đang đặt xe nhưng muốn gặp tổng đài viên",
            ),
            AgentState(
                session_id="session-001",
                current_workflow=WorkflowType.RIDE_BOOKING,
            ),
        ),
        (
            AgentInput(session_id="session-001", turn_id="turn-001", transcript="Tôi cần hỗ trợ"),
            AgentState(session_id="session-001", retry_count=3),
        ),
        (
            AgentInput(
                session_id="session-001",
                turn_id="turn-001",
                transcript="Tôi cần hỗ trợ",
                stt_confidence=0.2,
            ),
            AgentState(session_id="session-001"),
        ),
    ],
)
def test_router_applies_handoff_policy(
    agent_input: AgentInput,
    state: AgentState,
):
    assert AgentRouter().route(agent_input, state) is WorkflowType.HUMAN_HANDOFF


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("transcript", "expected_reason"),
    [
        ("Cho tôi gặp tổng đài viên", HandoffReason.USER_REQUEST),
        ("Tôi muốn khiếu nại tài xế", HandoffReason.COMPLAINT),
        ("Tôi đang gặp nguy hiểm", HandoffReason.EMERGENCY),
    ],
)
async def test_handoff_detects_realtime_reason(
    transcript: str,
    expected_reason: HandoffReason,
):
    action = await HandoffWorkflow().handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript=transcript),
        AgentState(session_id="session-001"),
    )

    context = action.state_updates["collected_data"]["handoff_context"]
    assert action.action_type is ActionType.HANDOFF
    assert action.tool_call is None
    assert context["reason_code"] == expected_reason.value
    assert expected_reason.value in action.reason


@pytest.mark.asyncio
async def test_handoff_detects_retry_limit():
    action = await HandoffWorkflow().handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript="Tôi không biết"),
        AgentState(session_id="session-001", retry_count=3),
    )

    context = action.state_updates["collected_data"]["handoff_context"]
    assert context["reason_code"] == HandoffReason.RETRY_LIMIT.value


@pytest.mark.asyncio
async def test_handoff_detects_low_stt_confidence():
    action = await HandoffWorkflow().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tôi cần hỗ trợ",
            stt_confidence=0.2,
        ),
        AgentState(session_id="session-001"),
    )

    context = action.state_updates["collected_data"]["handoff_context"]
    assert context["reason_code"] == HandoffReason.LOW_CONFIDENCE.value


@pytest.mark.asyncio
async def test_handoff_detects_critical_tool_error():
    tool_result = ToolResult(
        tool_name=ToolName.CREATE_BOOKING,
        call_id="session-001:create-booking:1",
        status=ToolStatus.ERROR,
        error="booking service unavailable",
    )

    action = await HandoffWorkflow().handle(
        AgentInput(session_id="session-001", turn_id="turn-001", tool_result=tool_result),
        AgentState(
            session_id="session-001",
            current_workflow=WorkflowType.HUMAN_HANDOFF,
            pending_tool_call_id=tool_result.call_id,
            pending_tool_name=ToolName.CREATE_BOOKING,
        ),
    )

    context = action.state_updates["collected_data"]["handoff_context"]
    assert context["reason_code"] == HandoffReason.CRITICAL_TOOL_ERROR.value
    assert context["tool_result"]["call_id"] == tool_result.call_id
    assert action.state_updates["pending_tool_call_id"] is None


@pytest.mark.asyncio
async def test_handoff_preserves_relevant_context():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="CONFIRM",
        collected_data={
            "pickup": "Times City",
            "destination": "Hồ Gươm",
        },
        retry_count=1,
    )

    action = await HandoffWorkflow().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Cho tôi gặp tổng đài viên",
            stt_confidence=0.98,
        ),
        state,
    )

    updated_data = action.state_updates["collected_data"]
    context = updated_data["handoff_context"]
    assert updated_data["pickup"] == "Times City"
    assert updated_data["destination"] == "Hồ Gươm"
    assert context["session_id"] == "session-001"
    assert context["source_workflow"] == WorkflowType.RIDE_BOOKING.value
    assert context["source_step"] == "CONFIRM"
    assert context["business_data"] == state.collected_data
    assert state.collected_data == {
        "pickup": "Times City",
        "destination": "Hồ Gươm",
    }


@pytest.mark.asyncio
async def test_handoff_redacts_nested_phone_and_booking_id():
    state = AgentState(
        session_id="session-001",
        collected_data={
            "booking": {
                "phone_number": "0901234567",
                "booking_id": "GSM-12345",
                "booking_status": "CONFIRMED",
            }
        },
    )

    action = await HandoffWorkflow().handle(
        AgentInput(
            session_id=state.session_id,
            turn_id="turn-001",
            transcript="Cho tôi gặp tổng đài viên",
        ),
        state,
    )
    business_data = action.state_updates["collected_data"]["handoff_context"]["business_data"]

    assert business_data["booking"]["phone_number"] == "[REDACTED_PHONE]"
    assert business_data["booking"]["booking_id"] == "[REDACTED_BOOKING_ID]"
    assert business_data["booking"]["booking_status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_handoff_rejects_state_from_another_session():
    with pytest.raises(ValueError, match="same session"):
        await HandoffWorkflow().handle(
            AgentInput(
                session_id="session-001",
                turn_id="turn-001",
                transcript="Cho tôi gặp tổng đài viên",
            ),
            AgentState(session_id="session-002"),
        )
