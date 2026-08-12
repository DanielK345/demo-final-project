from src.agents.state import AgentState


async def trip_status_node(state: AgentState) -> dict:
    _ = state
    return {"tool_result": {"status": "driver_arriving"}}
