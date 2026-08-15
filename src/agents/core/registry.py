from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from src.agents.contracts.schemas import AgentAction, ToolName, ToolResult
from src.agents.core.model import ModelToolCall
from src.agents.core.session import TurnSession


@dataclass(frozen=True)
class ContinueToolLoop:
    event: dict[str, Any]


ToolOutcome = AgentAction | ContinueToolLoop


class ToolHandler(Protocol):
    def __call__(self, session: TurnSession, arguments: dict[str, Any]) -> ToolOutcome: ...


class ResultReducer(Protocol):
    def __call__(self, session: TurnSession, result: ToolResult) -> ToolOutcome: ...


@dataclass(frozen=True)
class RegisteredTool:
    definition: dict[str, Any]
    handler: ToolHandler
    available: Callable[[TurnSession], bool] = lambda _session: True

    @property
    def name(self) -> str:
        return str(self.definition["function"]["name"])


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._reducers: dict[ToolName, ResultReducer] = {}

    def register(self, tool: RegisteredTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate semantic tool: {tool.name}")
        self._tools[tool.name] = tool

    def register_reducer(self, tool_name: ToolName, reducer: ResultReducer) -> None:
        if tool_name in self._reducers:
            raise ValueError(f"duplicate result reducer: {tool_name.value}")
        self._reducers[tool_name] = reducer

    def definitions(self, session: TurnSession) -> list[dict[str, Any]]:
        return [tool.definition for tool in self._tools.values() if tool.available(session)]

    def invoke(self, session: TurnSession, call: ModelToolCall) -> ToolOutcome:
        tool = self._tools.get(call.name)
        if tool is None or not tool.available(session):
            return ContinueToolLoop({"policy_error": f"Tool {call.name} is not available."})
        return tool.handler(session, call.arguments)

    def reduce(self, session: TurnSession, result: ToolResult) -> ToolOutcome:
        reducer = self._reducers.get(result.tool_name)
        if reducer is None:
            return ContinueToolLoop({"tool_error": "No reducer is registered for this result."})
        return reducer(session, result)
