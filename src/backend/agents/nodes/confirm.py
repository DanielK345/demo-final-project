from src.backend.agents.state import AgentState


async def confirm_node(state: AgentState) -> dict:
    _ = state
    return {"confirmation_status": "pending"}
