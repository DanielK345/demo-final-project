from src.agents.state import AgentState


async def intent_node(state: AgentState) -> dict:
    _ = state
    return {"intent": "booking"}
