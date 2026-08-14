from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.agent import LLMAgent
from src.agents.schemas import AgentAction, AgentInput, ToolResult
from src.agents.state import AgentState


class AgentTurnGraphState(TypedDict, total=False):
    query: str
    session_id: str
    turn_id: str
    stt_confidence: float | None
    state: AgentState | dict[str, Any]
    tool_result: ToolResult | dict[str, Any]
    agent_input: AgentInput
    agent_state: AgentState | None
    action_model: AgentAction
    response: str
    analysis: str
    action: dict[str, Any]


class AgentGraphAdapter:
    """LangGraph-backed one-turn adapter; Backend remains state/tool owner."""

    def __init__(self, llm_agent: LLMAgent | None = None) -> None:
        self.llm_agent = llm_agent or LLMAgent()
        self.compiled_graph = self._compile()

    def _compile(self) -> CompiledStateGraph:
        builder = StateGraph(AgentTurnGraphState)
        builder.add_node("normalize_input", self._normalize_input)
        builder.add_node("invoke_core_agent", self._invoke_core_agent)
        builder.add_node("format_output", self._format_output)
        builder.add_edge(START, "normalize_input")
        builder.add_edge("normalize_input", "invoke_core_agent")
        builder.add_edge("invoke_core_agent", "format_output")
        builder.add_edge("format_output", END)
        return builder.compile()

    async def _normalize_input(
        self,
        values: AgentTurnGraphState,
    ) -> AgentTurnGraphState:
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
        raw_turn_id = values.get("turn_id")
        if not isinstance(raw_turn_id, str) or not raw_turn_id.strip():
            raise ValueError("turn_id is required")
        turn_id = raw_turn_id.strip()
        return {
            "agent_input": AgentInput(
                session_id=session_id,
                turn_id=turn_id,
                transcript=query,
                stt_confidence=values.get("stt_confidence"),
                tool_result=tool_result,
            ),
            "agent_state": state,
        }

    async def _invoke_core_agent(
        self,
        values: AgentTurnGraphState,
    ) -> AgentTurnGraphState:
        action = await self.llm_agent.handle(
            values["agent_input"],
            values.get("agent_state"),
        )
        return {"action_model": action}

    @staticmethod
    async def _format_output(
        values: AgentTurnGraphState,
    ) -> AgentTurnGraphState:
        action = values["action_model"]
        return {
            "response": action.message or "",
            "analysis": action.reason or "",
            "action": action.model_dump(mode="json"),
        }

    async def ainvoke(self, values: dict[str, Any]) -> dict[str, Any]:
        result = await self.compiled_graph.ainvoke(values)
        return {
            **values,
            "response": result.get("response", ""),
            "analysis": result.get("analysis", ""),
            "action": result["action"],
        }


def build_graph(llm_agent: LLMAgent | None = None) -> AgentGraphAdapter:
    return AgentGraphAdapter(llm_agent=llm_agent)


agent = build_graph()
