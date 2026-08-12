from typing import Any

from pydantic import ValidationError

from src.agents.rag.answer_generator import (
    ExtractiveAnswerGenerator,
    GroundedAnswerGenerator,
)
from src.agents.schemas import (
    ActionType,
    AgentAction,
    AgentInput,
    ToolName,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.tools.call_id import build_call_id
from src.agents.tools.knowledge import RetrieveKnowledgeTool
from src.agents.tools.lifecycle import (
    ToolLifecycleError,
    clear_pending_tool_updates,
    correlate_tool_result,
    normalize_tool_failure,
    parse_tool_result,
    pending_tool_updates,
)
from src.agents.tools.schemas import KnowledgeDocument, RetrieveKnowledgeResult
from src.agents.understanding.models import UnderstandingResult
from src.agents.workflows.base import BaseWorkflow
from src.agents.workflows.faq_models import FAQData, FAQStep
from src.agents.workflows.handoff import HandoffWorkflow


class FAQWorkflow(BaseWorkflow):
    workflow_type = WorkflowType.FAQ
    data_key = "faq"

    def __init__(
        self,
        knowledge_tool: RetrieveKnowledgeTool | None = None,
        answer_generator: GroundedAnswerGenerator | None = None,
        *,
        min_score: float = 0.75,
        top_k: int = 3,
        max_retry_count: int = 2,
    ) -> None:
        if not 0 <= min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")
        if top_k < 1 or max_retry_count < 1:
            raise ValueError("FAQ limits must be positive")
        self.knowledge_tool = knowledge_tool or RetrieveKnowledgeTool()
        self.answer_generator = answer_generator or ExtractiveAnswerGenerator()
        self.min_score = min_score
        self.top_k = top_k
        self.max_retry_count = max_retry_count

    async def handle(
        self,
        agent_input: AgentInput,
        state: AgentState,
        understanding: UnderstandingResult | None = None,
    ) -> AgentAction:
        del understanding
        if agent_input.session_id != state.session_id:
            raise ValueError("agent input and state must belong to the same session")

        try:
            data = self._load_data(state)
        except ValidationError:
            return await self._handoff(agent_input, state, "Invalid FAQ state")

        if agent_input.tool_result is not None:
            return await self._handle_tool_result(agent_input, state, data)

        if self._step(state) is FAQStep.WAITING_FOR_KNOWLEDGE:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Tôi đang tra cứu thông tin. Bạn vui lòng đợi một chút.",
                reason="The FAQ workflow is waiting for a knowledge result.",
            )
        if self._step(state) is FAQStep.COMPLETE:
            return AgentAction(
                action_type=ActionType.RESPOND,
                message=data.answer or "Thông tin đã được cung cấp.",
                reason="The FAQ workflow is already complete.",
            )

        question = agent_input.transcript.strip()
        if not question:
            return AgentAction(
                action_type=ActionType.ASK_USER,
                message="Bạn muốn hỏi thông tin gì về dịch vụ?",
                state_updates={
                    "current_workflow": self.workflow_type,
                    "current_step": None,
                },
                reason="An FAQ question is required before retrieval.",
            )
        data.question = question
        data.answer = None
        data.sources = []
        return self._request_knowledge(state, data)

    def _request_knowledge(
        self,
        state: AgentState,
        data: FAQData,
        *,
        retry_count: int | None = None,
    ) -> AgentAction:
        assert data.question is not None
        call_id = build_call_id(
            session_id=state.session_id,
            workflow=self.workflow_type,
            tool_name=ToolName.RETRIEVE_KNOWLEDGE,
            operation="faq",
            sequence=state.state_version + 1,
        )
        tool_call = self.knowledge_tool.build_call(
            call_id,
            query=data.question,
        )
        updates: dict[str, Any] = {
            "current_workflow": self.workflow_type,
            "collected_data": self._store_data(state, data),
            **pending_tool_updates(
                tool_call,
                waiting_step=FAQStep.WAITING_FOR_KNOWLEDGE.value,
            ),
        }
        if retry_count is not None:
            updates["retry_count"] = retry_count
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=tool_call,
            state_updates=updates,
            reason="FAQ responses require grounded knowledge.",
        )

    async def _handle_tool_result(
        self,
        agent_input: AgentInput,
        state: AgentState,
        data: FAQData,
    ) -> AgentAction:
        result = agent_input.tool_result
        assert result is not None
        try:
            correlate_tool_result(result, state)
        except ToolLifecycleError as exc:
            return await self._handoff(agent_input, state, str(exc))

        if self._step(state) is not FAQStep.WAITING_FOR_KNOWLEDGE:
            return await self._handoff(
                agent_input,
                state,
                "Knowledge result is not valid for the current FAQ step",
            )

        if result.status is ToolStatus.ERROR:
            failure = normalize_tool_failure(result, state)
            next_retry = state.retry_count + 1
            if failure.retryable and next_retry < self.max_retry_count:
                return self._request_knowledge(state, data, retry_count=next_retry)
            return await self._handoff(
                agent_input,
                state,
                f"Knowledge retrieval failed: {failure.message}",
            )

        try:
            payload = parse_tool_result(result, state)
        except ToolLifecycleError as exc:
            return await self._handoff(agent_input, state, str(exc))
        if not isinstance(payload, RetrieveKnowledgeResult):
            return await self._handoff(
                agent_input,
                state,
                "Unexpected payload type for FAQ retrieval",
            )

        documents = self._select_grounded_documents(payload.documents)
        if not documents:
            return self._fallback(state, data)

        answer = (
            await self.answer_generator.generate(
                question=data.question or "",
                documents=documents,
            )
        ).strip()
        if not answer:
            return self._fallback(state, data)

        data.answer = answer
        data.sources = list(dict.fromkeys(document.source for document in documents))
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=answer,
            state_updates={
                "current_workflow": None,
                "current_step": None,
                "collected_data": self._store_data(state, data),
                "retry_count": 0,
                **clear_pending_tool_updates(),
            },
            reason=(
                "FAQ answer is grounded in validated knowledge sources: "
                f"{', '.join(data.sources)}"
            ),
        )

    def _select_grounded_documents(
        self,
        documents: list[KnowledgeDocument],
    ) -> list[KnowledgeDocument]:
        grounded = [
            document
            for document in documents
            if document.score >= self.min_score and document.source.strip()
        ]
        grounded.sort(key=lambda document: document.score, reverse=True)
        return grounded[: self.top_k]

    def _fallback(self, state: AgentState, data: FAQData) -> AgentAction:
        data.answer = None
        data.sources = []
        return AgentAction(
            action_type=ActionType.RESPOND,
            message=(
                "Tôi chưa tìm thấy thông tin đủ tin cậy để trả lời. "
                "Bạn có thể yêu cầu gặp tổng đài viên để được hỗ trợ thêm."
            ),
            state_updates={
                "current_workflow": None,
                "current_step": None,
                "collected_data": self._store_data(state, data),
                **clear_pending_tool_updates(),
            },
            reason="No retrieved document met the grounding policy.",
        )

    async def _handoff(
        self,
        agent_input: AgentInput,
        state: AgentState,
        reason: str,
    ) -> AgentAction:
        action = await HandoffWorkflow().handle(agent_input, state)
        action.reason = reason
        return action

    def _load_data(self, state: AgentState) -> FAQData:
        return FAQData.model_validate(state.collected_data.get(self.data_key, {}))

    def _store_data(self, state: AgentState, data: FAQData) -> dict[str, Any]:
        collected_data = dict(state.collected_data)
        collected_data[self.data_key] = data.model_dump(mode="json")
        return collected_data

    @staticmethod
    def _step(state: AgentState) -> FAQStep | None:
        if state.current_step is None:
            return None
        try:
            return FAQStep(state.current_step)
        except ValueError:
            return None
