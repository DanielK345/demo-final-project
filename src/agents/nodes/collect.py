from src.agents.state import AgentState


async def collect_node(state: AgentState) -> dict:
    _ = state
    return {"failed_count": 0}
