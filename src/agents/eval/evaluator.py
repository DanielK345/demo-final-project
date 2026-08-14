from time import perf_counter

from pydantic import ValidationError

from src.agents.agent import LLMAgent
from src.agents.eval.models import (
    ConversationEvaluationCase,
    ConversationEvaluationResult,
    EvaluationCase,
    EvaluationReport,
    EvaluationResult,
    ReadinessReport,
    ReadinessThresholds,
)
from src.agents.guardrails import redact_pii
from src.agents.schemas import ActionType, ToolName
from src.agents.state import AgentState, ConfirmationStatus

_SIDE_EFFECTS = {ToolName.CREATE_BOOKING, ToolName.CANCEL_BOOKING}


class BehaviorEvaluator:
    async def evaluate(
        self,
        agent: LLMAgent,
        cases: list[EvaluationCase],
    ) -> EvaluationReport:
        results: list[EvaluationResult] = []
        for case in cases:
            started = perf_counter()
            action = await agent.handle(case.agent_input, case.state)
            latency_ms = (perf_counter() - started) * 1000
            try:
                action.model_validate(action.model_dump(mode="json"))
                schema_valid = True
            except ValidationError:
                schema_valid = False
            actual_workflow = action.state_updates.get("current_workflow")
            actual_tool = action.tool_call.tool_name if action.tool_call else None
            results.append(
                EvaluationResult(
                    name=case.name,
                    action_correct=action.action_type is case.expected_action_type,
                    workflow_correct=(actual_workflow is case.expected_workflow),
                    tool_correct=(
                        actual_tool is case.expected_tool_name
                        if case.expected_action_type is ActionType.CALL_TOOL
                        else actual_tool is None
                    ),
                    schema_valid=schema_valid,
                    latency_ms=latency_ms,
                    actual_action_type=action.action_type,
                    actual_workflow=actual_workflow,
                    actual_tool_name=actual_tool,
                )
            )
        return self._report(results)

    @staticmethod
    def _report(results: list[EvaluationResult]) -> EvaluationReport:
        count = len(results)
        if count == 0:
            return EvaluationReport(
                results=[],
                case_count=0,
                pass_rate=0,
                action_accuracy=0,
                workflow_accuracy=0,
                tool_accuracy=0,
                schema_validity_rate=0,
                average_latency_ms=0,
            )

        latencies = [result.latency_ms for result in results]
        return EvaluationReport(
            results=results,
            case_count=count,
            pass_rate=sum(result.passed for result in results) / count,
            action_accuracy=sum(result.action_correct for result in results) / count,
            workflow_accuracy=(sum(result.workflow_correct for result in results) / count),
            tool_accuracy=sum(result.tool_correct for result in results) / count,
            schema_validity_rate=sum(result.schema_valid for result in results) / count,
            average_latency_ms=sum(result.latency_ms for result in results) / count,
            p50_latency_ms=_percentile(latencies, 0.50),
            p95_latency_ms=_percentile(latencies, 0.95),
            p99_latency_ms=_percentile(latencies, 0.99),
        )

    async def evaluate_conversations(
        self,
        agent: LLMAgent,
        cases: list[ConversationEvaluationCase],
        *,
        dataset_version: str,
        thresholds: ReadinessThresholds | None = None,
    ) -> ReadinessReport:
        scenario_results = [await self._evaluate_conversation(agent, case) for case in cases]
        return self._readiness_report(
            scenario_results,
            dataset_version=dataset_version,
            thresholds=thresholds or ReadinessThresholds(),
        )

    async def _evaluate_conversation(
        self,
        agent: LLMAgent,
        case: ConversationEvaluationCase,
    ) -> ConversationEvaluationResult:
        state = case.initial_state or AgentState(session_id=case.session_id)
        passed = action_correct = tool_correct = params_correct = 0
        pii_leaks = confirmation_violations = duplicate_violations = 0
        latencies: list[float] = []
        emitted_side_effect_keys: set[str] = set()

        for index, turn in enumerate(case.turns, start=1):
            agent_input = turn.to_agent_input(
                session_id=case.session_id,
                turn_id=f"eval-turn-{index:03d}",
                pending_call_id=state.pending_tool_call_id,
            )
            confirmation_before = state.confirmation
            started = perf_counter()
            action = await agent.handle(agent_input, state)
            latencies.append((perf_counter() - started) * 1000)

            action_ok = action.action_type is turn.expected_action_type
            actual_workflow = action.state_updates.get("current_workflow", state.current_workflow)
            workflow_ok = actual_workflow is turn.expected_workflow
            actual_tool = action.tool_call.tool_name if action.tool_call else None
            tool_ok = actual_tool is turn.expected_tool_name
            params_ok = bool(action.tool_call) or not turn.expected_tool_params
            if turn.expected_tool_params:
                params_ok = bool(action.tool_call) and all(
                    action.tool_call.params.get(key) == value for key, value in turn.expected_tool_params.items()
                )
            message = action.message or ""
            leak = any(term in message for term in turn.forbidden_message_terms)
            leak = leak or redact_pii(message) != message

            if action_ok:
                action_correct += 1
            if tool_ok:
                tool_correct += 1
            if params_ok:
                params_correct += 1
            if action_ok and workflow_ok and tool_ok and params_ok and not leak:
                passed += 1
            pii_leaks += int(leak)

            if actual_tool in _SIDE_EFFECTS:
                if confirmation_before is not ConfirmationStatus.AWAITING_CONFIRMATION:
                    confirmation_violations += 1
                key = str(action.tool_call.params.get("idempotency_key"))
                if key in emitted_side_effect_keys:
                    duplicate_violations += 1
                emitted_side_effect_keys.add(key)
            state = state.apply(action.state_updates)

        turn_count = len(case.turns)
        completed = not case.expect_completion or state.current_workflow is None
        return ConversationEvaluationResult(
            name=case.name,
            turn_count=turn_count,
            passed_turns=passed,
            action_accuracy=action_correct / turn_count,
            tool_accuracy=tool_correct / turn_count,
            tool_argument_accuracy=params_correct / turn_count,
            pii_leak_count=pii_leaks,
            confirmation_safety_violations=confirmation_violations,
            duplicate_side_effect_violations=duplicate_violations,
            completed=completed,
            completion_expected=case.expect_completion,
            latency_ms=latencies,
        )

    @staticmethod
    def _readiness_report(
        results: list[ConversationEvaluationResult],
        *,
        dataset_version: str,
        thresholds: ReadinessThresholds,
    ) -> ReadinessReport:
        turns = sum(result.turn_count for result in results)
        latencies = [latency for result in results for latency in result.latency_ms]
        completion_cases = [result for result in results if result.completion_expected]
        workflow_completion_rate = (
            sum(result.completed for result in completion_cases) / len(completion_cases)
            if completion_cases
            else 1
        )
        divisor = turns or 1
        scenario_divisor = len(results) or 1
        values = {
            "pass_rate": sum(result.passed for result in results) / scenario_divisor,
            "action_accuracy": sum(result.action_accuracy * result.turn_count for result in results) / divisor,
            "tool_accuracy": sum(result.tool_accuracy * result.turn_count for result in results) / divisor,
            "tool_argument_accuracy": sum(result.tool_argument_accuracy * result.turn_count for result in results)
            / divisor,
        }
        violations = {
            "pii_leakage_rate": sum(result.pii_leak_count for result in results) / divisor,
            "confirmation_safety_violation_rate": sum(result.confirmation_safety_violations for result in results)
            / divisor,
            "duplicate_side_effect_violation_rate": sum(result.duplicate_side_effect_violations for result in results)
            / divisor,
        }
        failed = []
        if values["pass_rate"] < thresholds.minimum_pass_rate:
            failed.append("minimum_pass_rate")
        if values["action_accuracy"] < thresholds.minimum_action_accuracy:
            failed.append("minimum_action_accuracy")
        if values["tool_accuracy"] < thresholds.minimum_tool_accuracy:
            failed.append("minimum_tool_accuracy")
        if values["tool_argument_accuracy"] < thresholds.minimum_tool_argument_accuracy:
            failed.append("minimum_tool_argument_accuracy")
        if workflow_completion_rate < thresholds.minimum_workflow_completion_rate:
            failed.append("minimum_workflow_completion_rate")
        if any(violations.values()):
            failed.append("zero_safety_violations")
        p95 = _percentile(latencies, 0.95)
        if thresholds.maximum_p95_latency_ms is not None and p95 > thresholds.maximum_p95_latency_ms:
            failed.append("maximum_p95_latency_ms")
        return ReadinessReport(
            dataset_version=dataset_version,
            scenario_count=len(results),
            turn_count=turns,
            **values,
            workflow_completion_rate=workflow_completion_rate,
            **violations,
            average_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            p50_latency_ms=_percentile(latencies, 0.50),
            p95_latency_ms=p95,
            p99_latency_ms=_percentile(latencies, 0.99),
            ready=not failed,
            failed_gates=failed,
            scenarios=results,
        )


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * quantile)
    return ordered[index]
