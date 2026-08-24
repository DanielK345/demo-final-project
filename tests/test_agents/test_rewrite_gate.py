from src.agents.context import (
    CandidateField,
    ContextCandidate,
    ContextMessage,
    ConversationContext,
)
from src.agents.legacy.understanding.rewrite_gate import ContextualRewriteGate
from src.agents.legacy.understanding.rewrite_models import RewriteReason
from src.agents.state import ConversationRole, DeliveryStatus


def context(
    *,
    candidates: list[ContextCandidate] | None = None,
    assistant_message: ContextMessage | None = None,
    current_step: str | None = None,
) -> ConversationContext:
    return ConversationContext(
        session_id="session-001",
        raw_transcript="",
        current_step=current_step,
        available_candidates=candidates or [],
        recent_messages=[assistant_message] if assistant_message else [],
        character_budget=1000,
    )


def candidate(index: int) -> ContextCandidate:
    return ContextCandidate(
        field=CandidateField.PICKUP,
        index=index,
        display_name=f"Địa điểm {index}",
    )


def delivered_question() -> ContextMessage:
    return ContextMessage(
        message_id="turn-001:assistant",
        turn_id="turn-001",
        role=ConversationRole.ASSISTANT,
        content="Bạn muốn chọn địa điểm nào?",
        delivery_status=DeliveryStatus.DELIVERED,
    )


def unavailable_question(status: DeliveryStatus) -> ContextMessage:
    return ContextMessage(
        message_id="turn-001:assistant",
        turn_id="turn-001",
        role=ConversationRole.ASSISTANT,
        content="Bạn muốn chọn địa điểm nào?",
        delivery_status=status,
    )


def test_gate_rewrites_ordinal_selection_when_candidate_exists():
    gate = ContextualRewriteGate()
    candidate_context = context(
        candidates=[candidate(1), candidate(2)],
        assistant_message=delivered_question(),
    )

    second = gate.evaluate("Cái thứ hai", candidate_context)
    numeric = gate.evaluate("Số 2", candidate_context)

    assert second.should_rewrite is True
    assert second.reasons == [RewriteReason.ORDINAL_SELECTION]
    assert numeric.reasons == [RewriteReason.ORDINAL_SELECTION]


def test_gate_skips_ordinal_selection_without_requested_candidate():
    gate = ContextualRewriteGate()

    assert gate.evaluate("Cái thứ hai", context()).should_rewrite is False
    assert (
        gate.evaluate(
            "Số 3",
            context(
                candidates=[candidate(1), candidate(2)],
                assistant_message=delivered_question(),
            ),
        ).should_rewrite
        is False
    )

    split_candidate_context = context(
        candidates=[
            candidate(1),
            ContextCandidate(
                field=CandidateField.DESTINATION,
                index=1,
                display_name="Điểm đến 1",
            ),
        ],
        assistant_message=delivered_question(),
        current_step="SELECT_PICKUP_CANDIDATE",
    )
    assert gate.evaluate("Cái thứ hai", split_candidate_context).should_rewrite is False


def test_gate_rewrites_deictic_reference_only_with_audible_context():
    gate = ContextualRewriteGate()

    decision = gate.evaluate("Đón tôi ở đó", context(assistant_message=delivered_question()))

    assert decision.should_rewrite is True
    assert decision.reasons == [RewriteReason.DEICTIC_REFERENCE]
    assert gate.evaluate("Đón tôi ở đó", context()).should_rewrite is False
    for status in (DeliveryStatus.PENDING, DeliveryStatus.FAILED):
        assert (
            gate.evaluate(
                "Đón tôi ở đó",
                context(assistant_message=unavailable_question(status)),
            ).should_rewrite
            is False
        )


def test_gate_rewrites_previous_turn_reference_with_recent_context():
    decision = ContextualRewriteGate().evaluate(
        "Cho tôi chỗ lúc nãy",
        context(assistant_message=delivered_question()),
    )

    assert decision.should_rewrite is True
    assert RewriteReason.PREVIOUS_TURN_REFERENCE in decision.reasons
    assert (
        ContextualRewriteGate()
        .evaluate(
            "Cho tôi chỗ lúc nãy",
            context(assistant_message=unavailable_question(DeliveryStatus.PENDING)),
        )
        .should_rewrite
        is False
    )


def test_gate_classifies_ambiguous_correction_without_double_deictic_reason():
    decision = ContextualRewriteGate().evaluate(
        "Đổi chỗ đó sang Times City",
        context(assistant_message=delivered_question()),
    )

    assert decision.reasons == [RewriteReason.AMBIGUOUS_CORRECTION]


def test_gate_uses_short_contextual_reply_only_after_assistant_question():
    gate = ContextualRewriteGate()

    decision = gate.evaluate("Hồ Gươm", context(assistant_message=delivered_question()))

    assert decision.reasons == [RewriteReason.SHORT_CONTEXTUAL_REPLY]
    assert gate.evaluate("Hồ Gươm", context()).should_rewrite is False


def test_gate_keeps_complete_statement_on_fast_path():
    decision = ContextualRewriteGate().evaluate(
        "Tôi muốn đặt xe từ Hồ Gươm đến Times City",
        context(assistant_message=delivered_question()),
    )

    assert decision.should_rewrite is False
    assert (
        ContextualRewriteGate()
        .evaluate("Tôi muốn đặt xe", context(assistant_message=delivered_question()))
        .should_rewrite
        is False
    )


def test_gate_keeps_confirmation_rejection_and_handoff_on_fast_path():
    gate = ContextualRewriteGate()
    active_context = context(assistant_message=delivered_question())

    for transcript in (
        "Đúng, đặt xe đi",
        "Vâng ạ",
        "Không",
        "Không đồng ý",
        "Tôi đang gặp nguy hiểm",
        "Cho tôi gặp tổng đài viên",
    ):
        assert gate.evaluate(transcript, active_context).should_rewrite is False


def test_gate_skips_empty_tool_result_only_turn():
    decision = ContextualRewriteGate().evaluate(
        "",
        context(assistant_message=delivered_question()),
    )

    assert decision.should_rewrite is False
