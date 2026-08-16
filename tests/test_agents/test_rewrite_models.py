import pytest
from pydantic import ValidationError

from src.agents.legacy.understanding.rewrite_models import (
    ResolvedReference,
    RewriteDecision,
    RewriteReason,
    RewriteResult,
)


def test_changed_rewrite_result_preserves_evidence():
    result = RewriteResult(
        original_text="Cái thứ hai",
        rewritten_text="Người dùng chọn Phố đi bộ Hồ Gươm làm điểm đón.",
        changed=True,
        confidence=0.95,
        resolved_references=[
            ResolvedReference(
                original_phrase="cái thứ hai",
                resolved_value="Phố đi bộ Hồ Gươm",
                source_turn_id="turn-001",
            )
        ],
    )

    assert result.changed is True
    assert result.resolved_references[0].source_turn_id == "turn-001"


def test_unchanged_factory_returns_safe_fallback():
    result = RewriteResult.unchanged(
        "Ở đó",
        ambiguity="insufficient_context",
    )

    assert result.original_text == "Ở đó"
    assert result.rewritten_text == "Ở đó"
    assert result.changed is False
    assert result.confidence == 0
    assert result.ambiguities == ["insufficient_context"]


def test_rewrite_result_preserves_original_text_for_audit():
    result = RewriteResult.unchanged("  Ở đó  ")

    assert result.original_text == "  Ở đó  "
    assert result.rewritten_text == "  Ở đó  "


def test_rewrite_result_rejects_inconsistent_changed_flag():
    with pytest.raises(ValidationError, match="unchanged rewrite"):
        RewriteResult(
            original_text="Ở đó",
            rewritten_text="Ở Hồ Gươm",
            changed=False,
            confidence=0.8,
        )

    with pytest.raises(ValidationError, match="changed rewrite"):
        RewriteResult(
            original_text="Ở đó",
            rewritten_text="Ở đó",
            changed=True,
            confidence=0.8,
        )


def test_resolved_reference_requires_non_blank_source_turn():
    with pytest.raises(ValidationError, match="source_turn_id"):
        ResolvedReference(
            original_phrase="cái thứ hai",
            resolved_value="Hồ Gươm",
            source_turn_id="   ",
        )


def test_rewrite_result_rejects_confidence_outside_range():
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        RewriteResult(
            original_text="Ở đó",
            rewritten_text="Ở đó",
            changed=False,
            confidence=1.1,
        )


def test_rewrite_result_rejects_duplicate_references():
    reference = ResolvedReference(
        original_phrase="cái thứ hai",
        resolved_value="Hồ Gươm",
        source_turn_id="turn-001",
    )
    with pytest.raises(ValidationError, match="must be unique"):
        RewriteResult(
            original_text="Cái thứ hai",
            rewritten_text="Người dùng chọn Hồ Gươm.",
            changed=True,
            confidence=0.9,
            resolved_references=[reference, reference],
        )


def test_rewrite_decision_requires_reasons_to_match_decision():
    with pytest.raises(ValidationError, match="must agree"):
        RewriteDecision(should_rewrite=True)

    with pytest.raises(ValidationError, match="must agree"):
        RewriteDecision(
            should_rewrite=False,
            reasons=[RewriteReason.DEICTIC_REFERENCE],
        )

    with pytest.raises(ValidationError, match="must be unique"):
        RewriteDecision(
            should_rewrite=True,
            reasons=[
                RewriteReason.DEICTIC_REFERENCE,
                RewriteReason.DEICTIC_REFERENCE,
            ],
        )
