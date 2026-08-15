"""Compatibility wrapper for the Backend's legacy graph import.

The current Agent no longer uses LangGraph. Backend routes kept from the older
app still import ``src.agents.graph.agent`` and call ``ainvoke``; expose the new
turn adapter under the old names so BE/FE can remain unchanged.
"""

from src.agents.turn_adapter import AgentTurnAdapter, agent, build_turn_adapter

AgentGraphAdapter = AgentTurnAdapter

__all__ = ["AgentGraphAdapter", "AgentTurnAdapter", "agent", "build_turn_adapter"]
