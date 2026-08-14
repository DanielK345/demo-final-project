"""Offline Core Agent demo with a mock Backend tool executor.

Run from the repository root:
    .venv/bin/python -m examples.core_agent_demo
"""

import asyncio
from typing import Any

from src.agents.graph import AgentGraphAdapter
from src.agents.history import acknowledge_assistant_delivery, build_message_id
from src.agents.schemas import ActionType, AgentAction, ToolResult, ToolStatus
from src.agents.state import (
    AgentState,
    AssistantDeliveryEvent,
    ConversationRole,
    DeliveryStatus,
)


class DemoSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.turn_sequence = 0
        self.state = AgentState(session_id=session_id)
        self.graph = AgentGraphAdapter()

    async def user(self, message: str, confidence: float = 0.98) -> AgentAction:
        print(f"USER: {message}")
        return await self._turn(query=message, stt_confidence=confidence)

    async def tool(self, result: ToolResult) -> AgentAction:
        print(f"TOOL: {result.tool_name.value} → {result.status.value}")
        return await self._turn(tool_result=result.model_dump(mode="json"))

    async def _turn(self, **values: Any) -> AgentAction:
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
        if action.action_type is ActionType.CALL_TOOL:
            assert action.tool_call is not None
            print(f"AGENT: CALL_TOOL {action.tool_call.tool_name.value}")
        else:
            print(f"AGENT: {action.action_type.value} — {action.message}")
        if action.action_type is not ActionType.CALL_TOOL and action.message:
            history = acknowledge_assistant_delivery(
                self.state.conversation_history,
                AssistantDeliveryEvent(
                    session_id=self.session_id,
                    turn_id=turn_id,
                    message_id=build_message_id(
                        turn_id,
                        ConversationRole.ASSISTANT,
                    ),
                    status=DeliveryStatus.DELIVERED,
                ),
                session_id=self.session_id,
            )
            self.state = self.state.apply({"conversation_history": history})
        print(f"HISTORY: {len(self.state.conversation_history)} messages")
        return action


def success(action: AgentAction, data: dict[str, Any]) -> ToolResult:
    assert action.tool_call is not None
    return ToolResult(
        tool_name=action.tool_call.tool_name,
        call_id=action.tool_call.call_id,
        status=ToolStatus.SUCCESS,
        data=data,
    )


async def booking_demo() -> None:
    print("\n=== BOOKING ===")
    session = DemoSession("demo-booking")
    await session.user("Tôi muốn đặt xe")
    pickup = await session.user("Hồ Gươm")
    await session.tool(
        success(
            pickup,
            {"candidates": [{"place_id": "p1", "display_name": "Hồ Gươm"}]},
        )
    )
    destination = await session.user("Times City")
    await session.tool(
        success(
            destination,
            {"candidates": [{"place_id": "p2", "display_name": "Times City"}]},
        )
    )
    fare = await session.user("Ô tô 4 chỗ")
    await session.tool(
        success(
            fare,
            {
                "estimate_id": "demo-fare-001",
                "fare_amount": 75000,
                "currency": "VND",
                "eta_minutes": 6,
            },
        )
    )
    await session.user("0901234567")
    booking = await session.user("Đúng, đặt giúp tôi")
    await session.tool(
        success(
            booking,
            {
                "booking_id": "demo-booking-001",
                "status": "CONFIRMED",
                "eta_minutes": 5,
            },
        )
    )


async def lookup_demo() -> None:
    print("\n=== TRIP LOOKUP ===")
    session = DemoSession("demo-trip")
    await session.user("Tra cứu chuyến của tôi")
    lookup = await session.user("Mã chuyến là GSM-12345")
    await session.tool(
        success(
            lookup,
            {
                "found": True,
                "booking_id": "GSM-12345",
                "status": "Đang đến điểm đón",
                "eta_minutes": 4,
            },
        )
    )


async def faq_demo() -> None:
    print("\n=== GROUNDED FAQ ===")
    session = DemoSession("demo-faq")
    retrieval = await session.user("Dịch vụ hỗ trợ thanh toán thế nào?")
    await session.tool(
        success(
            retrieval,
            {
                "documents": [
                    {
                        "content": "Khách có thể thanh toán bằng tiền mặt.",
                        "source": "demo-approved-faq",
                        "score": 0.92,
                    }
                ]
            },
        )
    )


async def handoff_demo() -> None:
    print("\n=== HUMAN HANDOFF ===")
    session = DemoSession("demo-handoff")
    action = await session.user("Tôi đang gặp nguy hiểm")
    assert action.action_type is ActionType.HANDOFF


async def main() -> None:
    await booking_demo()
    await lookup_demo()
    await faq_demo()
    await handoff_demo()


if __name__ == "__main__":
    asyncio.run(main())
