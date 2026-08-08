from typing import Any
from uuid import uuid4

from src.agents.agent import LLMAgent
from src.agents.schemas import AgentInput


class AgentGraphAdapter:
    """Compatibility adapter for the starter template's ``ainvoke`` API."""

    def __init__(self, llm_agent: LLMAgent | None = None) -> None:
        self.llm_agent = llm_agent or LLMAgent()

    async def ainvoke(self, values: dict[str, Any]) -> dict[str, Any]:
        query = str(values.get("query", ""))
        action = await self.llm_agent.handle(
            AgentInput(
                session_id=str(values.get("session_id") or uuid4()),
                transcript=query,
            )
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
