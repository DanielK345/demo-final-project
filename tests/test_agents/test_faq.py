import pytest

from src.agents.rag.answer_generator import ExtractiveAnswerGenerator
from src.agents.schemas import (
    ActionType,
    AgentInput,
    ToolName,
    ToolResult,
    ToolStatus,
    WorkflowType,
)
from src.agents.state import AgentState
from src.agents.workflows.faq import FAQWorkflow
from src.agents.workflows.faq_models import FAQData, FAQStep


def apply_action(state: AgentState, action) -> AgentState:
    return state.apply(action.state_updates)


async def start_faq(
    workflow: FAQWorkflow,
    question: str = "Dịch vụ hỗ trợ thanh toán thế nào?",
):
    state = AgentState(session_id="session-001")
    action = await workflow.handle(
        AgentInput(session_id="session-001", turn_id="turn-001", transcript=question),
        state,
    )
    return action, apply_action(state, action)


@pytest.mark.asyncio
async def test_faq_requests_knowledge_and_persists_question():
    action, _ = await start_faq(FAQWorkflow())

    assert action.action_type is ActionType.CALL_TOOL
    assert action.tool_call is not None
    assert action.tool_call.tool_name is ToolName.RETRIEVE_KNOWLEDGE
    assert action.state_updates["current_step"] == FAQStep.WAITING_FOR_KNOWLEDGE
    data = FAQData.model_validate(action.state_updates["collected_data"]["faq"])
    assert data.question == "Dịch vụ hỗ trợ thanh toán thế nào?"


@pytest.mark.asyncio
async def test_faq_returns_only_grounded_content_sorted_by_score():
    workflow = FAQWorkflow(min_score=0.75, top_k=2)
    call, state = await start_faq(workflow)

    action = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            tool_result=ToolResult(
                tool_name=ToolName.RETRIEVE_KNOWLEDGE,
                call_id=call.tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data={
                    "documents": [
                        {
                            "content": "Nội dung điểm thấp không được sử dụng.",
                            "source": "mock-low",
                            "score": 0.4,
                        },
                        {
                            "content": "Khách có thể thanh toán bằng tiền mặt.",
                            "source": "mock-payment-v1",
                            "score": 0.91,
                        },
                        {
                            "content": "Phương thức điện tử phụ thuộc ứng dụng.",
                            "source": "mock-payment-v2",
                            "score": 0.82,
                        },
                    ]
                },
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.RESPOND
    assert action.message == ("Khách có thể thanh toán bằng tiền mặt. Phương thức điện tử phụ thuộc ứng dụng.")
    assert "điểm thấp" not in action.message
    assert action.state_updates["current_workflow"] is None
    data = FAQData.model_validate(action.state_updates["collected_data"]["faq"])
    assert data.sources == ["mock-payment-v1", "mock-payment-v2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("documents", [[], [{"content": "Không đủ tin cậy", "source": "mock", "score": 0.2}]])
async def test_faq_falls_back_without_grounded_documents(documents):
    workflow = FAQWorkflow(min_score=0.75)
    call, state = await start_faq(workflow)

    action = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            tool_result=ToolResult(
                tool_name=ToolName.RETRIEVE_KNOWLEDGE,
                call_id=call.tool_call.call_id,
                status=ToolStatus.SUCCESS,
                data={"documents": documents},
            ),
        ),
        state,
    )

    assert action.action_type is ActionType.RESPOND
    assert "chưa tìm thấy thông tin đủ tin cậy" in action.message
    assert action.state_updates["pending_tool_call_id"] is None


@pytest.mark.asyncio
async def test_faq_retries_retryable_retrieval_error_once():
    workflow = FAQWorkflow(max_retry_count=2)
    call, state = await start_faq(workflow)

    retry = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            tool_result=ToolResult(
                tool_name=ToolName.RETRIEVE_KNOWLEDGE,
                call_id=call.tool_call.call_id,
                status=ToolStatus.ERROR,
                error="knowledge service timeout",
                error_code="TIMEOUT",
                retryable=True,
            ),
        ),
        state,
    )

    assert retry.action_type is ActionType.CALL_TOOL
    assert retry.tool_call is not None
    assert retry.tool_call.call_id != call.tool_call.call_id
    assert retry.state_updates["retry_count"] == 1


@pytest.mark.asyncio
async def test_faq_handoffs_on_critical_or_mismatched_result():
    workflow = FAQWorkflow()
    call, state = await start_faq(workflow)

    critical = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            tool_result=ToolResult(
                tool_name=ToolName.RETRIEVE_KNOWLEDGE,
                call_id=call.tool_call.call_id,
                status=ToolStatus.ERROR,
                error="knowledge index unavailable",
                retryable=False,
            ),
        ),
        state,
    )
    mismatch = await workflow.handle(
        AgentInput(
            session_id="session-001",
            turn_id="turn-001",
            tool_result=ToolResult(
                tool_name=ToolName.RETRIEVE_KNOWLEDGE,
                call_id="wrong-call",
                status=ToolStatus.SUCCESS,
                data={"documents": []},
            ),
        ),
        state,
    )

    assert critical.action_type is ActionType.HANDOFF
    assert mismatch.action_type is ActionType.HANDOFF
    assert critical.state_updates["current_workflow"] is WorkflowType.HUMAN_HANDOFF


@pytest.mark.asyncio
async def test_extractive_generator_never_adds_unretrieved_facts():
    generator = ExtractiveAnswerGenerator(max_documents=1)
    from src.agents.tools.schemas import KnowledgeDocument

    answer = await generator.generate(
        question="Một câu hỏi bất kỳ",
        documents=[
            KnowledgeDocument(
                content="Đây là nội dung duy nhất được phê duyệt.",
                source="mock-approved",
                score=0.9,
            )
        ],
    )

    assert answer == "Đây là nội dung duy nhất được phê duyệt."
