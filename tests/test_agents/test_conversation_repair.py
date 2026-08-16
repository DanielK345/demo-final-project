import pytest

from src.agents.agent import LLMAgent
from src.agents.history import build_message_id
from src.agents.legacy.workflows.base import BaseWorkflow
from src.agents.repair import ConversationRepairHandler
from src.agents.repair_models import DialogueAct, DialogueActResult
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import (
    AgentState,
    ConfirmationStatus,
    ConversationMessage,
    ConversationMessageType,
    ConversationRole,
    DeliveryStatus,
)


def command(act: DialogueAct) -> DialogueActResult:
    return DialogueActResult(
        act=act,
        confidence=1,
        matched_evidence=[act.value],
    )


def assistant_message(
    turn_id: str,
    content: str,
    status: DeliveryStatus,
    *,
    spoken_content: str | None = None,
) -> ConversationMessage:
    return ConversationMessage(
        message_id=build_message_id(turn_id, ConversationRole.ASSISTANT),
        turn_id=turn_id,
        role=ConversationRole.ASSISTANT,
        message_type=ConversationMessageType.ASSISTANT_SPEECH,
        content=content,
        delivery_status=status,
        spoken_content=spoken_content,
    )


def repair(
    act: DialogueAct,
    state: AgentState,
    *,
    transcript: str | None = None,
):
    agent_input = AgentInput(
        session_id=state.session_id,
        turn_id="repair-turn",
        transcript=transcript or act.value,
    )
    action = ConversationRepairHandler().handle(command(act), agent_input, state)
    assert action is not None
    return action


def test_repeat_returns_last_delivered_assistant_message():
    state = AgentState(
        session_id="session-001",
        conversation_history=[
            assistant_message(
                "turn-001",
                "Bạn muốn đón ở đâu?",
                DeliveryStatus.DELIVERED,
                spoken_content="Bạn muốn đón ở đâu?",
            ),
            assistant_message(
                "turn-002",
                "Nội dung chưa được phát.",
                DeliveryStatus.PENDING,
            ),
        ],
    )

    action = repair(DialogueAct.REPEAT, state)

    assert action.action_type is ActionType.RESPOND
    assert action.message == "Bạn muốn đón ở đâu?"
    assert action.state_updates == {}


def test_repeat_returns_only_the_spoken_part_of_interrupted_message():
    state = AgentState(
        session_id="session-001",
        conversation_history=[
            assistant_message(
                "turn-001",
                "Bạn muốn đón ở Hồ Gươm hay Phố cổ?",
                DeliveryStatus.INTERRUPTED,
                spoken_content="Bạn muốn đón ở Hồ Gươm",
            )
        ],
    )

    action = repair(DialogueAct.REPEAT, state)

    assert action.message == "Bạn muốn đón ở Hồ Gươm"


def test_repeat_asks_for_a_new_request_without_audible_history():
    state = AgentState(
        session_id="session-001",
        conversation_history=[
            assistant_message("turn-001", "Không phát được", DeliveryStatus.FAILED)
        ],
    )

    action = repair(DialogueAct.REPEAT, state)

    assert action.action_type is ActionType.ASK_USER
    assert "chưa có nội dung" in (action.message or "").casefold()


def test_cancel_clears_only_active_workflow_namespace_and_read_only_pending_tool():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="SELECT_PICKUP_CANDIDATE",
        collected_data={
            "booking": {"pickup_query": "Hồ Gươm"},
            "trip_lookup": {"booking_id": "GSM-1"},
            "custom": {"keep": True},
        },
        pending_tool_call_id="search-1",
        pending_tool_name=ToolName.SEARCH_PLACE,
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
        retry_count=2,
    )

    action = repair(DialogueAct.CANCEL, state)
    next_state = state.apply(action.state_updates)

    assert action.action_type is ActionType.RESPOND
    assert next_state.current_workflow is None
    assert next_state.current_step is None
    assert next_state.pending_tool_name is None
    assert next_state.confirmation is ConfirmationStatus.NOT_REQUESTED
    assert next_state.retry_count == 0
    assert "booking" not in next_state.collected_data
    assert next_state.collected_data["trip_lookup"] == {"booking_id": "GSM-1"}
    assert next_state.collected_data["custom"] == {"keep": True}


def test_cancel_without_active_workflow_is_safe_and_idempotent():
    state = AgentState(session_id="session-001", collected_data={"custom": "keep"})

    action = repair(DialogueAct.CANCEL, state)

    assert action.action_type is ActionType.RESPOND
    assert action.state_updates == {}
    assert "không có yêu cầu" in (action.message or "").casefold()


@pytest.mark.parametrize(
    ("workflow", "namespace", "expected_step", "expected_prompt"),
    [
        (
            WorkflowType.RIDE_BOOKING,
            "booking",
            "COLLECT_PICKUP",
            "đón ở đâu",
        ),
        (
            WorkflowType.TRIP_LOOKUP,
            "trip_lookup",
            "COLLECT_IDENTIFIER",
            "mã chuyến",
        ),
        (WorkflowType.FAQ, "faq", None, "hỏi thông tin gì"),
    ],
)
def test_start_over_resets_active_workflow_to_its_initial_step(
    workflow,
    namespace,
    expected_step,
    expected_prompt,
):
    state = AgentState(
        session_id="session-001",
        current_workflow=workflow,
        current_step="LATER_STEP",
        collected_data={namespace: {"old": "value"}, "custom": "keep"},
        confirmation=ConfirmationStatus.CONFIRMED,
        retry_count=2,
    )

    action = repair(DialogueAct.START_OVER, state)
    next_state = state.apply(action.state_updates)

    assert action.action_type is ActionType.ASK_USER
    assert expected_prompt in (action.message or "").casefold()
    assert next_state.current_workflow is workflow
    assert next_state.current_step == expected_step
    assert namespace not in next_state.collected_data
    assert next_state.collected_data["custom"] == "keep"
    assert next_state.confirmation is ConfirmationStatus.NOT_REQUESTED
    assert next_state.retry_count == 0


def test_goodbye_ends_session_and_clears_safe_active_workflow():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step="COLLECT_IDENTIFIER",
        collected_data={"trip_lookup": {}, "custom": "keep"},
    )

    action = repair(DialogueAct.GOODBYE, state)
    next_state = state.apply(action.state_updates)

    assert action.action_type is ActionType.END_SESSION
    assert next_state.current_workflow is None
    assert "trip_lookup" not in next_state.collected_data
    assert next_state.collected_data["custom"] == "keep"


@pytest.mark.parametrize(
    "act",
    [
        DialogueAct.CORRECT,
        DialogueAct.CANCEL,
        DialogueAct.START_OVER,
        DialogueAct.GOODBYE,
    ],
)
def test_pending_side_effect_requires_reconciliation_and_is_preserved(act):
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="WAITING_FOR_BOOKING_RESULT",
        collected_data={"booking": {"pickup": "p1", "destination": "p2"}},
        pending_tool_call_id="booking-1",
        pending_tool_name=ToolName.CREATE_BOOKING,
        confirmation=ConfirmationStatus.CONFIRMED,
    )

    action = repair(act, state)
    next_state = state.apply(action.state_updates)

    assert action.action_type is ActionType.HANDOFF
    assert next_state.current_workflow is WorkflowType.HUMAN_HANDOFF
    assert next_state.current_step == "RECONCILIATION_REQUIRED"
    assert next_state.pending_tool_call_id == "booking-1"
    assert next_state.pending_tool_name is ToolName.CREATE_BOOKING
    assert next_state.collected_data == state.collected_data


def test_correction_without_active_booking_does_not_modify_other_workflow():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.TRIP_LOOKUP,
        current_step="COLLECT_IDENTIFIER",
        collected_data={"trip_lookup": {"booking_id": "GSM-1"}},
    )

    action = repair(DialogueAct.CORRECT, state, transcript="Sửa điểm đón")

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates == {}
    assert "không có yêu cầu đặt xe" in (action.message or "").casefold()


class FailingUnderstanding:
    async def understand(self, transcript, context):
        del transcript, context
        raise AssertionError("repair commands must bypass understanding")


class FailingRewriter:
    async def rewrite(self, original_text, context, decision):
        del original_text, context, decision
        raise AssertionError("repair commands must bypass rewrite")


@pytest.mark.asyncio
async def test_agent_handles_repeat_before_rewrite_and_records_raw_turn_history():
    state = AgentState(
        session_id="session-001",
        conversation_history=[
            assistant_message(
                "turn-001",
                "Bạn muốn đi đâu?",
                DeliveryStatus.DELIVERED,
                spoken_content="Bạn muốn đi đâu?",
            )
        ],
    )
    agent = LLMAgent(
        understanding_service=FailingUnderstanding(),
        message_rewriter=FailingRewriter(),
    )

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript="Nói lại giúp tôi",
        ),
        state,
    )

    assert action.action_type is ActionType.RESPOND
    assert action.message == "Bạn muốn đi đâu?"
    history = action.state_updates["conversation_history"]
    assert history[-2].content == "Nói lại giúp tôi"
    assert history[-2].delivery_status is DeliveryStatus.FINAL
    assert history[-1].content == "Bạn muốn đi đâu?"
    assert history[-1].delivery_status is DeliveryStatus.PENDING


@pytest.mark.asyncio
async def test_agent_preserves_pending_side_effect_when_handling_goodbye():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="WAITING_FOR_BOOKING_RESULT",
        collected_data={"booking": {"pickup": "p1", "destination": "p2"}},
        pending_tool_call_id="booking-1",
        pending_tool_name=ToolName.CREATE_BOOKING,
        confirmation=ConfirmationStatus.CONFIRMED,
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript="Tạm biệt",
        ),
        state,
    )
    next_state = state.apply(action.state_updates)

    assert action.action_type is ActionType.HANDOFF
    assert next_state.current_step == "RECONCILIATION_REQUIRED"
    assert next_state.pending_tool_call_id == "booking-1"
    assert next_state.pending_tool_name is ToolName.CREATE_BOOKING
    assert next_state.collected_data == state.collected_data


@pytest.mark.asyncio
async def test_agent_routes_active_booking_correction_to_booking_workflow():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="CONFIRM",
        collected_data={
            "booking": {
                "pickup": {"place_id": "p1", "display_name": "Hồ Gươm"},
                "destination": {
                    "place_id": "d1",
                    "display_name": "Times City",
                },
                "phone_number": "0901234567",
            }
        },
        confirmation=ConfirmationStatus.AWAITING_CONFIRMATION,
    )

    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript="Số điện thoại đúng là 0987654321",
        ),
        state,
    )
    corrected = action.state_updates["collected_data"]["booking"]

    assert action.action_type is ActionType.ASK_USER
    assert action.state_updates["current_step"] == "COLLECT_VEHICLE"
    assert action.state_updates["confirmation"] is ConfirmationStatus.NOT_REQUESTED
    assert corrected["phone_number"] == "0987654321"
    assert action.tool_call is None


class FailingDetector:
    def detect(self, transcript):
        del transcript
        raise AssertionError("tool results must bypass dialogue-act detection")


class ToolResultWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.RIDE_BOOKING

    async def handle(self, agent_input, state, understanding=None):
        del state, understanding
        assert agent_input.tool_result is not None
        return AgentAction(
            action_type=ActionType.RESPOND,
            message="Đã nhận kết quả công cụ.",
            state_updates={
                "pending_tool_call_id": None,
                "pending_tool_name": None,
            },
        )


@pytest.mark.asyncio
async def test_correlated_tool_result_has_priority_over_repair_command():
    state = AgentState(
        session_id="session-001",
        current_workflow=WorkflowType.RIDE_BOOKING,
        current_step="WAITING_FOR_PICKUP_RESULT",
        pending_tool_call_id="search-1",
        pending_tool_name=ToolName.SEARCH_PLACE,
    )
    agent = LLMAgent(
        dialogue_act_detector=FailingDetector(),
        workflows={WorkflowType.RIDE_BOOKING: ToolResultWorkflow()},
    )

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-002",
            transcript="Hủy",
            tool_result=ToolResult(
                tool_name=ToolName.SEARCH_PLACE,
                call_id="search-1",
                status=ToolStatus.SUCCESS,
                data={"candidates": []},
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.RESPOND
    assert action.state_updates["pending_tool_call_id"] is None
    assert action.state_updates["pending_tool_name"] is None


@pytest.mark.asyncio
async def test_agent_prioritizes_emergency_over_goodbye_repair():
    agent = LLMAgent(
        understanding_service=FailingUnderstanding(),
        message_rewriter=FailingRewriter(),
    )

    action = await agent.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            transcript="Tôi đang gặp nguy hiểm, tạm biệt",
        )
    )

    assert action.action_type is ActionType.HANDOFF
    assert "EMERGENCY" in (action.reason or "")
