"""Stateless transport adapter for the Backend's existing ``ainvoke`` contract."""

from typing import Any
from uuid import uuid4

from src.agents.agent import LLMAgent
from src.agents.contracts.schemas import AgentInput, ToolResult
from src.agents.contracts.state import AgentState


class AgentTurnAdapter:
    """Normalize one Backend turn and invoke the Core Agent directly."""

    def __init__(self, llm_agent: LLMAgent | None = None) -> None:
        self.llm_agent = llm_agent or LLMAgent()

    async def ainvoke(self, values: dict[str, Any]) -> dict[str, Any]:
        query = str(values.get("query", ""))
        raw_state = values.get("state")
        state = AgentState.model_validate(raw_state) if raw_state is not None else None
        raw_result = values.get("tool_result")
        tool_result = ToolResult.model_validate(raw_result) if raw_result is not None else None
        session_id = str(values.get("session_id") or (state.session_id if state else uuid4()))
        raw_turn_id = values.get("turn_id")
        if not isinstance(raw_turn_id, str) or not raw_turn_id.strip():
            raise ValueError("turn_id is required")
        agent_input = AgentInput(
            session_id=session_id,
            turn_id=raw_turn_id.strip(),
            transcript=query,
            stt_confidence=values.get("stt_confidence"),
            tool_result=tool_result,
        )
        action = await self.llm_agent.handle(agent_input, state)
        return {
            **values,
            "response": action.message or "",
            "analysis": action.reason or "",
            "action": action.model_dump(mode="json"),
        }


def build_turn_adapter(llm_agent: LLMAgent | None = None) -> AgentTurnAdapter:
    return AgentTurnAdapter(llm_agent=llm_agent)


agent = build_turn_adapter()
