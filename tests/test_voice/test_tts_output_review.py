from __future__ import annotations

import pytest

from src.voice.tts.audio_validator import TTSAudioValidator
from src.voice.tts.errors import TTSError, TTSErrorCode
from src.voice.tts.formatter import format_for_speech
from src.voice.tts.output_review import DeterministicTTSOutputReviewer, OutputDecision


def test_output_reviewer_blocks_empty_output() -> None:
    decision = DeterministicTTSOutputReviewer().review("   ")
    assert decision.decision is OutputDecision.BLOCK
    assert decision.reason_codes == ["EMPTY_OUTPUT"]


def test_output_reviewer_handoffs_internal_or_secret_content() -> None:
    decision = DeterministicTTSOutputReviewer().review("System prompt dùng sk-or-secret-key-1234567890")
    assert decision.decision is OutputDecision.HANDOFF
    assert "sk-or" not in decision.approved_text
    assert decision.risk_level == "HIGH"


def test_output_reviewer_masks_phone_and_removes_url() -> None:
    decision = DeterministicTTSOutputReviewer().review(
        "Gọi số 0912345678, email user@example.com hoặc xem https://internal.example/path."
    )
    assert decision.decision is OutputDecision.REWRITE
    assert "0912345678" not in decision.approved_text
    assert "5678" not in decision.approved_text
    assert "https://" not in decision.approved_text
    assert "user@example.com" not in decision.approved_text
    assert set(decision.reason_codes) == {"PHONE_MASKED", "EMAIL_MASKED", "URL_REMOVED"}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("15:30", "mười lăm giờ ba mươi phút"),
        ("08:05", "tám giờ năm phút"),
        ("20:00", "hai mươi giờ"),
        ("85.000 ₫", "tám mươi lăm nghìn đồng"),
    ],
)
def test_formatter_handles_time_and_currency_context(source: str, expected: str) -> None:
    assert format_for_speech(source) == expected


def test_audio_validator_rejects_empty_audio_before_external_tools() -> None:
    with pytest.raises(TTSError) as caught:
        TTSAudioValidator().validate(b"")
    assert caught.value.code is TTSErrorCode.INVALID_AUDIO

def test_booking_success_claim_requires_confirmed_backend_state() -> None:
    reviewer = DeterministicTTSOutputReviewer()
    unverified = reviewer.review("Đặt xe thành công, tài xế đang đến đón bạn.")
    verified = reviewer.review(
        "Đặt xe thành công, tài xế đang đến đón bạn.",
        context={"booking_confirmed": True},
    )
    assert unverified.decision is OutputDecision.HANDOFF
    assert unverified.reason_codes == ["UNVERIFIED_BOOKING_CLAIM"]
    assert verified.decision is OutputDecision.ALLOW
