from __future__ import annotations

from uuid import uuid4

from src.agents.schemas import ToolCall, ToolName, ToolResult, ToolStatus
from src.backend.services.booking_service import BookingService


class AgentToolExecutor:
    """MVP tool executor for Core Agent actions in the web session flow."""

    _FAQ_DOCUMENTS = [
        {
            "content": "Khách có thể thanh toán bằng tiền mặt hoặc chuyển khoản.",
            "source": "approved-faq",
            "score": 0.92,
        },
        {
            "content": "Giá cước được ước tính trước khi xác nhận đặt xe.",
            "source": "approved-faq",
            "score": 0.88,
        },
    ]

    async def execute(self, tool_call: ToolCall, *, session_id: str) -> ToolResult:
        try:
            data = await self._dispatch(tool_call, session_id=session_id)
            return ToolResult(
                tool_name=tool_call.tool_name,
                call_id=tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data=data,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=tool_call.tool_name,
                call_id=tool_call.call_id,
                status=ToolStatus.ERROR,
                data={},
                error=str(exc),
                error_code="EXECUTOR_ERROR",
                retryable=True,
            )

    async def _dispatch(self, tool_call: ToolCall, *, session_id: str) -> dict[str, object]:
        params = tool_call.params
        if tool_call.tool_name is ToolName.SEARCH_PLACE:
            query = str(params["query"])
            place_id = f"place_{uuid4().hex[:8]}"
            return {
                "candidates": [
                    {
                        "place_id": place_id,
                        "display_name": query,
                        "address": query,
                    }
                ]
            }
        if tool_call.tool_name is ToolName.CREATE_BOOKING:
            booking = BookingService().create_booking(
                {
                    "idempotency_key": f"{session_id}:create_booking:1",
                    "estimated_fare": 85000,
                }
            )
            return {
                "booking_id": booking["booking_id"],
                "status": "CONFIRMED",
                "eta_minutes": booking.get("eta_minutes", 5),
                "fare_amount": booking.get("estimated_fare", 85000),
                "currency": "VND",
            }
        if tool_call.tool_name is ToolName.LOOKUP_TRIP:
            booking_id = params.get("booking_id") or "GSM-DEMO"
            return {
                "found": True,
                "booking_id": booking_id,
                "status": "Đang đến điểm đón",
                "eta_minutes": 4,
            }
        if tool_call.tool_name is ToolName.RETRIEVE_KNOWLEDGE:
            return {"documents": self._FAQ_DOCUMENTS}
        if tool_call.tool_name is ToolName.CREATE_HANDOFF:
            return {"handoff_id": f"handoff_{uuid4().hex[:8]}", "status": "pending"}
        raise ValueError(f"Unsupported tool: {tool_call.tool_name}")
