"""Public Core Agent entrypoint.

The production path is deliberately small: model -> semantic tool -> policy ->
AgentAction. Backend remains the owner of state persistence and tool execution.
"""

from collections.abc import Mapping
from typing import Any

from src.agents.contracts.schemas import AgentAction, AgentInput, ToolName, WorkflowType
from src.agents.contracts.state import AgentState
from src.agents.core.agent import ModelDrivenAgent
from src.agents.core.guardrails import AgentGuardrails, GuardrailViolationError
from src.agents.core.history import record_turn_history
from src.agents.core.model import ConversationModel, build_conversation_model
from src.agents.core.turn_policy import TurnPolicy


class LLMAgent:
    """Handle one conversation turn without executing external work."""

    def __init__(
        self,
        *,
        conversation_model: ConversationModel | None = None,
        guardrails: AgentGuardrails | None = None,
        model_driven: bool | None = None,
        router: Any = None,
        workflows: Mapping[WorkflowType, Any] | None = None,
        understanding_service: Any = None,
        context_builder: Any = None,
        rewrite_gate: Any = None,
        message_rewriter: Any = None,
        dialogue_act_detector: Any = None,
        repair_handler: Any = None,
    ) -> None:
        """Build the production agent or the temporary offline legacy adapter.

        The extra injected arguments exist only while old deterministic tests are
        being migrated. They are lazy-loaded and never enter the production path.
        """
        legacy_inputs = {
            "router": router,
            "workflows": workflows,
            "understanding_service": understanding_service,
            "context_builder": context_builder,
            "rewrite_gate": rewrite_gate,
            "message_rewriter": message_rewriter,
            "dialogue_act_detector": dialogue_act_detector,
            "repair_handler": repair_handler,
        }
        use_legacy = model_driven is False or any(value is not None for value in legacy_inputs.values())
        if model_driven is None and conversation_model is None and not use_legacy:
            from src.config import get_settings

            use_legacy = not get_settings().agent_llm_enabled

        self.guardrails = guardrails or AgentGuardrails()
        self.turn_policy = TurnPolicy(self.guardrails.policy)
        self._legacy = None
        self._model_agent = None
        if use_legacy:
            from src.agents.legacy.agent import LegacyAgent

            self._legacy = LegacyAgent(guardrails=self.guardrails, **legacy_inputs)
        else:
            self._model_agent = ModelDrivenAgent(
                conversation_model or build_conversation_model(),
                policy=self.guardrails.policy,
            )

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState | None = None,
    ) -> AgentAction:
        if self._legacy is not None:
            return await self._legacy.handle(agent_input, state)

        current_state = state or AgentState(session_id=agent_input.session_id)
        if current_state.session_id != agent_input.session_id:
            raise ValueError("agent input and state must belong to the same session")
        policy_action = self.turn_policy.evaluate(agent_input, current_state)
        if policy_action is not None:
            return self._validate_action(agent_input, current_state, policy_action)
        assert self._model_agent is not None
        action = await self._model_agent.handle(agent_input, current_state)
        return self._validate_action(agent_input, current_state, action)

    def _validate_action(
        self,
        agent_input: AgentInput,
        state: AgentState,
        action: AgentAction,
    ) -> AgentAction:
        try:
            validated = self.guardrails.validate_and_sanitize(agent_input, state, action)
        except GuardrailViolationError as exc:
            if state.pending_tool_name in {
                ToolName.CREATE_BOOKING,
                ToolName.CANCEL_BOOKING,
                ToolName.CREATE_HANDOFF,
            }:
                validated = self.guardrails.safe_reconciliation_handoff(
                    f"Guardrail violation: {exc}"
                )
            else:
                validated = self.guardrails.safe_handoff(f"Guardrail violation: {exc}")
        return record_turn_history(agent_input, state, validated)


agent = LLMAgent()
