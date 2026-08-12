from time import perf_counter

from src.agents.agent import LLMAgent
from src.agents.eval.models import EvaluationCase, EvaluationReport, EvaluationResult
from src.agents.schemas import ActionType


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
            schema_valid = action.model_validate(action.model_dump()) == action
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

        return EvaluationReport(
            results=results,
            case_count=count,
            pass_rate=sum(result.passed for result in results) / count,
            action_accuracy=sum(result.action_correct for result in results) / count,
            workflow_accuracy=(
                sum(result.workflow_correct for result in results) / count
            ),
            tool_accuracy=sum(result.tool_correct for result in results) / count,
            schema_validity_rate=sum(result.schema_valid for result in results) / count,
            average_latency_ms=sum(result.latency_ms for result in results) / count,
        )
