from src.backend.services.transcript_rewriter import (
    _confirmation_surface,
    _mask_sensitive_values,
    _minimal_context,
    _restore_sensitive_values,
)


def test_sensitive_values_are_masked_and_restored_exactly():
    raw = "Gọi 0901234567, mã AB-123 lúc 19:30 hoặc email a1@example.com"

    masked, replacements = _mask_sensitive_values(raw)

    assert "0901234567" not in masked
    assert "AB-123" not in masked
    assert "19:30" not in masked
    assert "a1@example.com" not in masked
    assert set(replacements) == {"<NUM_1>", "<ID_1>", "<NUM_2>", "<EMAIL_1>"}
    assert _restore_sensitive_values(masked, replacements) == raw


def test_only_workflow_and_step_are_sent_as_context():
    compact = _minimal_context(
        {
            "current_workflow": "RIDE_BOOKING",
            "current_step": "COLLECT_PICKUP",
            "user_phone": "0901234567",
            "conversation_history": [{"role": "user", "content": "đón tôi ở nhà"}],
        }
    )

    assert compact == {
        "current_workflow": "RIDE_BOOKING",
        "current_step": "COLLECT_PICKUP",
    }


def test_confirmation_guard_detects_diacritic_semantic_change():
    assert _confirmation_surface("dung roi") != _confirmation_surface("đúng rồi")
