"""Provider-independent model/tool loop for the service agent."""

from src.agents.capabilities import build_tool_registry
from src.agents.capabilities.common import handoff
from src.agents.contracts.schemas import ActionType, AgentAction, AgentInput, ToolName, ToolStatus
from src.agents.contracts.state import AgentState
from src.agents.core.booking.actions import request_fare_estimate_action
from src.agents.core.instructions import SERVICE_AGENT_INSTRUCTIONS
from src.agents.core.model import ConversationModel, ConversationModelError, ToolExchange
from src.agents.core.policy import AgentPolicy
from src.agents.core.registry import ContinueToolLoop, ToolRegistry
from src.agents.core.session import TurnSession
from src.agents.tools.builders import EstimateFareTool
from src.agents.tools.lifecycle import clear_pending_tool_updates, correlate_tool_result


class ModelDrivenAgent:
    """LLM selects semantic tools; capabilities enforce state and policy."""

    max_internal_decisions = 8

    def __init__(
        self,
        model: ConversationModel,
        registry: ToolRegistry | None = None,
        policy: AgentPolicy | None = None,
    ) -> None:
        self.policy = policy or AgentPolicy()
        self.model = model
        self.registry = registry or build_tool_registry(self.policy)

    async def handle(self, agent_input: AgentInput, state: AgentState) -> AgentAction:
        try:
            session = TurnSession.load(
                state,
                event={"user_transcript": agent_input.transcript.strip()},
            )
        except ValueError:
            session = TurnSession.load(AgentState(session_id=state.session_id), event={})
            return handoff(session, {"reason": "Invalid typed session state", "reason_code": "POLICY_BLOCK"})

        if agent_input.tool_result is not None:
            outcome = self._reduce_result(session, agent_input)
            if isinstance(outcome, AgentAction):
                return outcome
            session.event = outcome.event

        exchanges: list[ToolExchange] = []
        for _ in range(self.max_internal_decisions):
            # Passenger and luggage counts are optional booking preferences.  Once
            # the route and an explicit vehicle type are known, never let the
            # conversational model stall the flow by asking for those preferences:
            # obtain the required fare estimate instead.
            fare_action = self._required_fare_estimate(session)
            if fare_action is not None:
                return fare_action

            try:
                decision = await self.model.decide(
                    instructions=SERVICE_AGENT_INSTRUCTIONS,
                    context=session.public_context(),
                    tools=self.registry.definitions(session),
                    exchanges=exchanges,
                )
            except ConversationModelError:
                return self._handle_model_failure(session)

            if session.state.model_failure_count:
                session.updates["model_failure_count"] = 0

            if decision.message:
                if "booking" in session.state.collected_data:
                    session.persist("booking")
                return AgentAction(
                    action_type=ActionType.ASK_USER if "?" in decision.message else ActionType.RESPOND,
                    message=decision.message,
                    state_updates=session.updates,
                    reason="Model generated a conversational response from typed state.",
                )
            if decision.tool_call is None:
                return handoff(session, {"reason": "Conversation model returned no decision", "reason_code": "UNABLE_TO_CONTINUE"})

            outcome = self.registry.invoke(session, decision.tool_call)
            if isinstance(outcome, AgentAction):
                return outcome
            session.event = outcome.event
            exchanges.append(ToolExchange(decision.tool_call, outcome.event))

        return handoff(session, {"reason": "Internal model/tool loop limit reached", "reason_code": "RETRY_LIMIT"})

    @staticmethod
    def _required_fare_estimate(session: TurnSession) -> AgentAction | None:
        data = session.booking
        state = session.working_state()
        if (
            state.pending_tool_name is None
            and data.pickup is not None
            and data.destination is not None
            and data.vehicle_type is not None
            and data.fare_estimate_id is None
        ):
            return request_fare_estimate_action(state, data, EstimateFareTool())
        return None

    def _handle_model_failure(self, session: TurnSession) -> AgentAction:
        failures = session.working_state().model_failure_count + 1
        session.updates["model_failure_count"] = failures
        if failures < self.policy.max_model_failure_count:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message=(
                    "Hệ thống đang phản hồi chậm nên tôi chưa xử lý xong lượt này. "
                    "Thông tin bạn đã cung cấp vẫn được giữ; bạn vui lòng thử lại nhé?"
                ),
                state_updates=session.updates,
                reason="Transient conversation model failure; state retained for retry.",
            )
        return handoff(session, {"reason": "Conversation model repeatedly unavailable", "reason_code": "MODEL_UNAVAILABLE"})

    def _reduce_result(self, session: TurnSession, agent_input: AgentInput):
        result = agent_input.tool_result
        assert result is not None
        try:
            correlate_tool_result(result, session.state)
        except ValueError:
            return handoff(session, {"reason": "Tool result does not match pending call", "reason_code": "CRITICAL_TOOL_ERROR"})

        if result.status is ToolStatus.ERROR:
            if result.tool_name in {ToolName.CREATE_BOOKING, ToolName.CANCEL_BOOKING, ToolName.CREATE_HANDOFF}:
                return handoff(session, {"reason": "Side-effect tool failed and requires reconciliation", "reason_code": "SIDE_EFFECT_RECONCILIATION"})
            session.updates.update(clear_pending_tool_updates())
            session.updates.update(current_step=None, retry_count=session.state.retry_count + 1)
            return ContinueToolLoop({
                "tool_failure": {
                    "tool": result.tool_name.value,
                    "message": result.error,
                    "retryable": result.retryable,
                }
            })
        try:
            return self.registry.reduce(session, result)
        except ValueError:
            return handoff(session, {"reason": "Backend returned an invalid tool payload", "reason_code": "CRITICAL_TOOL_ERROR"})
