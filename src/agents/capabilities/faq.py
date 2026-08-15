from datetime import UTC, datetime

from pydantic import ValidationError

from src.agents.capabilities.common import policy_error
from src.agents.contracts.schemas import ActionType, AgentAction, ToolName, ToolResult, WorkflowType
from src.agents.core.policy import AgentPolicy
from src.agents.core.registry import ContinueToolLoop, RegisteredTool, ToolRegistry
from src.agents.core.session import TurnSession
from src.agents.core.tools import definition
from src.agents.tools.builders import RetrieveKnowledgeTool
from src.agents.tools.call_id import build_call_id
from src.agents.tools.lifecycle import clear_pending_tool_updates, parse_tool_result, pending_tool_updates
from src.agents.tools.schemas import RetrieveKnowledgeResult


def register_faq(registry: ToolRegistry, policy: AgentPolicy) -> None:
    builder = RetrieveKnowledgeTool()

    def retrieve(session: TurnSession, arguments: dict):
        query = str(arguments.get("query") or "").strip()
        try:
            call_id = build_call_id(
                session_id=session.state.session_id,
                workflow=WorkflowType.FAQ,
                tool_name=ToolName.RETRIEVE_KNOWLEDGE,
                operation="faq",
                sequence=session.state.state_version + 1,
            )
            call = builder.build_call(call_id, query=query)
        except (ValidationError, ValueError):
            return policy_error("Câu hỏi cần tra cứu không hợp lệ.")
        session.faq.question = query
        session.persist("faq")
        return AgentAction(
            action_type=ActionType.CALL_TOOL,
            tool_call=call,
            state_updates={
                **session.updates,
                "current_workflow": WorkflowType.FAQ,
                **pending_tool_updates(call, waiting_step="WAITING_FOR_KNOWLEDGE"),
            },
            reason="Backend owns retrieval; agent emitted a grounded knowledge request.",
        )

    def reduce(session: TurnSession, result: ToolResult):
        payload = parse_tool_result(result, session.state)
        assert isinstance(payload, RetrieveKnowledgeResult)
        now = datetime.now(UTC)
        documents = [
            item for item in payload.documents
            if item.score >= policy.min_knowledge_score
            and (item.effective_at is None or item.effective_at <= now)
            and (item.expires_at is None or item.expires_at > now)
        ][: policy.max_knowledge_documents]
        session.faq.sources = [item.source for item in documents]
        session.faq.citations = [item.citation_id or item.source for item in documents]
        session.persist("faq")
        session.updates.update(clear_pending_tool_updates())
        session.updates.update(current_step=None, retry_count=0)
        return ContinueToolLoop({
            "knowledge_result": [item.model_dump(mode="json") for item in documents],
            "grounding_rule": "Chỉ trả lời từ tài liệu này; nếu rỗng phải nói chưa có thông tin.",
        })

    registry.register(RegisteredTool(definition("retrieve_knowledge"), retrieve))
    registry.register_reducer(ToolName.RETRIEVE_KNOWLEDGE, reduce)
