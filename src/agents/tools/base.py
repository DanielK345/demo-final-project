from abc import ABC, abstractmethod
from typing import Any

from src.agents.schemas import ToolCall, ToolName


class BaseTool(ABC):
    """Builds a tool request; execution remains the backend's responsibility."""

    tool_name: ToolName

    @abstractmethod
    def build_call(self, call_id: str, **params: Any) -> ToolCall:
        """Validate parameters and build the shared tool-call contract."""

