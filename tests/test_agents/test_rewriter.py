import json
from hashlib import sha256
from types import SimpleNamespace

import pytest
from openai import APIConnectionError

from src.agents.context import (
    CandidateField,
    ContextCandidate,
    ContextMessage,
    ConversationContext,
)
from src.agents.legacy.understanding.rewrite_base import (
    InvalidRewriteOutputError,
    RewriteProviderError,
    RewriteTimeoutError,
)
from src.agents.legacy.understanding.rewrite_models import (
    ResolvedReference,
    RewriteDecision,
    RewriteReason,
    RewriteResult,
)
from src.agents.legacy.understanding.rewrite_openai import OpenAIContextualRewriteAdapter
from src.agents.legacy.understanding.rewrite_service import ResilientContextualRewriteService
from src.agents.state import ConversationRole, DeliveryStatus


def rewrite_context() -> ConversationContext:
    return ConversationContext(
        session_id="private-session-001",
        raw_transcript="Cái thứ hai",
        current_workflow="RIDE_BOOKING",
        current_step="SELECT_PICKUP_CANDIDATE",
        available_candidates=[
            ContextCandidate(
                field=CandidateField.PICKUP,
                index=1,
                display_name="Hồ Gươm",
            ),
            ContextCandidate(
                field=CandidateField.PICKUP,
                index=2,
                display_name="Phố đi bộ Hồ Gươm",
                address="Đinh Tiên Hoàng",
            ),
        ],
        recent_messages=[
            ContextMessage(
                message_id="turn-001:assistant",
                turn_id="turn-001",
                role=ConversationRole.ASSISTANT,
                content=("Tôi tìm thấy Hồ Gươm và Phố đi bộ Hồ Gươm. Bạn chọn địa điểm nào?"),
                delivery_status=DeliveryStatus.DELIVERED,
            )
        ],
        character_budget=1000,
    )


def rewrite_decision(*, should_rewrite: bool = True) -> RewriteDecision:
    return RewriteDecision(
        should_rewrite=should_rewrite,
        reasons=[RewriteReason.ORDINAL_SELECTION] if should_rewrite else [],
    )


def valid_rewrite(**updates) -> RewriteResult:
    values = {
        "original_text": "Cái thứ hai",
        "rewritten_text": "Người dùng chọn Phố đi bộ Hồ Gươm làm điểm đón.",
        "changed": True,
        "confidence": 0.95,
        "resolved_references": [
            ResolvedReference(
                original_phrase="Cái thứ hai",
                resolved_value="Phố đi bộ Hồ Gươm",
                source_turn_id="turn-001",
            )
        ],
    }
    values.update(updates)
    return RewriteResult(**values)


class RecordingRewriter:
    def __init__(self, result: RewriteResult | None = None, error: Exception | None = None) -> None:
        self.result = result or valid_rewrite()
        self.error = error
        self.calls = []

    async def rewrite(self, original_text, context, decision):
        self.calls.append((original_text, context, decision))
        if self.error is not None:
            raise self.error
        return self.result


class FakeResponses:
    def __init__(self, *, parsed=None, error=None) -> None:
        self.parsed = parsed
        self.error = error
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(output_parsed=self.parsed)


class FakeOpenAIClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


@pytest.mark.asyncio
async def test_resilient_rewriter_returns_grounded_candidate_rewrite():
    primary = RecordingRewriter()
    service = ResilientContextualRewriteService(primary)

    result = await service.rewrite(
        "Cái thứ hai",
        rewrite_context(),
        rewrite_decision(),
    )

    assert result == valid_rewrite()
    assert primary.calls == [("Cái thứ hai", rewrite_context(), rewrite_decision())]


@pytest.mark.asyncio
async def test_fast_path_does_not_call_provider():
    primary = RecordingRewriter()
    result = await ResilientContextualRewriteService(primary).rewrite(
        "Đặt xe từ Hồ Gươm đến Times City",
        rewrite_context(),
        rewrite_decision(should_rewrite=False),
    )

    assert result.changed is False
    assert result.rewritten_text == result.original_text
    assert result.ambiguities == []
    assert primary.calls == []


@pytest.mark.asyncio
async def test_sensitive_current_input_never_calls_provider():
    primary = RecordingRewriter()
    service = ResilientContextualRewriteService(primary)

    for text in ("Số đó là 0901234567", "Mã lúc nãy là GSM-12345"):
        result = await service.rewrite(text, rewrite_context(), rewrite_decision())
        assert result.ambiguities == ["sensitive_input"]
    assert primary.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "ambiguity"),
    [
        (RewriteTimeoutError("timeout"), "rewrite_timeout"),
        (RewriteProviderError("provider"), "rewrite_provider_error"),
        (InvalidRewriteOutputError("invalid"), "invalid_rewrite_output"),
    ],
)
async def test_rewriter_failures_fall_back_to_original_text(error, ambiguity):
    service = ResilientContextualRewriteService(RecordingRewriter(error=error))

    result = await service.rewrite("Cái thứ hai", rewrite_context(), rewrite_decision())

    assert result == RewriteResult.unchanged("Cái thứ hai", ambiguity=ambiguity)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_result",
    [
        valid_rewrite(original_text="Provider changed original"),
        valid_rewrite(
            resolved_references=[
                ResolvedReference(
                    original_phrase="Cái thứ hai",
                    resolved_value="Phố đi bộ Hồ Gươm",
                    source_turn_id="unknown-turn",
                )
            ]
        ),
        valid_rewrite(
            rewritten_text="Người dùng chọn Royal City làm điểm đón.",
            resolved_references=[
                ResolvedReference(
                    original_phrase="Cái thứ hai",
                    resolved_value="Royal City",
                    source_turn_id="turn-001",
                )
            ],
        ),
        valid_rewrite(
            resolved_references=[
                ResolvedReference(
                    original_phrase="phrase không tồn tại",
                    resolved_value="Phố đi bộ Hồ Gươm",
                    source_turn_id="turn-001",
                )
            ]
        ),
        valid_rewrite(
            rewritten_text=("Người dùng chọn Phố đi bộ Hồ Gươm và có số 0901234567."),
        ),
        valid_rewrite(
            rewritten_text=("Người dùng chọn Phố đi bộ Hồ Gươm tại 123 đường Bịa."),
        ),
        valid_rewrite(
            rewritten_text=("Người dùng chọn Phố đi bộ Hồ Gươm và xác nhận đặt xe đi."),
        ),
    ],
)
async def test_unsafe_rewrite_output_falls_back(unsafe_result):
    service = ResilientContextualRewriteService(RecordingRewriter(result=unsafe_result))

    result = await service.rewrite("Cái thứ hai", rewrite_context(), rewrite_decision())

    assert result.changed is False
    assert result.original_text == "Cái thứ hai"
    assert result.ambiguities == ["unsafe_rewrite_output"]


@pytest.mark.asyncio
async def test_openai_adapter_uses_sanitized_structured_request():
    expected = valid_rewrite()
    responses = FakeResponses(parsed=expected)
    adapter = OpenAIContextualRewriteAdapter(
        api_key="test-key",
        model="test-model",
        client=FakeOpenAIClient(responses),
    )
    context = rewrite_context()

    result = await adapter.rewrite("Cái thứ hai", context, rewrite_decision())

    assert result == expected
    request = responses.calls[0]
    assert request["text_format"] is RewriteResult
    assert request["store"] is False
    assert request["model"] == "test-model"
    assert request["safety_identifier"] == sha256(context.session_id.encode()).hexdigest()
    assert context.session_id not in request["input"]
    payload = json.loads(request["input"])
    assert payload["original_text"] == "Cái thứ hai"
    assert "session_id" not in payload["context"]
    assert "raw_transcript" not in payload["context"]


@pytest.mark.asyncio
async def test_openai_adapter_normalizes_timeout_provider_and_invalid_output():
    request = SimpleNamespace(method="POST", url="https://api.openai.com")
    cases = [
        (TimeoutError(), RewriteTimeoutError),
        (APIConnectionError(request=request), RewriteProviderError),
    ]
    for error, expected_error in cases:
        adapter = OpenAIContextualRewriteAdapter(
            api_key="test-key",
            model="test-model",
            client=FakeOpenAIClient(FakeResponses(error=error)),
        )
        with pytest.raises(expected_error):
            await adapter.rewrite("Cái thứ hai", rewrite_context(), rewrite_decision())

    adapter = OpenAIContextualRewriteAdapter(
        api_key="test-key",
        model="test-model",
        client=FakeOpenAIClient(FakeResponses(parsed=None)),
    )
    with pytest.raises(InvalidRewriteOutputError):
        await adapter.rewrite("Cái thứ hai", rewrite_context(), rewrite_decision())
