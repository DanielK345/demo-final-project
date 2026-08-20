"""Run deterministic, multi-turn Core Agent workflow evaluations.

The scripted model controls semantic intent selection only. Production Agent,
typed state, guardrails, SessionService, and backend tools run unchanged.
"""

from __future__ import annotations

import asyncio
import json
import platform
import subprocess
import sys
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.agents.agent import LLMAgent
from src.agents.contracts.schemas import ActionType, AgentAction, ToolCall, ToolResult
from src.agents.contracts.state import AgentState
from src.agents.core.model import ModelDecision, ModelToolCall, ToolExchange
from src.backend.services.agent_tool_executor import AgentToolExecutor
from src.backend.services.booking_service import BookingService
from src.backend.services.pricing_service import PricingService
from src.backend.services.session_service import SessionService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = PROJECT_ROOT / "eval_cases" / "agent_workflow_eval_summary.json"
RESULTS_DIR = PROJECT_ROOT / "eval_cases" / "results"

SELECTED_TESTS = [
    "eval_cases/test_agent_workflows.py",
    "tests/test_backend/test_hanoi_booking_flow.py::test_vinuni_to_ho_guom_can_reach_confirmation_and_create_booking",
    "tests/test_agents/test_model_driven_booking.py::test_typed_respond_tool_controls_whether_agent_expects_an_answer",
    "tests/test_agents/test_model_driven_booking.py::test_vehicle_correction_updates_typed_state_before_next_backend_call",
    "tests/test_agents/test_model_driven_booking.py::test_handoff_contains_safe_structured_conversation_context",
    "tests/test_agents/test_handoff_policy.py::test_classify_specialized_handoff_cases",
]


def tool(name: str, **arguments: object) -> ModelDecision:
    return ModelDecision(tool_call=ModelToolCall(name, arguments))


class ScriptedConversationModel:
    """Deterministic semantic decisions with an audit trace."""

    def __init__(self, *decisions: ModelDecision) -> None:
        self.decisions = deque(decisions)
        self.calls: list[dict[str, object]] = []

    async def decide(
        self,
        *,
        instructions: str,
        context: dict[str, Any],
        tools: Sequence[dict[str, Any]],
        exchanges: Sequence[ToolExchange] = (),
    ) -> ModelDecision:
        del instructions, context, tools, exchanges
        if not self.decisions:
            raise AssertionError("Scripted model ran out of semantic decisions")
        decision = self.decisions.popleft()
        if decision.tool_call is not None:
            recorded: dict[str, object] = {
                "tool": decision.tool_call.name,
                "arguments": decision.tool_call.arguments,
            }
        else:
            recorded = {"message": decision.message}
        self.calls.append(recorded)
        return decision


class InMemoryQuoteService:
    def __init__(self, pricing: PricingService) -> None:
        self.pricing = pricing

    async def issue_quote(
        self,
        *,
        user_id: str,
        session_id: str,
        pickup_place_id: str,
        destination_place_id: str,
        vehicle_type: str,
        route_id: str | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
        del user_id, session_id, route_id, kwargs
        return self.pricing.estimate_fare(
            pickup_place_id=pickup_place_id,
            destination_place_id=destination_place_id,
            vehicle_type=vehicle_type,
        )


def _safe_tool_params(tool_call: ToolCall) -> dict[str, object]:
    params = dict(tool_call.params)
    if "idempotency_key" in params:
        params["idempotency_key"] = "<sha256-present>"
    return params


def _tool_result_summary(result: ToolResult) -> dict[str, object]:
    summary: dict[str, object] = {"tool_status": result.status.value}
    if result.error:
        summary["error"] = result.error
    data = result.data
    candidates = data.get("candidates")
    if isinstance(candidates, list):
        summary["candidates"] = [
            {
                "place_id": item.get("place_id"),
                "display_name": item.get("display_name"),
            }
            for item in candidates
            if isinstance(item, dict)
        ]
    for key in (
        "estimate_id",
        "fare_amount",
        "currency",
        "eta_minutes",
        "booking_id",
        "status",
    ):
        if key in data:
            output_key = "backend_status" if key == "status" else key
            summary[output_key] = data[key]
    return summary


class TracingToolExecutor(AgentToolExecutor):
    """Production executor plus a redacted per-call evidence trail."""

    def __init__(self, *, pricing: PricingService) -> None:
        super().__init__(pricing=pricing, booking_service=BookingService())
        self._durable = False
        self._quotes = InMemoryQuoteService(pricing)
        self.calls: list[dict[str, object]] = []

    async def execute(
        self,
        tool_call: ToolCall,
        *,
        session_id: str,
        user_id: str | None,
        agent_state: AgentState,
    ) -> ToolResult:
        result = await super().execute(
            tool_call,
            session_id=session_id,
            user_id=user_id,
            agent_state=agent_state,
        )
        self.calls.append(
            {
                "tool": tool_call.tool_name.value,
                "params": _safe_tool_params(tool_call),
                "result": _tool_result_summary(result),
            }
        )
        return result


async def _persist_eval_handoff(
    session: dict[str, object],
    agent_state: AgentState,
    action: AgentAction,
) -> None:
    """Avoid external persistence while preserving the response contract."""

    del agent_state
    if action.action_type is ActionType.HANDOFF:
        session["handoff_id"] = "handoff_eval_operator"


@dataclass
class WorkflowHarness:
    service: SessionService
    session_id: str
    model: ScriptedConversationModel
    executor: TracingToolExecutor
    turn_number: int = 0

    async def turn(self, user_message: str) -> dict[str, object]:
        self.turn_number += 1
        model_start = len(self.model.calls)
        tool_start = len(self.executor.calls)
        response = await self.service.process_message(
            self.session_id,
            user_message,
            source="TEXT",
        )
        session = self.service.get_session(self.session_id)
        raw_state = session.get("agent_state")
        assert isinstance(raw_state, dict)
        return {
            "turn": self.turn_number,
            "user": user_message,
            "assistant": {
                "action": response["action"],
                "message": response["message"],
                "booking": response.get("booking"),
            },
            "semantic_decisions": self.model.calls[model_start:],
            "backend_tools": self.executor.calls[tool_start:],
            "state_after_turn": _state_snapshot(raw_state),
        }


def _new_harness(*decisions: ModelDecision) -> WorkflowHarness:
    SessionService.sessions.clear()
    model = ScriptedConversationModel(*decisions)
    executor = TracingToolExecutor(pricing=PricingService())
    service = SessionService()
    service._durable = False
    service._agent = LLMAgent(conversation_model=model)
    service._tool_executor = executor
    service._persist_handoff = _persist_eval_handoff  # type: ignore[method-assign]
    session_id = str(
        service.create_session(
            "usr_agent_eval",
            "WEB_TEXT",
            phone="0901234567",
        )["session_id"]
    )
    return WorkflowHarness(service, session_id, model, executor)


def _place_snapshot(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return {
        "place_id": value.get("place_id"),
        "display_name": value.get("display_name"),
        "address": value.get("address"),
    }


def _state_snapshot(raw_state: dict[str, object]) -> dict[str, object]:
    collected = raw_state.get("collected_data")
    collected = collected if isinstance(collected, dict) else {}
    booking = collected.get("booking")
    booking = booking if isinstance(booking, dict) else {}
    handoff = collected.get("handoff")
    handoff = handoff if isinstance(handoff, dict) else None
    return {
        "workflow": raw_state.get("current_workflow"),
        "step": raw_state.get("current_step"),
        "confirmation": raw_state.get("confirmation"),
        "booking": {
            "pickup_query": booking.get("pickup_query"),
            "pickup": _place_snapshot(booking.get("pickup")),
            "destination_query": booking.get("destination_query"),
            "destination": _place_snapshot(booking.get("destination")),
            "vehicle_type": booking.get("vehicle_type"),
            "fare_estimate_id": booking.get("fare_estimate_id"),
            "fare_amount": booking.get("estimated_fare_amount"),
            "currency": booking.get("estimated_currency"),
            "booking_id": booking.get("booking_id"),
            "booking_status": booking.get("booking_status"),
        },
        "handoff": (
            {
                "reason_code": handoff.get("reason_code"),
                "source_workflow": handoff.get("source_workflow"),
                "priority": handoff.get("priority"),
                "severity": handoff.get("severity"),
                "queue": handoff.get("queue"),
            }
            if handoff is not None
            else None
        ),
    }


def _assertion(
    assertions: list[dict[str, object]],
    name: str,
    actual: object,
    expected: object,
) -> None:
    assertions.append(
        {
            "name": name,
            "passed": actual == expected,
            "expected": expected,
            "actual": actual,
        }
    )


def _tool_names(turn: dict[str, object]) -> list[str]:
    calls = turn["backend_tools"]
    assert isinstance(calls, list)
    return [str(call["tool"]) for call in calls if isinstance(call, dict)]


def _decision_names(turn: dict[str, object]) -> list[str]:
    calls = turn["semantic_decisions"]
    assert isinstance(calls, list)
    return [
        str(call["tool"])
        for call in calls
        if isinstance(call, dict) and "tool" in call
    ]


def _state(turn: dict[str, object]) -> dict[str, object]:
    state = turn["state_after_turn"]
    assert isinstance(state, dict)
    return state


def _booking(turn: dict[str, object]) -> dict[str, object]:
    booking = _state(turn)["booking"]
    assert isinstance(booking, dict)
    return booking


def _place_name(booking: dict[str, object], field: str) -> object:
    place = booking[field]
    assert isinstance(place, dict)
    return place["display_name"]


async def _base_booking_turns(harness: WorkflowHarness) -> list[dict[str, object]]:
    return [
        await harness.turn("Cho tôi xe 4 chỗ từ VinUni tới Hồ Gươm"),
        await harness.turn("Tôi chọn cổng chính VinUni"),
        await harness.turn("Tôi chọn Bưu điện Hà Nội"),
    ]


async def case_happy_path() -> dict[str, object]:
    harness = _new_harness(
        tool(
            "update_booking",
            pickup_query="VinUni",
            destination_query="Hồ Gươm",
            vehicle_type="CAR_4",
        ),
        tool("select_place", target="pickup", index=1),
        tool("select_place", target="destination", index=2),
    )
    conversation = await _base_booking_turns(harness)
    conversation.append(await harness.turn("Xác nhận"))
    assertions: list[dict[str, object]] = []
    _assertion(
        assertions,
        "state progression",
        [_state(turn)["step"] for turn in conversation],
        ["SELECT_PICKUP_CANDIDATE", "SELECT_DESTINATION_CANDIDATE", "CONFIRM", None],
    )
    final_booking = _booking(conversation[-1])
    _assertion(
        assertions,
        "pickup resolved",
        _place_name(final_booking, "pickup"),
        "Cổng chính VinUni",
    )
    _assertion(
        assertions,
        "destination resolved",
        _place_name(final_booking, "destination"),
        "Bưu điện Hà Nội",
    )
    _assertion(assertions, "vehicle retained", final_booking["vehicle_type"], "CAR_4")
    _assertion(
        assertions,
        "booking confirmed",
        final_booking["booking_status"],
        "CONFIRMED",
    )
    _assertion(
        assertions,
        "final backend call",
        _tool_names(conversation[-1]),
        ["create_booking"],
    )
    _assertion(assertions, "all scripted decisions consumed", len(harness.model.decisions), 0)
    return {"conversation": conversation, "assertions": assertions}


async def case_change_pickup() -> dict[str, object]:
    harness = _new_harness(
        tool(
            "update_booking",
            pickup_query="VinUni",
            destination_query="Hồ Gươm",
            vehicle_type="CAR_4",
        ),
        tool("select_place", target="pickup", index=1),
        tool("select_place", target="destination", index=2),
        tool("update_booking", pickup_query="Ga Hà Nội"),
    )
    conversation = await _base_booking_turns(harness)
    old_fare_id = _booking(conversation[-1])["fare_estimate_id"]
    conversation.append(await harness.turn("Không"))
    conversation.append(await harness.turn("Đổi điểm đón sang Ga Hà Nội"))
    correction = conversation[-1]
    conversation.append(await harness.turn("Xác nhận"))
    corrected = _booking(correction)
    assertions: list[dict[str, object]] = []
    _assertion(
        assertions,
        "new pickup resolved",
        _place_name(corrected, "pickup"),
        "Ga Hà Nội",
    )
    _assertion(
        assertions,
        "destination preserved",
        _place_name(corrected, "destination"),
        "Bưu điện Hà Nội",
    )
    _assertion(assertions, "vehicle preserved", corrected["vehicle_type"], "CAR_4")
    _assertion(assertions, "new confirmation requested", _state(correction)["step"], "CONFIRM")
    _assertion(
        assertions,
        "correction semantic flow",
        _decision_names(correction),
        ["update_booking"],
    )
    _assertion(
        assertions,
        "route and fare recalculated",
        _tool_names(correction),
        ["search_place", "estimate_fare"],
    )
    _assertion(
        assertions,
        "old fare invalidated",
        corrected["fare_estimate_id"] == old_fare_id,
        False,
    )
    _assertion(
        assertions,
        "booking only after reconfirmation",
        _tool_names(conversation[-1]),
        ["create_booking"],
    )
    _assertion(
        assertions,
        "final status",
        _booking(conversation[-1])["booking_status"],
        "CONFIRMED",
    )
    _assertion(assertions, "all scripted decisions consumed", len(harness.model.decisions), 0)
    return {"conversation": conversation, "assertions": assertions}


async def case_change_destination() -> dict[str, object]:
    harness = _new_harness(
        tool(
            "update_booking",
            pickup_query="VinUni",
            destination_query="Hồ Gươm",
            vehicle_type="CAR_4",
        ),
        tool("select_place", target="pickup", index=1),
        tool("select_place", target="destination", index=2),
        tool("update_booking", destination_query="Ga Hà Nội"),
    )
    conversation = await _base_booking_turns(harness)
    old_fare_id = _booking(conversation[-1])["fare_estimate_id"]
    conversation.append(await harness.turn("Không"))
    conversation.append(await harness.turn("Đổi điểm đến sang Ga Hà Nội"))
    correction = conversation[-1]
    conversation.append(await harness.turn("Xác nhận"))
    corrected = _booking(correction)
    assertions: list[dict[str, object]] = []
    _assertion(
        assertions,
        "pickup preserved",
        _place_name(corrected, "pickup"),
        "Cổng chính VinUni",
    )
    _assertion(
        assertions,
        "new destination resolved",
        _place_name(corrected, "destination"),
        "Ga Hà Nội",
    )
    _assertion(assertions, "vehicle preserved", corrected["vehicle_type"], "CAR_4")
    _assertion(assertions, "new confirmation requested", _state(correction)["step"], "CONFIRM")
    _assertion(
        assertions,
        "correction semantic flow",
        _decision_names(correction),
        ["update_booking"],
    )
    _assertion(
        assertions,
        "route and fare recalculated",
        _tool_names(correction),
        ["search_place", "estimate_fare"],
    )
    _assertion(
        assertions,
        "old fare invalidated",
        corrected["fare_estimate_id"] == old_fare_id,
        False,
    )
    _assertion(
        assertions,
        "booking only after reconfirmation",
        _tool_names(conversation[-1]),
        ["create_booking"],
    )
    _assertion(
        assertions,
        "final status",
        _booking(conversation[-1])["booking_status"],
        "CONFIRMED",
    )
    _assertion(assertions, "all scripted decisions consumed", len(harness.model.decisions), 0)
    return {"conversation": conversation, "assertions": assertions}


async def case_change_vehicle() -> dict[str, object]:
    harness = _new_harness(
        tool(
            "update_booking",
            pickup_query="VinUni",
            destination_query="Hồ Gươm",
            vehicle_type="CAR_4",
        ),
        tool("select_place", target="pickup", index=1),
        tool("select_place", target="destination", index=2),
        tool("update_booking", vehicle_type="CAR_7"),
    )
    conversation = await _base_booking_turns(harness)
    old_fare_id = _booking(conversation[-1])["fare_estimate_id"]
    conversation.append(await harness.turn("Không"))
    conversation.append(await harness.turn("Đổi sang xe 7 chỗ"))
    correction = conversation[-1]
    conversation.append(await harness.turn("Xác nhận"))
    corrected = _booking(correction)
    assertions: list[dict[str, object]] = []
    _assertion(
        assertions,
        "pickup preserved",
        _place_name(corrected, "pickup"),
        "Cổng chính VinUni",
    )
    _assertion(
        assertions,
        "destination preserved",
        _place_name(corrected, "destination"),
        "Bưu điện Hà Nội",
    )
    _assertion(assertions, "vehicle changed", corrected["vehicle_type"], "CAR_7")
    _assertion(assertions, "new confirmation requested", _state(correction)["step"], "CONFIRM")
    _assertion(
        assertions,
        "vehicle correction semantic flow",
        _decision_names(correction),
        ["update_booking"],
    )
    _assertion(
        assertions,
        "only fare recalculated",
        _tool_names(correction),
        ["estimate_fare"],
    )
    _assertion(
        assertions,
        "old fare invalidated",
        corrected["fare_estimate_id"] == old_fare_id,
        False,
    )
    _assertion(
        assertions,
        "booking only after reconfirmation",
        _tool_names(conversation[-1]),
        ["create_booking"],
    )
    _assertion(
        assertions,
        "final status",
        _booking(conversation[-1])["booking_status"],
        "CONFIRMED",
    )
    _assertion(assertions, "all scripted decisions consumed", len(harness.model.decisions), 0)
    return {"conversation": conversation, "assertions": assertions}


async def case_out_of_scope() -> dict[str, object]:
    message = (
        "Mình chỉ hỗ trợ đặt xe và các vấn đề chuyến đi của AloSM. "
        "Bạn có muốn đặt một chuyến xe không?"
    )
    harness = _new_harness(tool("respond", message=message, expects_response=True))
    conversation = [
        await harness.turn("Viết giúp tôi một chương trình Python quản lý kho")
    ]
    turn = conversation[0]
    assistant = turn["assistant"]
    assert isinstance(assistant, dict)
    assertions: list[dict[str, object]] = []
    _assertion(assertions, "polite scoped response", assistant["message"], message)
    _assertion(assertions, "asks whether to book", assistant["action"], "ASK_USER")
    _assertion(assertions, "no workflow started", _state(turn)["workflow"], None)
    _assertion(assertions, "no backend tool called", _tool_names(turn), [])
    _assertion(assertions, "typed respond used", _decision_names(turn), ["respond"])
    _assertion(assertions, "all scripted decisions consumed", len(harness.model.decisions), 0)
    return {"conversation": conversation, "assertions": assertions}


async def case_operator_handoff() -> dict[str, object]:
    harness = _new_harness(
        tool("update_booking", vehicle_type="CAR_4"),
        tool(
            "respond",
            message="Bạn muốn đón ở đâu và đi đến đâu?",
            expects_response=True,
        ),
        tool(
            "handoff",
            reason="Khách yêu cầu gặp tổng đài viên",
            reason_code="USER_REQUEST",
        ),
    )
    conversation = [
        await harness.turn("Tôi muốn đặt xe 4 chỗ"),
        await harness.turn("Tôi muốn gặp tổng đài viên"),
    ]
    first, handoff_turn = conversation
    handoff = _state(handoff_turn)["handoff"]
    assistant = handoff_turn["assistant"]
    assert isinstance(handoff, dict)
    assert isinstance(assistant, dict)
    assertions: list[dict[str, object]] = []
    _assertion(assertions, "booking context started", _state(first)["workflow"], "RIDE_BOOKING")
    _assertion(assertions, "handoff response", assistant["action"], "HANDOFF")
    _assertion(assertions, "handoff semantic tool", _decision_names(handoff_turn), ["handoff"])
    _assertion(assertions, "handoff workflow", _state(handoff_turn)["workflow"], "HUMAN_HANDOFF")
    _assertion(assertions, "reason code", handoff["reason_code"], "USER_REQUEST")
    _assertion(assertions, "original workflow transferred", handoff["source_workflow"], "RIDE_BOOKING")
    _assertion(assertions, "operator queue", handoff["queue"], "GENERAL_OPERATOR")
    _assertion(assertions, "no booking side effect", _tool_names(handoff_turn), [])
    _assertion(assertions, "all scripted decisions consumed", len(harness.model.decisions), 0)
    return {"conversation": conversation, "assertions": assertions}


CaseCallable = Callable[[], Awaitable[dict[str, object]]]


@dataclass(frozen=True)
class CaseDefinition:
    case_id: str
    slug: str
    title: str
    goal: str
    function: CaseCallable


CASE_DEFINITIONS = [
    CaseDefinition(
        "AGENT-001",
        "happy-path",
        "Happy path đặt xe",
        "Hoàn tất VinUni → Hồ Gươm sau xác nhận rõ ràng.",
        case_happy_path,
    ),
    CaseDefinition(
        "AGENT-002",
        "change-pickup",
        "Đổi điểm đón giữa chừng",
        "Đổi điểm đón, báo giá lại và chỉ booking sau xác nhận mới.",
        case_change_pickup,
    ),
    CaseDefinition(
        "AGENT-003",
        "change-destination",
        "Đổi điểm đến giữa chừng",
        "Giữ điểm đón, đổi điểm đến và tạo lại bản xác nhận.",
        case_change_destination,
    ),
    CaseDefinition(
        "AGENT-004",
        "change-vehicle",
        "Đổi loại xe giữa chừng",
        "Đổi CAR_4 sang CAR_7 và chỉ tính lại giá cần thiết.",
        case_change_vehicle,
    ),
    CaseDefinition(
        "AGENT-005",
        "out-of-scope",
        "Yêu cầu ngoài phạm vi",
        "Từ chối lịch sự, không tạo workflow hay gọi backend.",
        case_out_of_scope,
    ),
    CaseDefinition(
        "AGENT-006",
        "operator-handoff",
        "Handoff tổng đài viên",
        "Chuyển booking context đang dở tới đúng hàng đợi người thật.",
        case_operator_handoff,
    ),
]


async def execute_case(definition: CaseDefinition) -> dict[str, object]:
    started = datetime.now(UTC)
    try:
        result = await definition.function()
        assertions = result.get("assertions")
        assert isinstance(assertions, list)
        passed = all(
            isinstance(assertion, dict) and assertion.get("passed") is True
            for assertion in assertions
        )
        return {
            "id": definition.case_id,
            "title": definition.title,
            "goal": definition.goal,
            "status": "passed" if passed else "failed",
            "duration_ms": round(
                (datetime.now(UTC) - started).total_seconds() * 1000,
                3,
            ),
            **result,
        }
    except Exception as exc:
        return {
            "id": definition.case_id,
            "title": definition.title,
            "goal": definition.goal,
            "status": "error",
            "duration_ms": round(
                (datetime.now(UTC) - started).total_seconds() * 1000,
                3,
            ),
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }


def run_selected_pytest() -> dict[str, object]:
    command = [sys.executable, "-m", "pytest", "-q", *SELECTED_TESTS]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(
        part.strip()
        for part in (completed.stdout, completed.stderr)
        if part.strip()
    )
    return {
        "command": " ".join(command),
        "selected_tests": SELECTED_TESTS,
        "exit_code": completed.returncode,
        "output": output,
    }


async def main() -> int:
    cases = [await execute_case(definition) for definition in CASE_DEFINITIONS]
    pytest_result = run_selected_pytest()
    passed = sum(case["status"] == "passed" for case in cases)
    generated_at = datetime.now(UTC).isoformat()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for stale_path in RESULTS_DIR.glob("*.json"):
        stale_path.unlink()

    case_files: list[dict[str, str]] = []
    for definition, case in zip(CASE_DEFINITIONS, cases, strict=True):
        path = RESULTS_DIR / f"{definition.slug}.json"
        artifact = {
            "schema_version": "2.0",
            "generated_at": generated_at,
            "mode": "offline_deterministic_agent_workflow",
            "case": case,
        }
        path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        case_files.append(
            {
                "id": definition.case_id,
                "status": str(case["status"]),
                "path": str(path.relative_to(PROJECT_ROOT)),
            }
        )

    artifact = {
        "schema_version": "2.0",
        "generated_at": generated_at,
        "mode": "offline_deterministic_agent_workflow",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "summary": {
            "cases": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pytest_exit_code": pytest_result["exit_code"],
            "overall_status": (
                "passed"
                if passed == len(cases) and pytest_result["exit_code"] == 0
                else "failed"
            ),
        },
        "pytest": pytest_result,
        "case_files": case_files,
    }
    ARTIFACT_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"EVAL_ARTIFACT={ARTIFACT_PATH.relative_to(PROJECT_ROOT)}")
    print(json.dumps(artifact["summary"], ensure_ascii=False))
    return 0 if artifact["summary"]["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
