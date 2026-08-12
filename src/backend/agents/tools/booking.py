<<<<<<< HEAD:src/backend/agents/tools/booking.py
async def create_booking(payload: dict[str, object]) -> dict[str, object]:
    return {"status": "pending", "payload": payload}
=======
from typing import Any

from src.agents.schemas import ToolCall, ToolName
from src.agents.tools.base import BaseTool
from src.agents.tools.schemas import CreateBookingParams


class CreateBookingTool(BaseTool):
    tool_name = ToolName.CREATE_BOOKING

    def build_call(self, call_id: str, **params: Any) -> ToolCall:
        validated = CreateBookingParams.model_validate(params)
        return ToolCall(
            tool_name=self.tool_name,
            call_id=call_id,
            params=validated.model_dump(),
        )
>>>>>>> 8cd3a39b010f5ca897c1f87bdcc03f29e9a49cc0:src/agents/tools/booking.py
