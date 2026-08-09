from typing import Any
from uuid import uuid4

from src.agents.agent import LLMAgent
from src.agents.schemas import AgentInput, ToolResult
from src.agents.state import AgentState


class AgentGraphAdapter:
    """Compatibility adapter for the starter template's ``ainvoke`` API."""

    def __init__(self, llm_agent: LLMAgent | None = None) -> None:
        self.llm_agent = llm_agent or LLMAgent()

    async def ainvoke(self, values: dict[str, Any]) -> dict[str, Any]:
        query = str(values.get("query", ""))
        raw_state = values.get("state")
        state = (
            AgentState.model_validate(raw_state)
            if raw_state is not None
            else None
        )
        raw_tool_result = values.get("tool_result")
        tool_result = (
            ToolResult.model_validate(raw_tool_result)
            if raw_tool_result is not None
            else None
        )
        session_id = str(
            values.get("session_id")
            or (state.session_id if state is not None else uuid4())
        )

        action = await self.llm_agent.handle(
            AgentInput(
                session_id=session_id,
                transcript=query,
                tool_result=tool_result,
            ),
            state,
        )
        return {
            **values,
            "response": action.message or "",
            "analysis": action.reason or "",
            "action": action.model_dump(mode="json"),
        }


def build_graph() -> AgentGraphAdapter:
    return AgentGraphAdapter()


agent = build_graph()
