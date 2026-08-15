import re

from src.agents.contracts.schemas import ToolName, WorkflowType

_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_-]+$")


def build_call_id(
    *,
    session_id: str,
    workflow: WorkflowType,
    tool_name: ToolName,
    operation: str,
    sequence: int,
) -> str:
    """Build a correlatable ID without keeping process-local counters."""
    if sequence < 1:
        raise ValueError("call sequence must be positive")

    components = {
        "session_id": session_id,
        "operation": operation,
    }
    for name, value in components.items():
        if not value or not _SAFE_COMPONENT.fullmatch(value):
            raise ValueError(f"{name} contains unsupported characters")

    return ":".join(
        (
            session_id,
            workflow.value.lower(),
            tool_name.value,
            operation,
            str(sequence),
        )
    )
