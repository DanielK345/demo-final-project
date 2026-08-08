from src.backend.agents.state import AgentState


async def booking_node(state: AgentState) -> dict:
    _ = state
    return {"booking_id": None}
