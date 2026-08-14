import pytest
from pydantic import ValidationError

from src.agents.agent import LLMAgent
from src.agents.schemas import (
    ActionType,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState, ConfirmationStatus
from src.agents.state_types import InterruptedWorkflow, InterruptionReason
from src.agents.workflows.booking_models import BookingData, BookingStep
from src.agents.workflows.faq_models import FAQStep
from src.agents.workflows.trip_lookup_models import TripLookupStep


def apply_action(state: AgentState, action) -> AgentState:
    return state.apply(action.state_updates)


def complete_locations() -> BookingData:
    return BookingData.model_validate(
        {
            "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
            "destination": {"place_id": "d1", "display_name": "Times City"},
            "vehicle_type": "CAR_4",
            "fare_estimate_id": "fare-001",
            "estimated_fare_amount": 75000,
            "estimated_currency": "VND",
        }
    )


def booking_state(*, step: BookingStep = BookingStep.COLLECT_PHONE) -> AgentState:
    return AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step=step,
        collected_data={
            "booking": complete_locations().model_dump(mode="json"),
            "custom": {"keep": True},
        },
        confirmation=(
            ConfirmationStatus.AWAITING_CONFIRMATION
            if step is BookingStep.CONFIRM
            else ConfirmationStatus.NOT_REQUESTED
        ),
        retry_count=1,
    )


def test_interrupted_workflow_rejects_non_resumable_workflow():
    with pytest.raises(ValidationError, match="only booking and trip lookup"):
        InterruptedWorkflow(
            workflow=WorkflowType.FAQ,
            step="WAITING_FOR_KNOWLEDGE",
            reason=InterruptionReason.FAQ,
        )

    with pytest.raises(ValidationError, match="step is not resumable"):
        InterruptedWorkflow(
            workflow=WorkflowType.RIDE_BOOKING,
            step=BookingStep.WAITING_FOR_BOOKING_RESULT,
            reason=InterruptionReason.USER_PAUSE,
        )


def test_agent_state_rejects_same_active_and_interrupted_workflow():
    with pytest.raises(ValidationError, match="must be different"):
        AgentState(
            session_id="session-001",
            current_workflow=WorkflowType.RIDE_BOOKING,
            current_step=BookingStep.COLLECT_PHONE,
            interrupted_workflow=InterruptedWorkflow(
                workflow=WorkflowType.RIDE_BOOKING,
                step=BookingStep.COLLECT_PICKUP,
                reason=InterruptionReason.USER_PAUSE,
            ),
        )


def test_old_agent_state_payload_remains_backward_compatible():
    state = AgentState.model_validate({"session_id": "session-001"})

    assert state.interrupted_workflow is None


@pytest.mark.asyncio
async def test_pause_and_resume_restore_exact_booking_step_and_control_state():
    agent = LLMAgent()
    state = booking_state(step=BookingStep.CONFIRM)

    paused = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Khoan đã",
        ),
        state,
    )
    paused_state = apply_action(state, paused)

    assert paused.action_type is ActionType.RESPOND
    assert paused_state.current_workflow is None
    assert paused_state.current_step is None
    assert paused_state.interrupted_workflow is not None
    assert paused_state.interrupted_workflow.workflow is WorkflowType.RIDE_BOOKING
    assert paused_state.interrupted_workflow.step == BookingStep.CONFIRM
    assert (
        paused_state.interrupted_workflow.confirmation
        is ConfirmationStatus.AWAITING_CONFIRMATION
    )
    assert paused_state.interrupted_workflow.retry_count == 1
    assert "booking" in paused_state.collected_data

    resumed = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript="Tiếp tục",
        ),
        paused_state,
    )
    resumed_state = apply_action(paused_state, resumed)

    assert resumed.action_type is ActionType.ASK_USER
    assert "Hồ Gươm" in (resumed.message or "")
    assert "Times City" in (resumed.message or "")
    assert resumed_state.current_workflow is WorkflowType.RIDE_BOOKING
    assert resumed_state.current_step == BookingStep.CONFIRM
    assert resumed_state.confirmation is ConfirmationStatus.AWAITING_CONFIRMATION
    assert resumed_state.retry_count == 1
    assert resumed_state.interrupted_workflow is None


@pytest.mark.asyncio
async def test_pause_is_blocked_while_read_only_tool_is_pending():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step=BookingStep.WAITING_FOR_PICKUP_RESULT,
        pending_tool_call_id="search-1",
        pending_tool_name=ToolName.SEARCH_PLACE,
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tạm dừng",
        ),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert "chờ kết quả" in (action.message or "").casefold()
    assert "interrupted_workflow" not in action.state_updates
    assert "pending_tool_call_id" not in action.state_updates


@pytest.mark.asyncio
async def test_pause_with_pending_side_effect_requires_reconciliation():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step=BookingStep.WAITING_FOR_BOOKING_RESULT,
        collected_data={"booking": {"phone_number": "0901234567"}},
        pending_tool_call_id="booking-1",
        pending_tool_name=ToolName.CREATE_BOOKING,
        confirmation=ConfirmationStatus.CONFIRMED,
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tạm dừng",
        ),
        state,
    )
    next_state = apply_action(state, action)

    assert action.action_type is ActionType.HANDOFF
    assert next_state.current_step == "RECONCILIATION_REQUIRED"
    assert next_state.pending_tool_call_id == "booking-1"


@pytest.mark.asyncio
async def test_help_is_contextual_and_does_not_change_booking_state():
    state = booking_state()

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tôi cần trợ giúp",
        ),
        state,
    )

    assert action.action_type is ActionType.RESPOND
    assert "điểm đón" in (action.message or "")
    assert "current_workflow" not in action.state_updates
    assert "collected_data" not in action.state_updates


@pytest.mark.asyncio
async def test_explicit_intent_change_pauses_booking_and_starts_trip_lookup():
    state = booking_state()

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Chuyển sang tra cứu chuyến",
        ),
        state,
    )
    next_state = apply_action(state, action)

    assert action.action_type is ActionType.ASK_USER
    assert next_state.current_workflow is WorkflowType.TRIP_LOOKUP
    assert next_state.current_step == TripLookupStep.COLLECT_IDENTIFIER
    assert next_state.interrupted_workflow is not None
    assert next_state.interrupted_workflow.workflow is WorkflowType.RIDE_BOOKING
    assert next_state.interrupted_workflow.step == BookingStep.COLLECT_PHONE
    assert "booking" in next_state.collected_data


@pytest.mark.asyncio
async def test_nested_intent_change_is_rejected_without_overwriting_saved_frame():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step=TripLookupStep.COLLECT_IDENTIFIER,
        interrupted_workflow=InterruptedWorkflow(
            workflow=WorkflowType.RIDE_BOOKING,
            step=BookingStep.COLLECT_PHONE,
            reason=InterruptionReason.CHANGE_INTENT,
        ),
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Chuyển sang hỏi đáp",
        ),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert "đang tạm dừng" in (action.message or "")
    assert "interrupted_workflow" not in action.state_updates


@pytest.mark.asyncio
async def test_booking_faq_interruption_answer_and_resume_full_workflow():
    agent = LLMAgent()
    state = booking_state()

    faq_call = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Dịch vụ có hỗ trợ thanh toán bằng tiền mặt không?",
        ),
        state,
    )
    faq_state = apply_action(state, faq_call)

    assert faq_call.action_type is ActionType.CALL_TOOL
    assert faq_call.tool_call is not None
    assert faq_call.tool_call.tool_name is ToolName.RETRIEVE_KNOWLEDGE
    assert faq_state.current_workflow is WorkflowType.FAQ
    assert faq_state.current_step == FAQStep.WAITING_FOR_KNOWLEDGE
    assert faq_state.interrupted_workflow is not None
    assert faq_state.interrupted_workflow.workflow is WorkflowType.RIDE_BOOKING
    assert faq_state.interrupted_workflow.step == BookingStep.COLLECT_PHONE
    assert "booking" in faq_state.collected_data

    faq_answer = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            tool_result=ToolResult(
                tool_name=ToolName.RETRIEVE_KNOWLEDGE,
                call_id=faq_call.tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data={
                    "documents": [
                        {
                            "content": "Khách có thể thanh toán bằng tiền mặt.",
                            "source": "payment-policy",
                            "score": 0.95,
                        }
                    ]
                },
            ),
        ),
        faq_state,
    )
    answered_state = apply_action(faq_state, faq_answer)

    assert faq_answer.action_type is ActionType.RESPOND
    assert "thanh toán bằng tiền mặt" in (faq_answer.message or "")
    assert "tiếp tục việc đặt xe" in (faq_answer.message or "").casefold()
    assert answered_state.current_workflow is None
    assert answered_state.interrupted_workflow is not None

    resume = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-003",
            transcript="Tiếp tục",
        ),
        answered_state,
    )
    resumed_state = apply_action(answered_state, resume)

    assert resume.action_type is ActionType.ASK_USER
    assert "số điện thoại" in (resume.message or "")
    assert resumed_state.current_workflow is WorkflowType.RIDE_BOOKING
    assert resumed_state.current_step == BookingStep.COLLECT_PHONE
    assert resumed_state.interrupted_workflow is None
    assert "faq" not in resumed_state.collected_data
    assert "booking" in resumed_state.collected_data

    confirmation = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-004",
            transcript="0901234567",
        ),
        resumed_state,
    )

    assert confirmation.action_type is ActionType.ASK_USER
    assert confirmation.state_updates["current_step"] == BookingStep.CONFIRM


@pytest.mark.asyncio
async def test_natural_faq_cannot_create_nested_interruption():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step=TripLookupStep.COLLECT_IDENTIFIER,
        interrupted_workflow=InterruptedWorkflow(
            workflow=WorkflowType.RIDE_BOOKING,
            step=BookingStep.COLLECT_PHONE,
            reason=InterruptionReason.CHANGE_INTENT,
        ),
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Dịch vụ hoạt động ban đêm không?",
        ),
        state,
    )

    assert action.action_type is ActionType.ASK_USER
    assert "đang tạm dừng" in (action.message or "")
    assert "current_workflow" not in action.state_updates


@pytest.mark.asyncio
async def test_cancel_paused_workflow_clears_only_its_namespace():
    state = AgentState(
        session_id="session-001",
        collected_data={
            "booking": complete_locations().model_dump(mode="json"),
            "custom": {"keep": True},
        },
        interrupted_workflow=InterruptedWorkflow(
            workflow=WorkflowType.RIDE_BOOKING,
            step=BookingStep.COLLECT_PHONE,
            reason=InterruptionReason.USER_PAUSE,
        ),
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Hủy đặt xe",
        ),
        state,
    )
    next_state = apply_action(state, action)

    assert next_state.interrupted_workflow is None
    assert "booking" not in next_state.collected_data
    assert next_state.collected_data["custom"] == {"keep": True}


@pytest.mark.asyncio
async def test_cancel_active_faq_preserves_paused_booking():
    frame = InterruptedWorkflow(
        workflow=WorkflowType.RIDE_BOOKING,
        step=BookingStep.COLLECT_PHONE,
        reason=InterruptionReason.FAQ,
    )
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.FAQ,
        current_step=FAQStep.COMPLETE,
        collected_data={
            "faq": {"question": "Thanh toán?"},
            "booking": complete_locations().model_dump(mode="json"),
        },
        interrupted_workflow=frame,
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Hủy yêu cầu",
        ),
        state,
    )
    next_state = apply_action(state, action)

    assert next_state.current_workflow is None
    assert next_state.interrupted_workflow == frame
    assert "faq" not in next_state.collected_data
    assert "booking" in next_state.collected_data


@pytest.mark.asyncio
async def test_goodbye_clears_active_and_interrupted_workflow_namespaces():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.FAQ,
        current_step=FAQStep.COMPLETE,
        collected_data={
            "faq": {"question": "Thanh toán?"},
            "booking": complete_locations().model_dump(mode="json"),
            "custom": {"keep": True},
        },
        interrupted_workflow=InterruptedWorkflow(
            workflow=WorkflowType.RIDE_BOOKING,
            step=BookingStep.COLLECT_PHONE,
            reason=InterruptionReason.FAQ,
        ),
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tạm biệt",
        ),
        state,
    )
    next_state = apply_action(state, action)

    assert action.action_type is ActionType.END_SESSION
    assert next_state.current_workflow is None
    assert next_state.interrupted_workflow is None
    assert next_state.collected_data == {"custom": {"keep": True}}
