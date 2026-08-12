import pytest

from src.agents.agent import LLMAgent
from src.agents.eval import BehaviorEvaluator, EvaluationCase
from src.agents.schemas import ActionType, AgentInput, ToolName, WorkflowType
from src.agents.state import AgentState


@pytest.mark.asyncio
async def test_behavior_evaluator_reports_offline_action_metrics():
    cases = [
        EvaluationCase(
            name="booking starts slot collection",
            agent_input=AgentInput(
                session_id="eval-booking",
                transcript="Tôi muốn đặt xe",
            ),
            expected_action_type=ActionType.ASK_USER,
            expected_workflow=WorkflowType.RIDE_BOOKING,
        ),
        EvaluationCase(
            name="booking resolves pickup",
            agent_input=AgentInput(
                session_id="eval-pickup",
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
                transcript="Cho tôi gặp tổng đài viên",
            ),
            expected_action_type=ActionType.HANDOFF,
            expected_workflow=WorkflowType.HUMAN_HANDOFF,
        ),
    ]

    report = await BehaviorEvaluator().evaluate(LLMAgent(), cases)

    assert report.case_count == 3
    assert report.pass_rate == 1
    assert report.action_accuracy == 1
    assert report.workflow_accuracy == 1
    assert report.tool_accuracy == 1
    assert report.schema_validity_rate == 1
    assert report.average_latency_ms >= 0


@pytest.mark.asyncio
async def test_behavior_evaluator_handles_empty_suite():
    report = await BehaviorEvaluator().evaluate(LLMAgent(), [])

    assert report.case_count == 0
    assert report.pass_rate == 0
