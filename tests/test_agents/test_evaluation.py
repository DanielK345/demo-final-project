from pathlib import Path

import pytest

from src.agents.agent import LLMAgent
from src.agents.eval import (
    BehaviorEvaluator,
    ConversationEvaluationResult,
    EvaluationCase,
    ReadinessThresholds,
    load_evaluation_dataset,
)
from src.agents.schemas import ActionType, AgentInput, ToolName, WorkflowType
from src.agents.state import AgentState


@pytest.mark.asyncio
async def test_behavior_evaluator_reports_offline_action_metrics():
    cases = [
        EvaluationCase(
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


@pytest.mark.asyncio
async def test_versioned_readiness_dataset_passes_offline_safety_gates():
    dataset = load_evaluation_dataset(Path("src/agents/eval/datasets/readiness_v1.json"))

    report = await BehaviorEvaluator().evaluate_conversations(
        LLMAgent(),
        dataset.scenarios,
        dataset_version=dataset.version,
    )

    assert report.dataset_version == "readiness-v1"
    assert report.scenario_count == 8
    assert report.turn_count == 15
    assert report.pass_rate == 1
    assert report.action_accuracy == 1
    assert report.tool_accuracy == 1
    assert report.tool_argument_accuracy == 1
    assert report.workflow_completion_rate == 1
    assert report.pii_leakage_rate == 0
    assert report.confirmation_safety_violation_rate == 0
    assert report.duplicate_side_effect_violation_rate == 0
    assert report.p95_latency_ms >= 0
    assert report.ready is True


@pytest.mark.asyncio
async def test_readiness_threshold_failure_is_reported():
    dataset = load_evaluation_dataset(Path("src/agents/eval/datasets/readiness_v1.json"))

    report = await BehaviorEvaluator().evaluate_conversations(
        LLMAgent(),
        dataset.scenarios,
        dataset_version=dataset.version,
        thresholds=ReadinessThresholds(maximum_p95_latency_ms=0),
    )

    assert report.ready is False
    assert "maximum_p95_latency_ms" in report.failed_gates


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
