from abc import ABC, abstractmethod

from src.agents.schemas import AgentAction, AgentInput, WorkflowType
from src.agents.state import AgentState
from src.agents.understanding.models import UnderstandingResult


class BaseWorkflow(ABC):
    workflow_type: WorkflowType

    @abstractmethod
    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState,
        understanding: UnderstandingResult | None = None,
    ) -> AgentAction:
        """Return the next backend action without performing side effects."""
