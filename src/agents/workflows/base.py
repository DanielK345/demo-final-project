from abc import ABC, abstractmethod

from src.agents.schemas import AgentAction, AgentInput, WorkflowType
from src.agents.state import AgentState


class BaseWorkflow(ABC):
    workflow_type: WorkflowType

    @abstractmethod
    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState,
    ) -> AgentAction:
        """Return the next backend action without performing side effects."""

