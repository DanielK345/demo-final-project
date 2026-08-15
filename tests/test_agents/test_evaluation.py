import pytest

from src.agents.contracts.schemas import ActionType, AgentAction, AgentInput
from src.agents.contracts.state import AgentState
from src.agents.eval import (
    BehaviorEvaluator,
    ConversationEvaluationResult,
    EvaluationCase,
    ReadinessThresholds,
)


class RespondingAgent:
    async def handle(self, agent_input: AgentInput, state: AgentState | None = None) -> AgentAction:
        del agent_input, state
        return AgentAction(action_type=ActionType.RESPOND, message="Chào bạn!")


@pytest.mark.asyncio
async def test_behavior_evaluator_reports_offline_action_metrics():
    cases = [
        EvaluationCase(
<<<<<<< HEAD
            name="booking starts slot collection",
            agent_input=AgentInput(
                session_id="eval-booking",
                turn_id="turn-001",
                transcript="Tôi muốn đặt xe",
            ),
            expected_action_type=ActionType.ASK_USER,
            expected_workflow=WorkflowType.RIDE_BOOKING,
        ),
        EvaluationCase(
            name="booking resolves pickup",
            agent_input=AgentInput(
                session_id="eval-pickup",
                turn_id="turn-001",
                transcript="Hồ Gươm",
            ),
            state=AgentState(
                session_id="eval-pickup",
                current_workflow=WorkflowType.RIDE_BOOKING,
                current_step="COLLECT_PICKUP",
            ),
            expected_action_type=ActionType.CALL_TOOL,
            expected_workflow=WorkflowType.RIDE_BOOKING,
            expected_tool_name=ToolName.SEARCH_PLACE,
        ),
        EvaluationCase(
            name="human request handoff",
            agent_input=AgentInput(
                session_id="eval-handoff",
                turn_id="turn-001",
                transcript="Cho tôi gặp tổng đài viên",
            ),
            expected_action_type=ActionType.HANDOFF,
            expected_workflow=WorkflowType.HUMAN_HANDOFF,
=======
            name="valid response",
            agent_input=AgentInput(session_id="eval", turn_id="turn-001", transcript="Xin chào"),
            expected_action_type=ActionType.RESPOND,
>>>>>>> 86cfe2ef3e6996c4053492e822e3a2435384bcc3
        ),
    ]

    report = await BehaviorEvaluator().evaluate(RespondingAgent(), cases)

    assert report.case_count == 1
    assert report.pass_rate == 1
    assert report.action_accuracy == 1
    assert report.workflow_accuracy == 1
    assert report.tool_accuracy == 1
    assert report.schema_validity_rate == 1
    assert report.average_latency_ms >= 0


@pytest.mark.asyncio
async def test_behavior_evaluator_handles_empty_suite():
    report = await BehaviorEvaluator().evaluate(RespondingAgent(), [])

    assert report.case_count == 0
    assert report.pass_rate == 0

def test_readiness_rejects_incomplete_expected_workflow():
    scenario = ConversationEvaluationResult(
        name="incomplete workflow",
        turn_count=1,
        passed_turns=1,
        action_accuracy=1,
        tool_accuracy=1,
        tool_argument_accuracy=1,
        pii_leak_count=0,
        confirmation_safety_violations=0,
        duplicate_side_effect_violations=0,
        completed=False,
        completion_expected=True,
        latency_ms=[1],
    )

    report = BehaviorEvaluator._readiness_report(
        [scenario],
        dataset_version="test",
        thresholds=ReadinessThresholds(),
    )

    assert report.pass_rate == 0
    assert report.workflow_completion_rate == 0
    assert report.ready is False
    assert "minimum_workflow_completion_rate" in report.failed_gates


def test_readiness_gates_tool_argument_accuracy():
    scenario = ConversationEvaluationResult(
        name="wrong arguments",
        turn_count=1,
        passed_turns=0,
        action_accuracy=1,
        tool_accuracy=1,
        tool_argument_accuracy=0,
        pii_leak_count=0,
        confirmation_safety_violations=0,
        duplicate_side_effect_violations=0,
        completed=True,
        completion_expected=True,
        latency_ms=[1],
    )

    report = BehaviorEvaluator._readiness_report(
        [scenario],
        dataset_version="test",
        thresholds=ReadinessThresholds(),
    )

    assert report.ready is False
    assert "minimum_tool_argument_accuracy" in report.failed_gates
