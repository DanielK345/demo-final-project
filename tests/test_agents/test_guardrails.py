import pytest

from src.agents.agent import LLMAgent
from src.agents.guardrails import (
    AgentGuardrails,
    GuardrailViolationError,
    redact_pii,
)
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolCall,
    ToolName,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.workflows.base import BaseWorkflow


class UnsafeBookingWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.RIDE_BOOKING

    async def handle(self, agent_input, state):
        call = ToolCall(
            tool_name=ToolName.CREATE_BOOKING,
            call_id="unsafe-call",
            params={
                "pickup_place_id": "p1",
                "destination_place_id": "p2",
                "phone_number": "0901234567",
            },
        )
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=call,
            state_updates={
                "current_workflow": self.workflow_type,
                "current_step": "WAITING_FOR_BOOKING_RESULT",
                "pending_tool_call_id": call.call_id,
                "pending_tool_name": call.tool_name,
            },
            reason="Unsafe booking for 0901234567",
        )


def test_guardrail_rejects_invalid_state_updates():
    with pytest.raises(GuardrailViolationError, match="invalid state"):
        AgentGuardrails().validate_and_sanitize(
            AgentInput(session_id="session-001", transcript="hello"),
            AgentState(session_id="session-001"),
            AgentAction(
                action_type=ActionType.ASK_USER,
                message="Hello",
                state_updates={"retry_count": -1},
            ),
        )


@pytest.mark.asyncio
async def test_agent_blocks_booking_without_confirmation():
    agent = LLMAgent(
        workflows={WorkflowType.RIDE_BOOKING: UnsafeBookingWorkflow()}
    )

    action = await agent.handle(
        AgentInput(session_id="session-001", transcript="Tôi muốn đặt xe")
    )

    assert action.action_type is ActionType.HANDOFF
    assert "create_booking requires" in action.reason
    assert "0901234567" not in action.reason


@pytest.mark.asyncio
async def test_agent_records_latest_stt_confidence_in_state_updates():
    action = await LLMAgent().handle(
        AgentInput(
            session_id="session-001",
            transcript="Tôi muốn đặt xe",
            stt_confidence=0.95,
        )
    )

    assert action.state_updates["last_stt_confidence"] == 0.95


def test_redact_pii_masks_phone_numbers():
    assert redact_pii("Customer phone is 090 123 4567") == (
        "Customer phone is [REDACTED_PHONE]"
    )
