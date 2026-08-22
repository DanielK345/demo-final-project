"""Interactive stateful Core Agent chat with real LLMs and mock business tools.

Run from the repository root:
    .venv/bin/python -u -m examples.core_agent_chat
"""

import asyncio
import json
from enum import StrEnum
from typing import Any
from uuid import uuid4

from src.agents.graph import AgentGraphAdapter
from src.agents.history import acknowledge_assistant_delivery, build_message_id
from src.agents.location_policy import is_ambiguous_location_text
from src.agents.schemas import (
    ActionType,
    AgentAction,
    ToolCall,
    ToolName,
    ToolResult,
    ToolStatus,
)
from src.agents.state import (
    AgentState,
    AssistantDeliveryEvent,
    ConversationRole,
    DeliveryStatus,
)
from src.config import get_settings


class SessionTerminalStatus(StrEnum):
    ACTIVE = "ACTIVE"
    HANDOFF = "HANDOFF"
    ENDED = "ENDED"


class MockBackendExecutor:
    """Return deterministic fixtures while the Agent and LLM paths stay real."""

    async def execute(self, call: ToolCall) -> ToolResult:
        data = self._result_data(call)
        return ToolResult(
            tool_name=call.tool_name,
            call_id=call.call_id,
            status=ToolStatus.SUCCESS,
            data=data,
        )

    def _result_data(self, call: ToolCall) -> dict[str, Any]:
        if call.tool_name is ToolName.SEARCH_PLACE:
            return {"candidates": self._place_candidates(str(call.params["query"]))}
        if call.tool_name is ToolName.ESTIMATE_FARE:
            rates = {"MOTORBIKE": 45000, "CAR_4": 75000, "CAR_7": 105000}
            vehicle = str(call.params["vehicle_type"])
            return {
                "estimate_id": f"DEMO-FARE-{vehicle}",
                "fare_amount": rates[vehicle],
                "currency": "VND",
                "eta_minutes": 6,
                "distance_km": 12.5,
            }
        if call.tool_name is ToolName.GET_VEHICLE_OPTIONS:
            passenger_count = int(call.params["passenger_count"])
            catalog = [
                ("bike", "MOTORBIKE", "Xe máy", 1, 45000),
                ("car-4", "CAR_4", "Ô tô 4 chỗ", 4, 75000),
                ("car-7", "CAR_7", "Ô tô 7 chỗ", 7, 105000),
            ]
            return {
                "options": [
                    {
                        "option_id": option_id,
                        "vehicle_type": vehicle_type,
                        "display_name": display_name,
                        "capacity": capacity,
                        "available": True,
                        "estimate_id": f"DEMO-FARE-{vehicle_type}",
                        "fare_amount": fare,
                        "currency": "VND",
                        "eta_minutes": 6,
                    }
                    for option_id, vehicle_type, display_name, capacity, fare in catalog
                    if capacity >= passenger_count
                ]
            }
        if call.tool_name is ToolName.CREATE_BOOKING:
            fare_by_estimate = {
                "DEMO-FARE-MOTORBIKE": 45000,
                "DEMO-FARE-CAR_4": 75000,
                "DEMO-FARE-CAR_7": 105000,
            }
            return {
                "booking_id": "DEMO-BOOKING-001",
                "status": "CONFIRMED",
                "eta_minutes": 5,
                "fare_amount": fare_by_estimate.get(str(call.params["fare_estimate_id"])),
                "currency": "VND",
            }
        if call.tool_name is ToolName.CANCEL_BOOKING:
            return {
                "booking_id": str(call.params["booking_id"]),
                "status": "CANCELLED",
            }
        if call.tool_name is ToolName.LOOKUP_TRIP:
            if call.params.get("phone_number"):
                return {
                    "found": True,
                    "trips": [
                        {
                            "booking_id": "DEMO-BOOKING-001",
                            "status": "Đang đến điểm đón",
                            "eta_minutes": 4,
                            "pickup_label": "VinUniversity",
                            "destination_label": "Times City",
                        },
                        {
                            "booking_id": "DEMO-BOOKING-002",
                            "status": "Đã hoàn thành",
                            "pickup_label": "Royal City",
                            "destination_label": "Nhà hát Lớn",
                        },
                    ],
                }
            booking_id = str(call.params["booking_id"])
            return {
                "found": True,
                "booking_id": booking_id,
                "status": "Đang đến điểm đón",
                "eta_minutes": 4,
            }
        if call.tool_name is ToolName.RETRIEVE_KNOWLEDGE:
            return {
                "documents": [
                    {
                        "content": self._faq_answer(str(call.params["query"])),
                        "source": "interactive-demo-policy",
                        "score": 0.95,
                    }
                ]
            }
        if call.tool_name is ToolName.CREATE_HANDOFF:
            return {"handoff_id": "DEMO-HANDOFF-001", "status": "QUEUED"}
        raise ValueError(f"No mock result is configured for {call.tool_name.value}")

    @staticmethod
    def _place_candidates(query: str) -> list[dict[str, str]]:
        if is_ambiguous_location_text(query):
            return []
        normalized = query.casefold()
        if "hồ gươm" in normalized or "bờ hồ" in normalized:
            return [
                {"place_id": "place-ho-guom", "display_name": "Hồ Hoàn Kiếm"},
                {
                    "place_id": "place-pho-di-bo-ho-guom",
                    "display_name": "Phố đi bộ Hồ Gươm",
                },
            ]
        known_places = {
            "vinuni": ("place-vinuni", "VinUniversity"),
            "times city": ("place-times-city", "Times City"),
            "royal city": ("place-royal-city", "Royal City"),
            "nhà hát lớn": ("place-nha-hat-lon", "Nhà hát Lớn"),
            "nội bài": ("place-noi-bai", "Sân bay Nội Bài"),
            "ocean park": ("place-ocean-park", "Vinhomes Ocean Park"),
        }
        for phrase, (place_id, display_name) in known_places.items():
            if phrase in normalized:
                return [{"place_id": place_id, "display_name": display_name}]
        return []

    @staticmethod
    def _faq_answer(question: str) -> str:
        normalized = question.casefold()
        if "thanh toán" in normalized or "tiền mặt" in normalized:
            return "Khách có thể thanh toán bằng tiền mặt."
        if "ban đêm" in normalized or "hoạt động" in normalized:
            return "Dịch vụ hoạt động 24 giờ mỗi ngày."
        if "hủy" in normalized or "huỷ" in normalized:
            return "Phí hủy phụ thuộc trạng thái chuyến tại thời điểm hủy."
        return "Tổng đài hỗ trợ giải đáp các thông tin về dịch vụ đặt xe."


class InteractiveSession:
    def __init__(
        self,
        session_id: str,
        *,
        graph: AgentGraphAdapter | None = None,
        backend: MockBackendExecutor | None = None,
    ) -> None:
        self.session_id = session_id
        self.turn_sequence = 0
        self.state = AgentState(session_id=session_id)
        self.graph = graph or AgentGraphAdapter()
        self.backend = backend or MockBackendExecutor()
        self.terminal_status = SessionTerminalStatus.ACTIVE

    async def user_turn(self, transcript: str) -> list[AgentAction]:
        if self.terminal_status is not SessionTerminalStatus.ACTIVE:
            raise RuntimeError("session đã kết thúc; dùng /reset để bắt đầu session mới")
        actions: list[AgentAction] = []
        action = await self._invoke(query=transcript, stt_confidence=0.98)
        actions.append(action)
        while action.action_type is ActionType.CALL_TOOL:
            assert action.tool_call is not None
            print(
                f"TOOL CALL: {action.tool_call.tool_name.value} "
                f"{json.dumps(action.tool_call.params, ensure_ascii=False)}"
            )
            result = await self.backend.execute(action.tool_call)
            print(f"MOCK BACKEND: {result.tool_name.value} → {result.status.value}")
            action = await self._invoke(tool_result=result.model_dump(mode="json"))
            actions.append(action)
        return actions

    async def _invoke(self, **values: Any) -> AgentAction:
        self.turn_sequence += 1
        turn_id = f"turn-{self.turn_sequence:03d}"
        output = await self.graph.ainvoke(
            {
                "session_id": self.session_id,
                "turn_id": turn_id,
                "state": self.state.model_dump(mode="json"),
                **values,
            }
        )
        action = AgentAction.model_validate(output["action"])
        self.state = self.state.apply(action.state_updates)
        if action.action_type is ActionType.HANDOFF:
            self.terminal_status = SessionTerminalStatus.HANDOFF
        elif action.action_type is ActionType.END_SESSION:
            self.terminal_status = SessionTerminalStatus.ENDED
        if action.action_type is not ActionType.CALL_TOOL and action.message:
            print(f"AGENT: {action.message}")
            self._acknowledge_delivery(turn_id)
        return action

    def reset(self) -> None:
        self.session_id = f"interactive-{uuid4().hex[:8]}"
        self.turn_sequence = 0
        self.state = AgentState(session_id=self.session_id)
        self.terminal_status = SessionTerminalStatus.ACTIVE
        print(f"Đã tạo session mới: {self.session_id}")

    def _acknowledge_delivery(self, turn_id: str) -> None:
        history = acknowledge_assistant_delivery(
            self.state.conversation_history,
            AssistantDeliveryEvent(
                session_id=self.session_id,
                turn_id=turn_id,
                message_id=build_message_id(turn_id, ConversationRole.ASSISTANT),
                status=DeliveryStatus.DELIVERED,
            ),
            session_id=self.session_id,
        )
        self.state = self.state.apply({"conversation_history": history})

    def print_state(self) -> None:
        values = self.state.model_dump(
            mode="json",
            exclude={"conversation_history", "conversation_summary"},
        )
        print(json.dumps(values, ensure_ascii=False, indent=2))

    def print_history(self) -> None:
        if not self.state.conversation_history:
            print("History đang trống.")
            return
        for message in self.state.conversation_history:
            print(f"{message.turn_id} {message.role.value} [{message.delivery_status.value}]: {message.content}")

    def print_config(self) -> None:
        settings = get_settings()
        values = {
            "session_id": self.session_id,
            "terminal_status": self.terminal_status.value,
            "llm_understanding": settings.agent_llm_enabled,
            "llm_model": settings.agent_llm_model,
            "context_rewrite": settings.agent_rewrite_enabled,
            "rewrite_model": settings.agent_rewrite_model,
            "openai_api_key_configured": bool(settings.openai_api_key),
            "business_tools": "MOCK",
        }
        print(json.dumps(values, ensure_ascii=False, indent=2))


def _print_startup() -> None:
    settings = get_settings()
    print("Core Agent interactive chat")
    print(f"LLM understanding: {'ON' if settings.agent_llm_enabled else 'OFF'} ({settings.agent_llm_model})")
    print(f"Context rewrite: {'ON' if settings.agent_rewrite_enabled else 'OFF'} ({settings.agent_rewrite_model})")
    print("Business tools: MOCK")
    print("Commands: /state, /history, /config, /reset, /help, /quit")


async def main() -> None:
    _print_startup()
    session = InteractiveSession(f"interactive-{uuid4().hex[:8]}")
    while True:
        try:
            transcript = input("\nYOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nĐã kết thúc.")
            return
        if not transcript:
            continue
        if transcript == "/quit":
            print("Đã kết thúc.")
            return
        if transcript == "/state":
            session.print_state()
            continue
        if transcript == "/history":
            session.print_history()
            continue
        if transcript == "/config":
            session.print_config()
            continue
        if transcript == "/reset":
            session.reset()
            continue
        if transcript == "/help":
            print("/state xem state; /history xem history; /config xem cấu hình; /reset tạo session mới; /quit thoát.")
            continue
        if session.terminal_status is not SessionTerminalStatus.ACTIVE:
            print("Session đã kết thúc hoặc chuyển tổng đài. Dùng /reset để chat lại.")
            continue
        try:
            await session.user_turn(transcript)
        except Exception as exc:  # pragma: no cover - interactive boundary
            print(f"ERROR: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
