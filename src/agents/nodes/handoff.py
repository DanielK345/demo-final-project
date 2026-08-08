from src.agents.state import AgentState


async def handoff_node(state: AgentState) -> dict:
    _ = state
    return {"handoff_triggered": True}
