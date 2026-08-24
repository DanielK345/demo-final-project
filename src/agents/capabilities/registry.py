from src.agents.capabilities.booking import register_booking
from src.agents.capabilities.common import register_common
from src.agents.capabilities.faq import register_faq
from src.agents.capabilities.trip_lookup import register_trip_lookup
from src.agents.core.policy import AgentPolicy
from src.agents.core.registry import ToolRegistry


def build_tool_registry(policy: AgentPolicy | None = None) -> ToolRegistry:
    active_policy = policy or AgentPolicy()
    registry = ToolRegistry()
    register_common(registry)
    register_booking(registry)
    register_trip_lookup(registry)
    register_faq(registry, active_policy)
    return registry
